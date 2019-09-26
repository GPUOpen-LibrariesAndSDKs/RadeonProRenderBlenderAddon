from abc import ABCMeta, abstractmethod

import pyrpr
import pyrprimagefilters as rif
from rprblender import utils
from rprblender.utils.user_settings import get_user_settings


class ImageFilter(metaclass=ABCMeta):
    def __init__(self, rpr_context, inputs, sigmas, params, width, height, frame_buffer_gl=None):
        # field for custom external settings
        self.settings = None

        # creating context
        creation_flags = rpr_context.get_creation_flags()
        if creation_flags & pyrpr.CREATION_FLAGS_ENABLE_METAL:
            self.context = rif.ContextMetal(rpr_context)
        elif pyrpr.is_gpu_enabled(creation_flags):
            self.context = rif.ContextGPU(rpr_context)
        elif creation_flags & pyrpr.CREATION_FLAGS_ENABLE_CPU:
            self.context = rif.ContextCPU(rpr_context)
        else:
            raise ValueError("Not supported CONTEXT_CREATION_FLAGS: %d" % creation_flags)

        self.width = width
        self.height = height
        self.filter = None
        self.params = params
        self.sigmas = sigmas
        self.inputs = {}

        if isinstance(inputs, set):
            for input_id in inputs:
                self.inputs[input_id] = self.context.create_image(self.width, self.height)

        else:
            for input_id, fb in inputs.items():
                if fb:
                    self.inputs[input_id] = self.context.create_frame_buffer_image(fb)
                else:
                    self.inputs[input_id] = self.context.create_image(self.width, self.height)

        self.command_queue = self.context.create_command_queue()
        if frame_buffer_gl:
            self.output_image = self.context.create_frame_buffer_image_gl(frame_buffer_gl)
        else:
            self.output_image = self.context.create_image(self.width, self.height)

        self._create_filter()

    def update_sigma(self, input_id, sigma):
        self.sigmas[input_id] = sigma

    def update_param(self, name, value):
        self.params[name] = value

    def update_input(self, input_id, data, pos=(0, 0)):
        self.inputs[input_id].set_data(data, pos)

    @abstractmethod
    def _create_filter(self):
        pass

    def apply_parameters(self):
        for name, param in self.params.items():
            self.filter.set_parameter(name, param)

    def apply_sigmas(self):
        pass

    def _setup_variance_image_filter(self, input_filter, out_variance_image):
        input_filter.set_parameter('positionsImg', self.inputs['world_coordinate'])
        input_filter.set_parameter('normalsImg', self.inputs['normal'])
        input_filter.set_parameter('meshIdsImg', self.inputs['object_id'])
        input_filter.set_parameter('outVarianceImg', out_variance_image)

    def run(self):
        self.apply_parameters()
        self.apply_sigmas()
        
        # updating input images
        for image in self.inputs.values():
            if isinstance(image, rif.FrameBufferImage):
                image.update()

        self.command_queue.execute()

    def get_data(self):
        return self.output_image.get_data()


class ImageFilterBilateral(ImageFilter):
    input_ids = ['color', 'normal', 'world_coordinate', 'object_id']

    def _create_filter(self):
        self.filter = self.context.create_filter(rif.IMAGE_FILTER_BILATERAL_DENOISE)
        self.filter.set_parameter('inputs', [self.inputs[input_id] for input_id in self.input_ids])
        self.filter.set_parameter('inputsNum', len(self.input_ids))

        self.command_queue.attach_image_filter(self.filter, self.inputs['color'], self.output_image)

    def apply_sigmas(self):
        self.filter.set_parameter('sigmas', [self.sigmas[input_id] for input_id in self.input_ids])


class ImageFilterLwr(ImageFilter):
    def _create_filter(self):
        self.filter = self.context.create_filter(rif.IMAGE_FILTER_LWR_DENOISE)

        aux_filters = {}
        aux_images = {}
        for key in ['color', 'normal', 'depth', 'trans']:
            aux_filters[key] = self.context.create_filter(rif.IMAGE_FILTER_TEMPORAL_ACCUMULATOR)
            aux_images[key] = self.context.create_image(self.width, self.height)
            self._setup_variance_image_filter(aux_filters[key], aux_images[key])            

        # configure Filter
        self.filter.set_parameter('vColorImg', aux_images['color'])
        
        self.filter.set_parameter('normalsImg', self.inputs['normal'])
        self.filter.set_parameter('vNormalsImg', aux_images['normal'])

        self.filter.set_parameter('depthImg', self.inputs['depth'])
        self.filter.set_parameter('vDepthImg', aux_images['depth'])

        self.filter.set_parameter('transImg', self.inputs['trans'])
        self.filter.set_parameter('vTransImg', aux_images['trans'])

        # attach filters
        self.command_queue.attach_image_filter(aux_filters['trans'], self.inputs['trans'], aux_images['trans'])
        self.command_queue.attach_image_filter(aux_filters['depth'], self.inputs['depth'], aux_images['depth'])
        self.command_queue.attach_image_filter(aux_filters['normal'], self.inputs['normal'], aux_images['normal'])
        self.command_queue.attach_image_filter(aux_filters['color'], self.inputs['color'], aux_images['color'])

        self.command_queue.attach_image_filter(self.filter, self.inputs['color'], self.output_image)


