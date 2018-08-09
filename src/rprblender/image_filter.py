import pyrpr
import pyrpropencl
import pyrprimagefilters as rif
import sys
import numpy as np


class ImageFilterError(RuntimeError):
    pass


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


class RifContextWrapper():
    def __init__(self):
        self._rif_context = rif.RifContext()
        self._rif_command_queue = rif.RifCommandQueue()
        self._rif_output_image = rif.RifImage()

    def __del__(self):
        self._rif_output_image.delete()
        self._rif_command_queue.delete()
        self._rif_context.delete()


    def _get_rpr_cache_path(rpr_context):
        size = pyrpr.ffi.new('size_t *', 0)
        pyrpr.ContextGetInfo(rpr_context, pyrpr.CONTEXT_CACHE_PATH, 0, pyrpr.ffi.NULL, size)

        path = pyrpr.ffi.new('char[]', size[0])
        pyrpr.ContextGetInfo(rpr_context, pyrpr.CONTEXT_CACHE_PATH, size[0], path, pyrpr.ffi.NULL)
        return pyrpr.ffi.string(path)


    def _check_devices(backend_api_type, processor_type):
        deviceCount = rif.ffi.new('rif_int *', 0)
        rif.GetDeviceCount(backend_api_type, processor_type, deviceCount)

        if deviceCount[0] == 0:
            raise ImageFilterError("RPR denoiser hasn't found compatible devices")


    def context(self):
        return self._rif_context


    def queue(self):
        return self._rif_command_queue


    def output(self):
        return self._rif_output_image


    def create_output(self, rif_image_desc):
        rif.ContextCreateImage(self._rif_context, rif_image_desc, rif.ffi.NULL, self._rif_output_image)


    def create_rif_image(self, rpr_framebuffer, rif_image_desc):
        raise NotImplementedError()


    def update_inputs(self, rif_filter):
        raise NotImplementedError()


class RifContextGPU(RifContextWrapper):
    def __init__(self, rpr_context):
        super(RifContextGPU, self).__init__()
        RifContextWrapper._check_devices(rif.BACKEND_API_OPENCL, rif.PROCESSOR_GPU)

        cl_context = pyrpropencl.ffi.new('rpr_cl_context *')
        pyrpr.ContextGetInfo(rpr_context, pyrpropencl.CONTEXT, sys.getsizeof(cl_context), cl_context, pyrpropencl.ffi.NULL)

        cl_device = pyrpropencl.ffi.new('rpr_cl_device *')
        pyrpr.ContextGetInfo(rpr_context, pyrpropencl.DEVICE,  sys.getsizeof(cl_device), cl_device, pyrpropencl.ffi.NULL)

        cl_command_queue = pyrpropencl.ffi.new('rpr_cl_command_queue *')
        pyrpr.ContextGetInfo(rpr_context, pyrpropencl.COMMAND_QUEUE,  sys.getsizeof(cl_command_queue), cl_command_queue, pyrpropencl.ffi.NULL)

        path = RifContextWrapper._get_rpr_cache_path(rpr_context)
        rif.CreateContextFromOpenClContext(rif.API_VERSION, cl_context[0], cl_device[0], cl_command_queue[0], path, self._rif_context)

        rif.ContextCreateCommandQueue(self._rif_context, self._rif_command_queue)


    def create_rif_image(self, rpr_framebuffer, rif_image_desc):
        cl_mem = pyrpropencl.ffi.new('rpr_cl_mem *')
        pyrpr.FrameBufferGetInfo(rpr_framebuffer, pyrpropencl.MEM_OBJECT, sys.getsizeof(cl_mem), cl_mem, pyrpropencl.ffi.NULL)

        rif_image = rif.RifImage()
        rif.ContextCreateImageFromOpenClMemory(self._rif_context, rif_image_desc, cl_mem[0], False, rif_image)

        return rif_image

    
    def update_inputs(self, rif_filter):
        # image filter processes buffers directly in GPU mode
        pass


