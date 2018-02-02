import pyrpr
import pyrprimagefilters
import pyrpropencl
import sys
import numpy as np

from rprblender import logging

class Denoiser:
    def __init__(self, render_layers, render_device, filter_type, core_context):
        self.filter_type = filter_type

        self.render_targets = render_layers.render_targets
        self.render_device = render_device

        self.filters = {}
        self.rif_images = {}

        render_layers.enable_aov('geometric_normal')
        render_layers.enable_aov('world_coordinate')
        render_layers.enable_aov('object_id')
        render_layers.enable_aov('depth')

        #Create input rif image
        desc = pyrpr.ffi.new("rpr_framebuffer_desc*")
        width, height = self.render_targets.render_resolution
        desc.fb_width, desc.fb_height = width, height

        fmt = (4, pyrpr.COMPONENT_TYPE_FLOAT32)
        self.resolved_frame_buffer = pyrpr.FrameBuffer()
        pyrpr.ContextCreateFrameBuffer(core_context, fmt, desc, self.resolved_frame_buffer)
        pyrpr.FrameBufferClear(self.resolved_frame_buffer)

        self.input_rif_image = self.get_rif_image_from_rpr_frame_buffer(
            self.resolved_frame_buffer)

        # Get rif image description
        rif_image_desc = pyrprimagefilters.ffi.new("rif_image_desc*")
        rif_image_size = pyrprimagefilters.ffi.new("size_t*")

        pyrprimagefilters.ImageGetInfo(self.input_rif_image, pyrprimagefilters.IMAGE_DESC,
                                      sys.getsizeof(rif_image_desc), rif_image_desc,
                                      rif_image_size)

        #Create output rif images
        self.rif_images["output_rif_image"] = pyrprimagefilters.RifImage()

        if self.filter_type == pyrprimagefilters.IMAGE_FILTER_BILATERAL_DENOISE:
            self.filters["bilateral_image_filter"] = pyrprimagefilters.RifImageFilter()
            pyrprimagefilters.ContextCreateImageFilter(self.render_device.rif_context,
                                                       pyrprimagefilters.IMAGE_FILTER_BILATERAL_DENOISE,
                                                       self.filters["bilateral_image_filter"])

            pyrprimagefilters.ContextCreateImage(self.render_device.rif_context,
                                                 rif_image_desc, pyrprimagefilters.ffi.NULL,
                                                 self.rif_images["output_rif_image"])

        if self.filter_type == pyrprimagefilters.IMAGE_FILTER_EAW_DENOISE:
            render_layers.enable_aov('depth')
            
            #Create needed filters
            self.filters["variance_image_filter"] = pyrprimagefilters.RifImageFilter()
            pyrprimagefilters.ContextCreateImageFilter(self.render_device.rif_context,
                                                       pyrprimagefilters.IMAGE_FILTER_TEMPORAL_ACCUMULATOR,
                                                       self.filters["variance_image_filter"])

            self.filters["denoise_image_filter"] = pyrprimagefilters.RifImageFilter()
            pyrprimagefilters.ContextCreateImageFilter(self.render_device.rif_context,
                                                       pyrprimagefilters.IMAGE_FILTER_EAW_DENOISE,
                                                       self.filters["denoise_image_filter"])

            self.filters["mlaa_image_filter"] = pyrprimagefilters.RifImageFilter()
            pyrprimagefilters.ContextCreateImageFilter(self.render_device.rif_context,
                                                       pyrprimagefilters.IMAGE_FILTER_MLAA,
                                                       self.filters["mlaa_image_filter"])

            #Create needed rif images
            self.rif_images["variance_output_image"] = pyrprimagefilters.RifImage()
            self.rif_images["denoise_output_image"] = pyrprimagefilters.RifImage()
            self.rif_images["normalized_depth_rif_image"] = pyrprimagefilters.RifImage()

            for key in self.rif_images:
                pyrprimagefilters.ContextCreateImage(self.render_device.rif_context,
                                                     rif_image_desc, pyrprimagefilters.ffi.NULL,
                                                     self.rif_images[key])

        if self.filter_type == pyrprimagefilters.IMAGE_FILTER_LWR_DENOISE:
            render_layers.enable_aov('depth')

            #Create needed filters
            self.filters["variance_image_filter"] = pyrprimagefilters.RifImageFilter()
            self.filters["normal_var_image_filter"] = pyrprimagefilters.RifImageFilter()
            self.filters["depth_var_image_filter"] = pyrprimagefilters.RifImageFilter()
            self.filters["object_id_var_image_filter"] = pyrprimagefilters.RifImageFilter()
            self.filters["normalized_depth_filter"] = pyrprimagefilters.RifImageFilter()

            for key in self.filters:
                pyrprimagefilters.ContextCreateImageFilter(self.render_device.rif_context, 
                                                           pyrprimagefilters.IMAGE_FILTER_TEMPORAL_ACCUMULATOR,
                                                           self.filters[key])

            self.filters["denoise_image_filter"] = pyrprimagefilters.RifImageFilter()
            pyrprimagefilters.ContextCreateImageFilter(self.render_device.rif_context, 
                                                           pyrprimagefilters.IMAGE_FILTER_LWR_DENOISE,
                                                           self.filters["denoise_image_filter"])

            #Create needed rif images
            self.rif_images["variance_output_image"] = pyrprimagefilters.RifImage()
            self.rif_images["color_output_image"] = pyrprimagefilters.RifImage()
            self.rif_images["normal_var_output_image"] = pyrprimagefilters.RifImage()
            self.rif_images["normal_output_image"] = pyrprimagefilters.RifImage()
            self.rif_images["depth_var_output_image"] = pyrprimagefilters.RifImage()
            self.rif_images["object_id_var_output_image"] = pyrprimagefilters.RifImage()
            self.rif_images["object_id_output_image"] = pyrprimagefilters.RifImage()
            self.rif_images["normalized_depth_rif_image"] = pyrprimagefilters.RifImage()

            for key in self.rif_images:
                pyrprimagefilters.ContextCreateImage(self.render_device.rif_context,
                                                     rif_image_desc, pyrprimagefilters.ffi.NULL,
                                                     self.rif_images[key])

    def __del__(self):
        pyrprimagefilters.ObjectDelete(self.input_rif_image._get_handle())

        for key in self.filters:
            pyrprimagefilters.CommandQueueDetachImageFilter(self.render_device.rif_command_queue,
                                                                self.filters[key])
            pyrprimagefilters.ObjectDelete(self.filters[key]._get_handle())

        for key in self.rif_images:
            pyrprimagefilters.ObjectDelete(self.rif_images[key]._get_handle())

    def execute(self, frame_buffer):
        pyrpr.ContextResolveFrameBuffer(self.render_device.core_context, frame_buffer, self.resolved_frame_buffer)

        pyrprimagefilters.ContextExecuteCommandQueue(self.render_device.rif_context, self.render_device.rif_command_queue,
                                                pyrprimagefilters.ffi.NULL, pyrprimagefilters.ffi.NULL)

        # Store results in float array to form final image
        mapped_data = pyrprimagefilters.ffi.new("void**")
        rif_result = pyrprimagefilters.ImageMap(self.rif_images["output_rif_image"], pyrprimagefilters.IMAGE_MAP_READ, mapped_data)
        assert rif_result == pyrprimagefilters.SUCCESS

        width, height = self.render_targets.render_resolution

        float_data = pyrprimagefilters.ffi.cast("float*", mapped_data[0])

        buffer_size = width*height*4*4
        float_out_buffer = pyrprimagefilters.ffi.buffer(float_data, buffer_size)

        output = np.frombuffer(float_out_buffer, dtype=np.float32).reshape(height, width, 4)

        rif_result = pyrprimagefilters.ImageUnmap(self.rif_images["output_rif_image"], mapped_data[0])
        assert rif_result == pyrprimagefilters.SUCCESS

        return output

    def create_normalized_filter(self, input_rif_image, output_rif_image):
        pyrprimagefilters.CommandQueueAttachImageFilter(self.render_device.rif_command_queue,
                                                        self.filters["normalized_depth_filter"], input_rif_image, output_rif_image)

    def configure_bilateral_filter(self, radius, inputs_num):
        self.input_rif_array = pyrprimagefilters.ArrayObject("rif_image[]", [self.input_rif_image._handle_ptr[0],
                                                             self.rif_images["geometric_normal"]._handle_ptr[0],
                                                             self.rif_images["world_coordinate"]._handle_ptr[0],
                                                             self.rif_images["object_id"]._handle_ptr[0]])

        pyrprimagefilters.ImageFilterSetParameterImageArray(self.filters["bilateral_image_filter"], b"inputs",
                                                            self.input_rif_array, inputs_num)

        self.sigmas = pyrprimagefilters.ffi.new("float[]", [.1, .1, .1, .1])
        pyrprimagefilters.ImageFilterSetParameterFloatArray(self.filters["bilateral_image_filter"], b"sigmas",
                                                            self.sigmas, inputs_num)

        pyrprimagefilters.ImageFilterSetParameter1u(self.filters["bilateral_image_filter"], b"radius",
                                                    radius)

        pyrprimagefilters.ImageFilterSetParameter1u(self.filters["bilateral_image_filter"], b"inputsNum", inputs_num)

    def create_bilateral_filter(self):
        pyrprimagefilters.CommandQueueAttachImageFilter(self.render_device.rif_command_queue,
                                                        self.filters["bilateral_image_filter"], self.input_rif_image,
                                                        self.rif_images["output_rif_image"])

    def create_variance_image_filter(self, input_filter, input_rif_image, output_rif_image):
        pyrprimagefilters.ImageFilterSetParameterImage(input_filter, b"positionsImg",
                                                       self.rif_images["world_coordinate"])

        pyrprimagefilters.ImageFilterSetParameterImage(input_filter, b"normalsImg",
                                                       self.rif_images["geometric_normal"])

        pyrprimagefilters.ImageFilterSetParameterImage(input_filter, b"meshIdsImg",
                                                       self.rif_images["object_id"])

        pyrprimagefilters.ImageFilterSetParameterImage(input_filter, b"outVarianceImg",
                                                       self.rif_images["variance_output_image"])


        pyrprimagefilters.CommandQueueAttachImageFilter(self.render_device.rif_command_queue,
                                                        input_filter, input_rif_image,
                                                        output_rif_image)

    def create_lwr_image_filter(self):
        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["denoise_image_filter"], b"vColorImg",
                                                       self.rif_images["variance_output_image"])

        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["denoise_image_filter"], b"normalsImg",
                                                       self.rif_images["normal_output_image"])

        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["denoise_image_filter"], b"vNormalsImg",
                                                       self.rif_images["normal_var_output_image"])

        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["denoise_image_filter"], b"depthImg",
                                                       self.rif_images["normalized_depth_rif_image"])

        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["denoise_image_filter"], b"vDepthImg",
                                                       self.rif_images["normalized_depth_rif_image"])

        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["denoise_image_filter"], b"transImg",
                                                       self.rif_images["object_id_output_image"])

        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["denoise_image_filter"], b"vTransImg",
                                                       self.rif_images["object_id_var_output_image"])

        pyrprimagefilters.CommandQueueAttachImageFilter(self.render_device.rif_command_queue,
                                                        self.filters["denoise_image_filter"], self.rif_images["color_output_image"],
                                                        self.rif_images["output_rif_image"])

    def configure_lwr_image_filter(self, samples, halfWindow, bandwidth):
        pyrprimagefilters.ImageFilterSetParameter1u(self.filters["denoise_image_filter"], b"samples", samples)
        pyrprimagefilters.ImageFilterSetParameter1u(self.filters["denoise_image_filter"], b"halfWindow", halfWindow)
        pyrprimagefilters.ImageFilterSetParameter1f(self.filters["denoise_image_filter"], b"bandwidth", bandwidth)

    def create_eaw_filter(self):
        pyrprimagefilters.ContextCreateImageFilter(self.render_device.rif_context,
                                                   pyrprimagefilters.IMAGE_FILTER_EAW_DENOISE,
                                                   self.filters["denoise_image_filter"])

        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["denoise_image_filter"], b"normalsImg",
                                                       self.rif_images["geometric_normal"])

        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["denoise_image_filter"], b"transImg",
                                                       self.rif_images["object_id"])

        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["denoise_image_filter"], b"colorVar",
                                                       self.input_rif_image)

        pyrprimagefilters.CommandQueueAttachImageFilter(self.render_device.rif_command_queue,
                                                        self.filters["denoise_image_filter"], self.rif_images["output_rif_image"],
                                                        self.rif_images["denoise_output_image"])

    def configure_eaw_filter(self, color_sigma, normal_sigma, depth_sigma, trans_sigma):
        pyrprimagefilters.ImageFilterSetParameter1f(self.filters["denoise_image_filter"], b"colorSigma",
                                                    color_sigma)

        pyrprimagefilters.ImageFilterSetParameter1f(self.filters["denoise_image_filter"], b"normalSigma",
                                                    normal_sigma)

        pyrprimagefilters.ImageFilterSetParameter1f(self.filters["denoise_image_filter"], b"depthSigma",
                                                    depth_sigma)

        pyrprimagefilters.ImageFilterSetParameter1f(self.filters["denoise_image_filter"], b"transSigma",
                                                    trans_sigma)

    def create_mlaa_filter(self):
        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["mlaa_image_filter"], b"normalsImg",
                                                       self.rif_images["geometric_normal"])

        pyrprimagefilters.ImageFilterSetParameterImage(self.filters["mlaa_image_filter"], b"meshIDImg",
                                                       self.rif_images["object_id"])

        pyrprimagefilters.CommandQueueAttachImageFilter(self.render_device.rif_command_queue,
                                                        self.filters["mlaa_image_filter"], self.rif_images["denoise_output_image"],
                                                        self.rif_images["output_rif_image"])

    def add_input(self, input_name):
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