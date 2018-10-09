import pyrpr
import pyrprimagefilters as rif
import sys
import numpy as np
import bgl


class RifFilterType:
    Bilateral = 0
    Lwr = 1
    Eaw = 2


class RifFilterInput:
    Color = 0
    Normal = 1
    Depth = 2
    WorldCoordinate = 3
    ObjectId = 4
    Trans = 5


class RifContext():
    def __init__(self, rpr_context):
        def is_gpu_enabled(creation_flags):
            for i in range(16):
                if getattr(pyrpr, 'CREATION_FLAGS_ENABLE_GPU%d' % i) & creation_flags:
                    return True

            return False

        creation_flags = rpr_context.get_creation_flags()
        if creation_flags & pyrpr.CREATION_FLAGS_ENABLE_METAL:
            self._rif_context = rif.ContextMetal(rpr_context)
        elif is_gpu_enabled(creation_flags):
            self._rif_context = rif.ContextGPU(rpr_context)
        elif creation_flags & pyrpr.CREATION_FLAGS_ENABLE_CPU:
            self._rif_context = rif.ContextCPU(rpr_context)
        else:
            raise ValueError("Not supported CONTEXT_CREATION_FLAGS")

        self._rif_command_queue = self._rif_context.create_command_queue()
        self._rif_output_image = None


    def context(self):
        return self._rif_context


    def queue(self):
        return self._rif_command_queue


    def output(self):
        return self._rif_output_image


    def create_output(self, width, height):
        self._rif_output_image = self._rif_context.create_image(width, height)


    def create_output_gl(self, frame_buffer_gl):
        self._rif_output_image = self._rif_context.create_frame_buffer_image_gl(frame_buffer_gl)


    def create_rif_image(self, rpr_framebuffer):
        return self._rif_context.create_frame_buffer_image(rpr_framebuffer)


    def update_inputs(self, rif_filter):
        for input_data in rif_filter.inputs().values():
            input_data.rif_image.update()


class RifFilterWrapper():
    class _InputTraits():
        def __init__(self, rif_image, rpr_framebuffer, sigma):
            self.rif_image = rif_image
            self.rpr_framebuffer = rpr_framebuffer
            self.sigma = sigma


    def __init__(self, rif_context):
        self._rif_context = rif_context
        self._rif_image_filter = None
        self._aux_filters = []
        self._aux_images = []
        self._inputs = {}
        self._params = {}


    def inputs(self):
        return self._inputs


    def add_input(self, input_id, rif_image, rpr_framebuffer, sigma):
        self._inputs[input_id] = RifFilterWrapper._InputTraits(rif_image, rpr_framebuffer, sigma)


    def add_param(self, name, param):
        self._params[name] = param


    def attach_filter(self):
        raise NotImplementedError()


    def detach_filter(self):
        for filter in self._aux_filters:
            self._rif_context.queue().detach(filter)

        self._rif_context.queue().detach(self._rif_image_filter)


    def apply_parameters(self):
        for name, param in self._params.items():
            self._rif_image_filter.set_parameter(name, param)


    def _setup_variance_image_filter(self, input_filter, out_variance_image):
        input_filter.set_parameter('positionsImg', self._inputs[RifFilterInput.WorldCoordinate].rif_image)
        input_filter.set_parameter('normalsImg', self._inputs[RifFilterInput.Normal].rif_image)
        input_filter.set_parameter('meshIdsImg', self._inputs[RifFilterInput.ObjectId].rif_image)
        input_filter.set_parameter('outVarianceImg', out_variance_image)


    def create_rif_image_descr(width, height):
        rif_image_desc = rif.ffi.new('rif_image_desc *')
        rif_image_desc.image_width = width
        rif_image_desc.image_height = height
        rif_image_desc.image_depth = 1
        rif_image_desc.num_components = 4
        rif_image_desc.image_row_pitch = 0
        rif_image_desc.image_slice_pitch = 0
        rif_image_desc.type = rif.COMPONENT_TYPE_FLOAT32

        return rif_image_desc