class RifContextCPU(RifContextWrapper):
    def __init__(self, rpr_context):
        super(RifContextCPU, self).__init__()
        RifContextWrapper._check_devices(rif.BACKEND_API_OPENCL, rif.PROCESSOR_CPU)

        path = RifContextWrapper._get_rpr_cache_path(rpr_context)
        rif.CreateContext(rif.API_VERSION, rif.BACKEND_API_OPENCL, rif.PROCESSOR_CPU, 0, path, self._rif_context)

        rif.ContextCreateCommandQueue(self._rif_context, self._rif_command_queue)


    def create_rif_image(self, rpr_framebuffer, rif_image_desc):
        rif_image = rif.RifImage()
        rif.ContextCreateImage(self._rif_context, rif_image_desc, rif.ffi.NULL, rif_image)

        return rif_image

    
    def update_inputs(self, rif_filter):
        for input_data in rif_filter.inputs().values():
            size_in_bytes = rif.ffi.new('size_t *', 0)
            ret_size = rif.ffi.new('size_t *', 0)
            rif.ImageGetInfo(input_data.rif_image, rif.IMAGE_DATA_SIZEBYTE, sys.getsizeof(size_in_bytes), rif.ffi.cast('void *', size_in_bytes), ret_size)

            fb_size = pyrpr.ffi.new('size_t *', 0)
            pyrpr.FrameBufferGetInfo(input_data.rpr_framebuffer, pyrpr.FRAMEBUFFER_DATA, 0, pyrpr.ffi.NULL, fb_size)

            if size_in_bytes[0] != fb_size[0]:
                raise ImageFilterError("RPR denoiser failed to match RIF image and frame buffer sizes")

            # resolve framebuffer data to rif_image
            image_data = rif.ffi.new('void **')
            rif.ImageMap(input_data.rif_image, rif.IMAGE_MAP_WRITE, image_data)
            pyrpr.FrameBufferGetInfo(input_data.rpr_framebuffer, pyrpr.FRAMEBUFFER_DATA, fb_size[0], image_data[0], pyrpr.ffi.NULL)
            rif.ImageUnmap(input_data.rif_image, image_data[0])


class RifContextGPUMetal(RifContextWrapper):
    def __init__(self, rpr_context):
        super(RifContextGPUMetal, self).__init__()
        RifContextWrapper._check_devices(rif.BACKEND_API_METAL, rif.PROCESSOR_GPU)

        path = RifContextWrapper._get_rpr_cache_path(rpr_context)
        rif.CreateContext(rif.API_VERSION, rif.BACKEND_API_METAL, rif.PROCESSOR_GPU, 0, path, self._rif_context)

        rif.ContextCreateCommandQueue(self._rif_context, self._rif_command_queue)


    def create_rif_image(self, rpr_framebuffer, rif_image_desc):
        cl_mem = pyrpropencl.ffi.new('rpr_cl_mem *')
        pyrpr.FrameBufferGetInfo(rpr_framebuffer, pyrpropencl.MEM_OBJECT, sys.getsizeof(cl_mem), cl_mem, pyrpropencl.ffi.NULL)

        rif_image = rif.RifImage()
        rif.ContextCreateImageFromOpenClMemory(self._rif_context, rif_image_desc, cl_mem[0], False, rif_image)

        return rif_image

    
    def update_inputs(self, rif_filter):
        # image filter processes buffers directly in METAL mode
        pass


