import pyrpr
import pyrprimagefilters
import pyrpropencl
import sys
import numpy as np
import math
import platform

from rprblender import logging
import numbers

class Denoiser:
    def __init__(self, render_layers, render_device, denoiser_settings, core_context):
        ''' On initialization the denoiser gets the settings from config and creates the 
        filter chain along with any images needed '''

        self.render_targets = render_layers.render_targets
        self.render_device = render_device
        self.render_layers = render_layers

        self.filters = []
        self.rif_images = {}

        self.add_input('default')   # adding default to all filters

        #Create resolved_frame_buffer with input_image
        desc = pyrpr.ffi.new("rpr_framebuffer_desc*")
        desc.fb_width, desc.fb_height = self.render_targets.render_resolution

        self.resolved_frame_buffer = pyrpr.FrameBuffer()
        pyrpr.ContextCreateFrameBuffer(core_context, (4, pyrpr.COMPONENT_TYPE_FLOAT32), 
                                       desc, self.resolved_frame_buffer)
        pyrpr.FrameBufferClear(self.resolved_frame_buffer)

        self.input_image = self.get_rif_image_from_rpr_frame_buffer(self.resolved_frame_buffer)

        # Get rif image description
        self.rif_image_desc = pyrprimagefilters.ffi.new("rif_image_desc*")
        pyrprimagefilters.ImageGetInfo(self.input_image, pyrprimagefilters.IMAGE_DESC,
                                      sys.getsizeof(self.rif_image_desc), self.rif_image_desc,
                                      pyrprimagefilters.ffi.new("size_t*"))

        #Create output rif images
        self.create_image('rif_output_image')
        self.main_denoiser_filter = None

        filter_name_mapping = {
            'bilateral': self.add_bilateral_filter,
            'eaw': self.add_eaw_filter,
            'lwr': self.add_lwr_filter
        }
        self.filter_type = None

        # create filters from config, 
        filter_name_mapping[denoiser_settings.filter_type](denoiser_settings, self.input_image)
        self.denoiser_settings = denoiser_settings
        
    def __del__(self):
        for filter in self.filters:
            pyrprimagefilters.CommandQueueDetachImageFilter(self.render_device.rif_command_queue,
                                                            filter)
            pyrprimagefilters.ObjectDelete(filter._get_handle())

        for key, image in self.rif_images.items():
            pyrprimagefilters.ObjectDelete(image._handle_ptr[0])

        pyrprimagefilters.ObjectDelete(self.input_image._handle_ptr[0])


    def execute(self, frame_buffer):
        ''' Executes the command_queue '''
        
        pyrpr.ContextResolveFrameBuffer(self.render_device.core_context, 
            self.render_targets.get_frame_buffer('default'), self.resolved_frame_buffer)

        if 'Darwin' == platform.system():
            pyrprimagefilters.ContextExecuteCommandQueue(self.render_device.rif_context, self.render_device.rif_command_queue,
                                                pyrprimagefilters.ffi.NULL, pyrprimagefilters.ffi.NULL )
        else:
            pyrprimagefilters.ContextExecuteCommandQueue(self.render_device.rif_context, self.render_device.rif_command_queue,
                                                pyrprimagefilters.ffi.NULL, pyrprimagefilters.ffi.NULL, pyrprimagefilters.ffi.NULL )

        # Store results in float array to form final image
        mapped_data = pyrprimagefilters.ffi.new("void**")
        rif_result = pyrprimagefilters.ImageMap(self.rif_images["rif_output_image"], pyrprimagefilters.IMAGE_MAP_READ, mapped_data)
        assert rif_result == pyrprimagefilters.SUCCESS

        width, height = self.render_targets.render_resolution

        float_data = pyrprimagefilters.ffi.cast("float*", mapped_data[0])

        buffer_size = width*height*4*4   # 4*4 is the size in bytes of pixel as RGBA color as 4 floats (every color component is float value)
        
        output = np.frombuffer(pyrprimagefilters.ffi.buffer(float_data, buffer_size), dtype=np.float32).reshape(height, width, 4)

        rif_result = pyrprimagefilters.ImageUnmap(self.rif_images["rif_output_image"], mapped_data[0])
        assert rif_result == pyrprimagefilters.SUCCESS

        return output


    def create_image(self, name): 
        ''' Creates an image with the name and adds to list of images if not there already '''   
        if name in self.rif_images:
            return
        self.rif_images[name] = pyrprimagefilters.RifImage()
        pyrprimagefilters.ContextCreateImage(self.render_device.rif_context,
                                             self.rif_image_desc, pyrprimagefilters.ffi.NULL,
                                             self.rif_images[name])  


    def create_filter(self, filter_type): 
        ''' Creates an filter and adds to the list and returns '''   
        filter = pyrprimagefilters.RifImageFilter()
        pyrprimagefilters.ContextCreateImageFilter(self.render_device.rif_context,
                                                   filter_type, filter)
        return filter   


    def add_filter_to_queue(self, filter, input_image, output_image): 
        ''' adds a filter to the queue '''   
        pyrprimagefilters.CommandQueueAttachImageFilter(self.render_device.rif_command_queue,
                                                        filter, input_image, output_image) 
        self.filters.append(filter)


    def add_normalized_image_filter(self, input_image, output_image_name):
        ''' Creates a normalizing filter that normalizes the input image and sets to the output '''

        if output_image_name in self.rif_images:
            return
        self.create_image(output_image_name)
        filter = self.create_filter(pyrprimagefilters.IMAGE_FILTER_NORMALIZATION)
        self.add_filter_to_queue(filter, input_image, self.rif_images[output_image_name])
        

    def add_bilateral_filter(self, settings, input_image):
        ''' a bilateral filter takes a list of input images and sigmas 
            TODO add alpha/z '''
        logging.info("Creating Bilateral Filter ")

        inputs_num = 4   # 1-st input is self.input_image, other 3 are following
        self.add_input('shading_normal')
        self.add_input('world_coordinate')
        self.add_input('object_id')


        filter = self.create_filter(pyrprimagefilters.IMAGE_FILTER_BILATERAL_DENOISE)
        self.filter_type = pyrprimagefilters.IMAGE_FILTER_BILATERAL_DENOISE

        self.input_rif_array = pyrprimagefilters.ArrayObject("rif_image[]", [self.input_image._handle_ptr[0],
                                                             self.rif_images["shading_normal"]._handle_ptr[0],
                                                             self.rif_images["world_coordinate"]._handle_ptr[0],
                                                             self.rif_images["object_id"]._handle_ptr[0]])

        pyrprimagefilters.ImageFilterSetParameterImageArray(filter, b"inputs",
                                                            self.input_rif_array, inputs_num)

        self.sigmas = pyrprimagefilters.ffi.new("float[]", [settings.color_sigma, 
                                                            settings.normal_sigma, 
                                                            settings.p_sigma, 
                                                            settings.trans_sigma])
        pyrprimagefilters.ImageFilterSetParameterFloatArray(filter, b"sigmas",
                                                            self.sigmas, inputs_num)

        pyrprimagefilters.ImageFilterSetParameter1u(filter, b"radius",settings.radius)

        pyrprimagefilters.ImageFilterSetParameter1u(filter, b"inputsNum", inputs_num)
        
        self.add_filter_to_queue(filter, self.input_image, self.rif_images["rif_output_image"])
        self.main_denoiser_filter = filter

    
    def add_variance_image_filter(self, input_image, output_image_name, output_var_image_name):
        ''' creates a variance filter which makes a var image with the output_var_image_name 
            and passes through input to output_image_name '''
        # if variance image is made we can return
        if output_var_image_name in self.rif_images:
            return
        self.create_image(output_image_name)
        self.create_image(output_var_image_name)

        self.add_input('shading_normal')
        self.add_input('world_coordinate')
        self.add_input('object_id')

        filter = self.create_filter(pyrprimagefilters.IMAGE_FILTER_TEMPORAL_ACCUMULATOR)

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"positionsImg",
                                                       self.rif_images["world_coordinate"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"normalsImg",
                                                       self.rif_images["shading_normal"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"meshIdsImg",
                                                       self.rif_images["object_id"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"outVarianceImg",
                                                       self.rif_images[output_var_image_name])

        self.add_filter_to_queue(filter, input_image, self.rif_images[output_image_name])


    def add_lwr_filter(self, settings, input_image):
        ''' creates a lwr filter ''' 
        self.add_input('world_coordinate')
        self.add_input('shading_normal')
        self.add_input('object_id')
        self.add_input('depth')

        self.add_variance_image_filter(self.input_image, 'color_output', 'color_var')
        self.add_normalized_image_filter(self.rif_images['depth'], 'depth_normalized')
        self.add_variance_image_filter(self.rif_images['depth_normalized'], 'depth_normalized_output', 'depth_normalized_var')
        self.add_variance_image_filter(self.rif_images['shading_normal'], 'shading_normal_output', 'shading_normal_var')
        self.add_variance_image_filter(self.rif_images['object_id'], 'object_id_output', 'object_id_var')
        
        filter = self.create_filter(pyrprimagefilters.IMAGE_FILTER_LWR_DENOISE)
        self.filter_type = pyrprimagefilters.IMAGE_FILTER_LWR_DENOISE

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"vColorImg",
                                                       self.rif_images["color_var"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"normalsImg",
                                                       self.rif_images["shading_normal_output"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"vNormalsImg",
                                                       self.rif_images["shading_normal_var"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"depthImg",
                                                       self.rif_images["depth_normalized_output"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"vDepthImg",
                                                       self.rif_images["depth_normalized_var"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"transImg",
                                                       self.rif_images["object_id_output"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"vTransImg",
                                                       self.rif_images["object_id_var"])

        pyrprimagefilters.ImageFilterSetParameter1u(filter, b"samples", settings.samples)
        pyrprimagefilters.ImageFilterSetParameter1u(filter, b"halfWindow", settings.half_window)
        pyrprimagefilters.ImageFilterSetParameter1f(filter, b"bandwidth", settings.bandwidth)

        self.add_filter_to_queue(filter, input_image, self.rif_images["rif_output_image"])
        self.main_denoiser_filter = filter


    def add_eaw_filter(self, settings, input_image):
        ''' EAW filter needs some sub filters. ''' 
        self.add_input('shading_normal')
        self.add_input('object_id')
        self.add_input('depth')

        self.add_variance_image_filter(self.input_image, 'color_output', 'color_var')
        self.add_normalized_image_filter(self.rif_images['depth'], 'depth_normalized')
        
        filter = self.create_filter(pyrprimagefilters.IMAGE_FILTER_EAW_DENOISE)
        self.filter_type = pyrprimagefilters.IMAGE_FILTER_EAW_DENOISE

        # set input images
        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"normalsImg",
                                                       self.rif_images["shading_normal"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"transImg",
                                                       self.rif_images["object_id"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"colorVar",
                                                       self.rif_images["color_var"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"depthImg",
                                                       self.rif_images["depth_normalized"])

        pyrprimagefilters.ImageFilterSetParameter1f(filter, b"colorSigma", settings.color_sigma)
        pyrprimagefilters.ImageFilterSetParameter1f(filter, b"normalSigma", settings.normal_sigma)
        pyrprimagefilters.ImageFilterSetParameter1f(filter, b"depthSigma", settings.depth_sigma)
        pyrprimagefilters.ImageFilterSetParameter1f(filter, b"transSigma", settings.trans_sigma)

        self.add_filter_to_queue(filter, self.rif_images["color_output"], self.rif_images["rif_output_image"])
        
        self.create_mlaa_filter(self.rif_images['rif_output_image'])
        self.main_denoiser_filter = filter

    
    def create_mlaa_filter(self, input_image):
        ''' mlaa is a post to EAW '''
        self.add_input('shading_normal')
        self.add_input('object_id')
        filter = self.create_filter(pyrprimagefilters.IMAGE_FILTER_MLAA)
        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"normalsImg",
                                                       self.rif_images["shading_normal"])

        pyrprimagefilters.ImageFilterSetParameterImage(filter, b"meshIDImg",
                                                       self.rif_images["object_id"])

        self.add_filter_to_queue(filter, input_image, input_image)


    def add_input(self, input_name):
        self.render_layers.enable_aov(input_name)
        if input_name not in self.rif_images:
            self.rif_images[input_name] = self.get_rif_image_from_rpr_frame_buffer(
                self.render_targets.get_frame_buffer(input_name))

    def get_rif_image_from_rpr_frame_buffer(self, rpr_frame_buffer):
        if not rpr_frame_buffer:
            return None

        width, height = self.render_targets.render_resolution

        # rif image
        rif_image_desc = pyrprimagefilters.ffi.new("rif_image_desc*")
        rif_image_desc.image_width = width
        rif_image_desc.image_height = height
        rif_image_desc.image_depth = 1
        rif_image_desc.num_components = 4
        rif_image_desc.image_row_pitch = 0
        rif_image_desc.image_slice_pitch = 0
        rif_image_desc.type = pyrprimagefilters.COMPONENT_TYPE_FLOAT32

        clmem = pyrpropencl.ffi.new("rpr_cl_mem*")
        pyrpr.FrameBufferGetInfo(rpr_frame_buffer, pyrpropencl.MEM_OBJECT,
                                 sys.getsizeof(clmem), clmem, pyrpropencl.ffi.NULL)

        rif_image = pyrprimagefilters.RifImage()
        pyrprimagefilters.ContextCreateImageFromOpenClMemory(self.render_device.rif_context,
            rif_image_desc, clmem[0], False, rif_image)

        return rif_image

    def update_iterations(self, iterations):
        ''' scale the color sigma by number of iterations, less iterations have more noise '''
        if not self.denoiser_settings.scale_by_iterations:
            return
        if self.denoiser_settings.filter_type == {'eaw', 'bilateral'}:
            filter = self.main_denoiser_filter
            # lower sigma based on number of iterations
            color_sigma = math.pow(self.denoiser_settings.color_sigma, math.log(max(float(iterations), 1.0), 2.0) - 8.0) 
            
            if self.denoiser_settings.filter_type == 'eaw':
                pyrprimagefilters.ImageFilterSetParameter1f(filter, b"colorSigma", color_sigma)
            else:
                self.sigmas[0] = color_sigma
                pyrprimagefilters.ImageFilterSetParameterFloatArray(filter, b"sigmas",
                                                                    self.sigmas, 4)