class RifFilterBilateral(RifFilterWrapper):
    def __init__(self, rif_context):
        super(RifFilterBilateral, self).__init__(rif_context)
        self._input_images = []
        self._sigmas = []

        self._rif_image_filter = self._rif_context.context().create_filter(rif.IMAGE_FILTER_BILATERAL_DENOISE)


    def attach_filter(self):
        self._rif_image_filter.set_parameter('inputs', [input.rif_image for input in self._inputs.values()])
        self._rif_image_filter.set_parameter('sigmas', [input.sigma for input in self._inputs.values()])
        self._rif_image_filter.set_parameter('inputsNum', len(self._inputs))

        self._rif_context.queue().attach(self._rif_image_filter, self._inputs[RifFilterInput.Color].rif_image, self._rif_context.output())


class RifFilterLwr(RifFilterWrapper):
    class _AuxInput:
        Color = 0
        Normal = 1
        Depth = 2
        Trans = 3
        AuxInputMax = 4

    def __init__(self, rif_context, width, height):
        super(RifFilterLwr, self).__init__(rif_context)

        self._rif_image_filter = self._rif_context.context().create_filter(rif.IMAGE_FILTER_LWR_DENOISE)

        desc = RifFilterWrapper.create_rif_image_descr(width, height)

        for i in range(RifFilterLwr._AuxInput.AuxInputMax):
            aux_filter = self._rif_context.context().create_filter(rif.IMAGE_FILTER_TEMPORAL_ACCUMULATOR)
            self._aux_filters.append(aux_filter)

            aux_image = self._rif_context.context().create_image(width, height)
            self._aux_images.append(aux_image)


    def attach_filter(self):
        # make variance image filters
        for i in range(len(self._aux_filters)):
            self._setup_variance_image_filter(self._aux_filters[i], self._aux_images[i])

        # configure Filter
        self._rif_image_filter.set_parameter('vColorImg', self._aux_images[RifFilterLwr._AuxInput.Color])
        
        self._rif_image_filter.set_parameter('normalsImg', self._inputs[RifFilterInput.Normal].rif_image)
        self._rif_image_filter.set_parameter('vNormalsImg', self._aux_images[RifFilterLwr._AuxInput.Normal])

        self._rif_image_filter.set_parameter('depthImg', self._inputs[RifFilterInput.Depth].rif_image)
        self._rif_image_filter.set_parameter('vDepthImg', self._aux_images[RifFilterLwr._AuxInput.Depth])

        self._rif_image_filter.set_parameter('transImg', self._inputs[RifFilterInput.Trans].rif_image)
        self._rif_image_filter.set_parameter('vTransImg', self._aux_images[RifFilterLwr._AuxInput.Trans])

        # attach filters
        self._rif_context.queue().attach(self._aux_filters[RifFilterLwr._AuxInput.Trans], 
                                         self._inputs[RifFilterInput.Trans].rif_image, self._aux_images[RifFilterLwr._AuxInput.Trans])
        self._rif_context.queue().attach(self._aux_filters[RifFilterLwr._AuxInput.Depth], 
                                         self._inputs[RifFilterInput.Depth].rif_image, self._aux_images[RifFilterLwr._AuxInput.Depth])
        self._rif_context.queue().attach(self._aux_filters[RifFilterLwr._AuxInput.Normal], 
                                         self._inputs[RifFilterInput.Normal].rif_image, self._aux_images[RifFilterLwr._AuxInput.Normal])
        self._rif_context.queue().attach(self._aux_filters[RifFilterLwr._AuxInput.Color], 
                                         self._inputs[RifFilterInput.Color].rif_image, self._aux_images[RifFilterLwr._AuxInput.Color])

        self._rif_context.queue().attach(self._rif_image_filter, self._inputs[RifFilterInput.Color].rif_image, self._rif_context.output())