class RifFilterWrapper():
    class _InputTraits():
        def __init__(self, rif_image, rpr_framebuffer, sigma):
            self.rif_image = rif_image
            self.rpr_framebuffer = rpr_framebuffer
            self.sigma = sigma


    def __init__(self, rif_context: RifContextWrapper):
        self._rif_context = rif_context
        self._rif_image_filter = rif.RifImageFilter()
        self._aux_filters = []
        self._aux_images = []
        self._inputs = {}
        self._params = {}

    def __del__(self):
        for input in self._inputs.values():
            input.rif_image.delete()

        for aux_image in self._aux_images:
            aux_image.delete()

        for aux_filter in self._aux_filters:
            aux_filter.delete()

        self._rif_image_filter.delete()


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
            rif.CommandQueueDetachImageFilter(self._rif_context.queue(), filter)

        rif.CommandQueueDetachImageFilter(self._rif_context.queue(), self._rif_image_filter)


    def apply_parameters(self):
        for name, param in self._params.items():
            if type(param) == int:
                rif.ImageFilterSetParameter1u(self._rif_image_filter, name.encode('latin1'), param)
            elif type(param) == float:
                rif.ImageFilterSetParameter1f(self._rif_image_filter, name.encode('latin1'), param)
            else:
                raise ImageFilterError("Not supported param type with name=%s" % name)


    def _setup_variance_image_filter(self, input_filter, out_variance_image):
        rif.ImageFilterSetParameterImage(input_filter, b'positionsImg', self._inputs[RifFilterInput.WorldCoordinate].rif_image)
        rif.ImageFilterSetParameterImage(input_filter, b'normalsImg', self._inputs[RifFilterInput.Normal].rif_image)
        rif.ImageFilterSetParameterImage(input_filter, b'meshIdsImg', self._inputs[RifFilterInput.ObjectId].rif_image)
        rif.ImageFilterSetParameterImage(input_filter, b'outVarianceImg', out_variance_image)


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

        rif.ContextCreateImageFilter(self._rif_context.context(), rif.IMAGE_FILTER_BILATERAL_DENOISE, self._rif_image_filter)


    def attach_filter(self):
        input_images = []
        sigmas = []
        for input in self._inputs.values():
            input_images.append(input.rif_image._get_handle())
            sigmas.append(input.sigma)

        self._input_images = rif.ArrayObject('rif_image[]', input_images)
        rif.ImageFilterSetParameterImageArray(self._rif_image_filter, b'inputs', self._input_images, len(input_images))

        self._sigmas = rif.ffi.new('float[]', sigmas)
        rif.ImageFilterSetParameterFloatArray(self._rif_image_filter, b'sigmas', self._sigmas, len(sigmas))

        rif.ImageFilterSetParameter1u(self._rif_image_filter, b'inputsNum', len(input_images))

        rif.CommandQueueAttachImageFilter(self._rif_context.queue(), self._rif_image_filter, self._inputs[RifFilterInput.Color].rif_image, self._rif_context.output())


class RifFilterLwr(RifFilterWrapper):
    class _AuxInput:
        Color = 0
        Normal = 1
        Depth = 2
        Trans = 3
        AuxInputMax = 4

    def __init__(self, rif_context, width, height):
        super(RifFilterLwr, self).__init__(rif_context)

        rif.ContextCreateImageFilter(self._rif_context.context(), rif.IMAGE_FILTER_LWR_DENOISE, self._rif_image_filter)

        desc = RifFilterWrapper.create_rif_image_descr(width, height)

        for i in range(RifFilterLwr._AuxInput.AuxInputMax):
            aux_filter = rif.RifImageFilter()
            rif.ContextCreateImageFilter(self._rif_context.context(), rif.IMAGE_FILTER_TEMPORAL_ACCUMULATOR, aux_filter)
            self._aux_filters.append(aux_filter)

            aux_image = rif.RifImage()
            rif.ContextCreateImage(self._rif_context.context(), desc, rif.ffi.NULL, aux_image)
            self._aux_images.append(aux_image)


    def attach_filter(self):
        # make variance image filters
        for i in range(len(self._aux_filters)):
            self._setup_variance_image_filter(self._aux_filters[i], self._aux_images[i])

        # configure Filter
        rif.ImageFilterSetParameterImage(self._rif_image_filter, b'vColorImg', self._aux_images[RifFilterLwr._AuxInput.Color])
        
        rif.ImageFilterSetParameterImage(self._rif_image_filter, b'normalsImg', self._inputs[RifFilterInput.Normal].rif_image)
        rif.ImageFilterSetParameterImage(self._rif_image_filter, b'vNormalsImg', self._aux_images[RifFilterLwr._AuxInput.Normal])

        rif.ImageFilterSetParameterImage(self._rif_image_filter, b'depthImg', self._inputs[RifFilterInput.Depth].rif_image)
        rif.ImageFilterSetParameterImage(self._rif_image_filter, b'vDepthImg', self._aux_images[RifFilterLwr._AuxInput.Depth])

        rif.ImageFilterSetParameterImage(self._rif_image_filter, b'transImg', self._inputs[RifFilterInput.Trans].rif_image)
        rif.ImageFilterSetParameterImage(self._rif_image_filter, b'vTransImg', self._aux_images[RifFilterLwr._AuxInput.Trans])

        # attach filters
        rif.CommandQueueAttachImageFilter(self._rif_context.queue(), self._aux_filters[RifFilterLwr._AuxInput.Trans], 
                                          self._inputs[RifFilterInput.Trans].rif_image, self._aux_images[RifFilterLwr._AuxInput.Trans])
        rif.CommandQueueAttachImageFilter(self._rif_context.queue(), self._aux_filters[RifFilterLwr._AuxInput.Depth], 
                                          self._inputs[RifFilterInput.Depth].rif_image, self._aux_images[RifFilterLwr._AuxInput.Depth])
        rif.CommandQueueAttachImageFilter(self._rif_context.queue(), self._aux_filters[RifFilterLwr._AuxInput.Normal], 
                                          self._inputs[RifFilterInput.Normal].rif_image, self._aux_images[RifFilterLwr._AuxInput.Normal])
        rif.CommandQueueAttachImageFilter(self._rif_context.queue(), self._aux_filters[RifFilterLwr._AuxInput.Color], 
                                          self._inputs[RifFilterInput.Color].rif_image, self._aux_images[RifFilterLwr._AuxInput.Color])

        rif.CommandQueueAttachImageFilter(self._rif_context.queue(), self._rif_image_filter, self._inputs[RifFilterInput.Color].rif_image, self._rif_context.output())