class ImageFilterML(ImageFilter):
    ''' Machine Learning Denoiser.  takes a normalized (-1, 1) normals image and a normalized depth image (0,1) 
        as well as an albedo '''
    def _create_filter(self):
        devices = self.get_devices()
        use_oidn = (utils.IS_WIN and devices.cpu_state) or utils.IS_MAC
        if use_oidn:
            self.filter = self.context.create_filter(rif.IMAGE_FILTER_OPENIMAGE_DENOISE)
        else:
            self.filter = self.context.create_filter(rif.IMAGE_FILTER_AI_DENOISE)
            self.filter.set_parameter('useHDR', True)

        models_path = utils.package_root_dir() / 'data/models'
        if not models_path.is_dir():
            # set alternative path
            models_path = utils.package_root_dir() / '../../ThirdParty/RadeonProImageProcessing/models'
        self.filter.set_parameter('modelPath', str(models_path))

        ml_output_image = self.context.create_image(self.width, self.height, 3)

        use_color_only = 'normal' not in self.inputs
        if use_color_only:
            self.filter.set_parameter('colorImg', self.inputs['color'])

        else:
            # setup remap normals filter
            normal_remap_filter = self.context.create_filter(rif.IMAGE_FILTER_REMAP_RANGE)
            normal_remap_filter.set_parameter('dstLo', -1.0)
            normal_remap_filter.set_parameter('dstHi', 1.0)
            normal_remap_image = self.context.create_image(self.width, self.height)
            self.command_queue.attach_image_filter(normal_remap_filter, self.inputs['normal'],
                                                   normal_remap_image)

            # setup remap depth filter
            depth_remap_filter = self.context.create_filter(rif.IMAGE_FILTER_REMAP_RANGE)
            depth_remap_filter.set_parameter('dstLo', 0.0)
            depth_remap_filter.set_parameter('dstHi', 1.0)
            depth_remap_image = self.context.create_image(self.width, self.height)
            self.command_queue.attach_image_filter(depth_remap_filter, self.inputs['depth'],
                                                   depth_remap_image)

            # configure Filter
            self.filter.set_parameter('colorImg', self.inputs['color'])
            self.filter.set_parameter('normalsImg', normal_remap_image)
            self.filter.set_parameter('depthImg', depth_remap_image)
            self.filter.set_parameter('albedoImg', self.inputs['albedo'])

        # setup resample filter
        output_resample_filter = self.context.create_filter(rif.IMAGE_FILTER_RESAMPLE)
        output_resample_filter.set_parameter('interpOperator', rif.IMAGE_INTERPOLATION_NEAREST)
        output_resample_filter.set_parameter('outSize', (self.width, self.height))

        # attach filters
        self.command_queue.attach_image_filter(self.filter, self.inputs['color'],
                                               ml_output_image)

        # attach output resample filter
        self.command_queue.attach_image_filter(output_resample_filter, ml_output_image,
                                               self.output_image)

    def get_devices(self, is_final_engine=True):
        """ Get render devices settings for current mode """
        devices_settings = get_user_settings()
        return devices_settings.final_devices


class ImageFilterEaw(ImageFilter):
    def _create_filter(self):
        self.filter = self.context.create_filter(rif.IMAGE_FILTER_EAW_DENOISE)

        aux_filters = {
            'color': self.context.create_filter(rif.IMAGE_FILTER_TEMPORAL_ACCUMULATOR),
            'mlaa': self.context.create_filter(rif.IMAGE_FILTER_MLAA),
            'depth': self.context.create_filter(rif.IMAGE_FILTER_NORMALIZATION),
        }
        aux_images = {
            'color': self.context.create_image(self.width, self.height),
            'mlaa': self.context.create_image(self.width, self.height),
            'depth': self.context.create_image(self.width, self.height),
        }

        # setup inputs
        self.filter.set_parameter('normalsImg', self.inputs['normal'])
        self.filter.set_parameter('transImg', self.inputs['trans'])
        self.filter.set_parameter('depthImg', aux_images['depth'])
        self.filter.set_parameter('colorVar', self.inputs['color'])

        # setup color variance filter
        self._setup_variance_image_filter(aux_filters['color'], aux_images['color'])

        # setup MLAA filter
        aux_filters['mlaa'].set_parameter('normalsImg', self.inputs['normal'])
        aux_filters['mlaa'].set_parameter('meshIDImg', self.inputs['object_id'])
        aux_filters['mlaa'].set_parameter('depthImg', self.inputs['depth'])

        # attach filters
        self.command_queue.attach_image_filter(aux_filters['depth'], self.inputs['depth'], aux_images['depth'])
        self.command_queue.attach_image_filter(aux_filters['color'], self.inputs['color'], self.output_image)
        self.command_queue.attach_image_filter(self.filter, self.output_image, aux_images['mlaa'])
        self.command_queue.attach_image_filter(aux_filters['mlaa'], aux_images['mlaa'], self.output_image)

    def apply_sigmas(self):
        self.filter.set_parameter('colorSigma', self.sigmas['color'])
        self.filter.set_parameter('normalSigma', self.sigmas['normal'])
        self.filter.set_parameter('depthSigma', self.sigmas['depth'])
        self.filter.set_parameter('transSigma', self.sigmas['trans'])