class RifFilterEaw(RifFilterWrapper):
    class _AuxInput:
        Color = 0
        Mlaa = 1
        Depth = 2
        AuxInputMax = 3

    def __init__(self, rif_context, width, height):
        super(RifFilterEaw, self).__init__(rif_context)

        self._rif_image_filter = self._rif_context.context().create_filter(rif.IMAGE_FILTER_EAW_DENOISE)

        desc = RifFilterWrapper.create_rif_image_descr(width, height)

        for i in range(RifFilterEaw._AuxInput.AuxInputMax):
            if i == RifFilterEaw._AuxInput.Color:
                aux_filter = self._rif_context.context().create_filter(rif.IMAGE_FILTER_TEMPORAL_ACCUMULATOR)
            elif i == RifFilterEaw._AuxInput.Depth:
                aux_filter = self._rif_context.context().create_filter(rif.IMAGE_FILTER_NORMALIZATION)
            else:
                aux_filter = self._rif_context.context().create_filter(rif.IMAGE_FILTER_MLAA)

            self._aux_filters.append(aux_filter)

            aux_image = self._rif_context.context().create_image(width, height)
            self._aux_images.append(aux_image)


    def attach_filter(self):
        # setup inputs
        self._rif_image_filter.set_parameter('normalsImg', self._inputs[RifFilterInput.Normal].rif_image)
        self._rif_image_filter.set_parameter('transImg', self._inputs[RifFilterInput.Trans].rif_image)
        self._rif_image_filter.set_parameter('depthImg', self._aux_images[RifFilterEaw._AuxInput.Depth])
        self._rif_image_filter.set_parameter('colorVar', self._inputs[RifFilterInput.Color].rif_image)

        # setup sigmas
        self._rif_image_filter.set_parameter('colorSigma', self._inputs[RifFilterInput.Color].sigma)
        self._rif_image_filter.set_parameter('normalSigma', self._inputs[RifFilterInput.Normal].sigma)
        self._rif_image_filter.set_parameter('depthSigma', self._inputs[RifFilterInput.Depth].sigma)
        self._rif_image_filter.set_parameter('transSigma', self._inputs[RifFilterInput.Trans].sigma)

        # setup color variance filter
        self._setup_variance_image_filter(self._aux_filters[RifFilterEaw._AuxInput.Color], self._aux_images[RifFilterEaw._AuxInput.Color])

        # setup MLAA filter
        self._aux_filters[RifFilterEaw._AuxInput.Mlaa].set_parameter('normalsImg', self._inputs[RifFilterInput.Normal].rif_image)
        self._aux_filters[RifFilterEaw._AuxInput.Mlaa].set_parameter('meshIDImg', self._inputs[RifFilterInput.ObjectId].rif_image)
        self._aux_filters[RifFilterEaw._AuxInput.Mlaa].set_parameter('depthImg', self._inputs[RifFilterInput.Depth].rif_image)

        # attach filters
        self._rif_context.queue().attach(self._aux_filters[RifFilterEaw._AuxInput.Depth],
                                         self._inputs[RifFilterInput.Depth].rif_image, self._aux_images[RifFilterEaw._AuxInput.Depth])
        self._rif_context.queue().attach(self._aux_filters[RifFilterEaw._AuxInput.Color], 
                                         self._inputs[RifFilterInput.Color].rif_image, self._rif_context.output())
        self._rif_context.queue().attach(self._rif_image_filter, 
                                         self._rif_context.output(), self._aux_images[RifFilterEaw._AuxInput.Mlaa])
        self._rif_context.queue().attach(self._aux_filters[RifFilterEaw._AuxInput.Mlaa], 
                                         self._aux_images[RifFilterEaw._AuxInput.Mlaa], self._rif_context.output())



class ImageFilter():
    def __init__(self, rpr_context, rif_filter_type: RifFilterType, width, height, frame_buffer_gl):
        self._rpr_context = rpr_context
        self._width = width
        self._height = height
        self._rif_context = RifContext(self._rpr_context)
        self.rif_filter_type = rif_filter_type

        if frame_buffer_gl:
            self._rif_context.create_output_gl(frame_buffer_gl)
        else:
            self._rif_context.create_output(self._width, self._height)

        if rif_filter_type == RifFilterType.Bilateral:
            self._rif_filter = RifFilterBilateral(self._rif_context)
        elif rif_filter_type == RifFilterType.Lwr:
            self._rif_filter = RifFilterLwr(self._rif_context, self._width, self._height)
        elif rif_filter_type == RifFilterType.Eaw:
            self._rif_filter = RifFilterEaw(self._rif_context, self._width, self._height)        


    def __del__(self):
        if self._rif_filter:
            self._rif_filter.detach_filter()


    def add_input(self, input_id, rpr_framebuffer, sigma):
        rif_image = self._rif_context.create_rif_image(rpr_framebuffer)
        self._rif_filter.add_input(input_id, rif_image, rpr_framebuffer, sigma)


    def add_param(self, name, param):
        self._rif_filter.add_param(name, param)

    
    def attach_filter(self):
        self._rif_filter.attach_filter()
        self._rif_filter.apply_parameters()


    def run(self):
        self._rif_context.update_inputs(self._rif_filter)
        self._rif_context.queue().execute()

    def get_data(self):
        return self._rif_context.output().get_data()