class RifFilterEaw(RifFilterWrapper):
    class _AuxInput:
        Color = 0
        Mlaa = 1
        AuxInputMax = 2

    def __init__(self, rif_context, width, height):
        super(RifFilterEaw, self).__init__(rif_context)

        rif.ContextCreateImageFilter(self._rif_context.context(), rif.IMAGE_FILTER_EAW_DENOISE, self._rif_image_filter)

        desc = RifFilterWrapper.create_rif_image_descr(width, height)

        for i in range(RifFilterEaw._AuxInput.AuxInputMax):
            aux_filter = rif.RifImageFilter()
            if i == RifFilterEaw._AuxInput.Color:
                rif.ContextCreateImageFilter(self._rif_context.context(), rif.IMAGE_FILTER_TEMPORAL_ACCUMULATOR, aux_filter)
            else:
                rif.ContextCreateImageFilter(self._rif_context.context(), rif.IMAGE_FILTER_MLAA, aux_filter)

            self._aux_filters.append(aux_filter)

            aux_image = rif.RifImage()
            rif.ContextCreateImage(self._rif_context.context(), desc, rif.ffi.NULL, aux_image)
            self._aux_images.append(aux_image)


    def attach_filter(self):
        # setup inputs
        rif.ImageFilterSetParameterImage(self._rif_image_filter, b'normalsImg', self._inputs[RifFilterInput.Normal].rif_image)
        rif.ImageFilterSetParameterImage(self._rif_image_filter, b'transImg', self._inputs[RifFilterInput.Trans].rif_image)
        rif.ImageFilterSetParameterImage(self._rif_image_filter, b'depthImg', self._inputs[RifFilterInput.Depth].rif_image)
        rif.ImageFilterSetParameterImage(self._rif_image_filter, b'colorVar', self._inputs[RifFilterInput.Color].rif_image)

        # setup sigmas
        rif.ImageFilterSetParameter1f(self._rif_image_filter, b'colorSigma', self._inputs[RifFilterInput.Color].sigma)
        rif.ImageFilterSetParameter1f(self._rif_image_filter, b'normalSigma', self._inputs[RifFilterInput.Normal].sigma)
        rif.ImageFilterSetParameter1f(self._rif_image_filter, b'depthSigma', self._inputs[RifFilterInput.Depth].sigma)
        rif.ImageFilterSetParameter1f(self._rif_image_filter, b'transSigma', self._inputs[RifFilterInput.Trans].sigma)

        # setup color variance filter
        self._setup_variance_image_filter(self._aux_filters[RifFilterEaw._AuxInput.Color], self._aux_images[RifFilterEaw._AuxInput.Color])

        # setup MLAA filter
        rif.ImageFilterSetParameterImage(self._aux_filters[RifFilterEaw._AuxInput.Mlaa], b'normalsImg', self._inputs[RifFilterInput.Normal].rif_image)
        rif.ImageFilterSetParameterImage(self._aux_filters[RifFilterEaw._AuxInput.Mlaa], b'meshIDImg', self._inputs[RifFilterInput.ObjectId].rif_image)
        rif.ImageFilterSetParameterImage(self._aux_filters[RifFilterEaw._AuxInput.Mlaa], b'depthImg', self._inputs[RifFilterInput.Depth].rif_image)

        # attach filters
        rif.CommandQueueAttachImageFilter(self._rif_context.queue(), self._aux_filters[RifFilterEaw._AuxInput.Color], 
                                          self._inputs[RifFilterInput.Color].rif_image, self._rif_context.output())
        rif.CommandQueueAttachImageFilter(self._rif_context.queue(), self._rif_image_filter, 
                                          self._rif_context.output(), self._aux_images[RifFilterEaw._AuxInput.Mlaa])
        rif.CommandQueueAttachImageFilter(self._rif_context.queue(), self._aux_filters[RifFilterEaw._AuxInput.Mlaa], 
                                          self._aux_images[RifFilterEaw._AuxInput.Mlaa], self._rif_context.output())



class ImageFilter():
    def __init__(self, rpr_context, rif_filter_type: RifFilterType, width, height):
        def is_gpu_enabled(creation_flags):
            gpu_flags = [pyrpr.CREATION_FLAGS_ENABLE_GPU0,
                         pyrpr.CREATION_FLAGS_ENABLE_GPU1,
                         pyrpr.CREATION_FLAGS_ENABLE_GPU2,
                         pyrpr.CREATION_FLAGS_ENABLE_GPU3,
                         pyrpr.CREATION_FLAGS_ENABLE_GPU4,
                         pyrpr.CREATION_FLAGS_ENABLE_GPU5,
                         pyrpr.CREATION_FLAGS_ENABLE_GPU6,
                         pyrpr.CREATION_FLAGS_ENABLE_GPU7]

            for flag in gpu_flags:
                if creation_flags & flag:
                    return True

            return False

        self._rpr_context = rpr_context
        self._width = width
        self._height = height
        self._resolved_framebuffer = None

        creation_flags = pyrpr.ffi.new("rpr_creation_flags*", 0)
        pyrpr.ContextGetInfo(rpr_context, pyrpr.CONTEXT_CREATION_FLAGS, sys.getsizeof(creation_flags), creation_flags, pyrpr.ffi.NULL)

        if creation_flags[0] & pyrpr.CREATION_FLAGS_ENABLE_METAL:
            self._rif_context = RifContextGPUMetal(self._rpr_context)
        elif is_gpu_enabled(creation_flags[0]):
            self._rif_context = RifContextGPU(self._rpr_context)
        elif creation_flags[0] & pyrpr.CREATION_FLAGS_ENABLE_CPU:
            self._rif_context = RifContextCPU(self._rpr_context)
        else:
            raise ImageFilterError("Not supported CONTEXT_CREATION_FLAGS")

        desc = RifFilterWrapper.create_rif_image_descr(self._width, self._height)
        self._rif_context.create_output(desc)

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
        desc = RifFilterWrapper.create_rif_image_descr(self._width, self._height)
        rif_image = self._rif_context.create_rif_image(rpr_framebuffer, desc)
        self._rif_filter.add_input(input_id, rif_image, rpr_framebuffer, sigma)


    def add_param(self, name, param):
        self._rif_filter.add_param(name, param)

    
    def attach_filter(self):
        self._rif_filter.attach_filter()
        self._rif_filter.apply_parameters()


    def run(self):
        self._rif_context.update_inputs(self._rif_filter)
        rif.ContextExecuteCommandQueue(self._rif_context.context(), self._rif_context.queue(), rif.ffi.NULL, rif.ffi.NULL, rif.ffi.NULL)


    def get_data(self):
        mapped_data = rif.ffi.new('void **')
        rif.ImageMap(self._rif_context.output(), rif.IMAGE_MAP_READ, mapped_data)

        float_data = rif.ffi.cast("float*", mapped_data[0])
        buffer_size = self._width*self._height*4*4    # 4*4 is the size in bytes of pixel as RGBA color as 4 floats (every color component is float value)
        output = np.frombuffer(rif.ffi.buffer(float_data, buffer_size), dtype=np.float32).reshape(self._height, self._width, 4)

        rif.ImageUnmap(self._rif_context.output(), mapped_data[0])

        return output

    def resolved_framebuffer(self):
        if not self._resolved_framebuffer:
            self._resolved_framebuffer = pyrpr.FrameBuffer()
            desc = pyrpr.ffi.new("rpr_framebuffer_desc*")
            desc.fb_width, desc.fb_height = self._width, self._height
            pyrpr.ContextCreateFrameBuffer(self._rpr_context, (4, pyrpr.COMPONENT_TYPE_FLOAT32), desc, self._resolved_framebuffer)
            pyrpr.FrameBufferClear(self._resolved_framebuffer)

        return self._resolved_framebuffer
