import platform
import traceback
import os
from abc import ABCMeta, abstractmethod
import numpy as np

import pyrprimagefilterswrap
from pyrprimagefilterswrap import *

import pyrpr

import bgl

lib_wrapped_log_calls = False


class _init_data:
    _log_fun = None


def init(log_fun, rprsdk_bin_path):
    _module = __import__(__name__)

    _init_data._log_fun = log_fun

    lib_platform = ""
    rel_path = "../../../RadeonProImageProcessing"
    if platform.system() == "Windows":
        lib_name = 'RadeonImageFilters64.dll'
        lib_platform = "Win/lib"
    elif platform.system() == "Linux":
        lib_name = 'libRadeonImageFilters64.so'
        lib_platform = "Linux/Ubuntu/lib64"
    elif platform.system() == "Darwin":
        lib_name = 'libRadeonImageFilters64.dylib'
        lib_platform = "Mac/lib"
    else:
        assert False

    import __imagefilters

    try:
        lib = __imagefilters.lib
    except AttributeError:
        lib_path = str(rprsdk_bin_path / lib_name )
        if not os.path.isfile(lib_path):
            lib_path = str(rprsdk_bin_path / rel_path / lib_platform / lib_name ) 
        lib = __imagefilters.ffi.dlopen(lib_path)

    pyrprimagefilterswrap.lib = lib
    pyrprimagefilterswrap.ffi = __imagefilters.ffi
    global ffi
    ffi = __imagefilters.ffi

    for name in pyrprimagefilterswrap._constants_names:
        setattr(_module, name, getattr(pyrprimagefilterswrap, name))

    for name in pyrprimagefilterswrap._functions_names:

        wrapped = getattr(pyrprimagefilterswrap, name)

        if lib_wrapped_log_calls:
            wrapped = pyrpr.wrap_core_log_call(wrapped, log_fun, 'RIF')
        wrapped = pyrpr.wrap_core_check_success(wrapped, 'RIF')
        setattr(_module, name, wrapped)
    del _module


class Object:
    core_type_name = 'void*'

    def __init__(self, core_type_name=None):
        self.ffi_type_name = (core_type_name if core_type_name is not None else self.core_type_name) + '*'
        self._reset_handle()

    def __del__(self):
        try:
            self.delete()
        except:
            _init_data._log_fun('EXCEPTION:', traceback.format_exc())

    def delete(self):
        if self._handle_ptr and self._get_handle():
            if lib_wrapped_log_calls:
                assert _init_data._log_fun
                _init_data._log_fun('delete: ', self)
            ObjectDelete(self._get_handle())
            self._reset_handle()
            

    def _reset_handle(self):
        self._handle_ptr = ffi.new(self.ffi_type_name, ffi.NULL)

    def _get_handle(self):
        return self._handle_ptr[0]


class ArrayObject:
    def __init__(self, core_type_name, init_data):
        self._handle_ptr = ffi.new(core_type_name, init_data)


def get_device_count(backend_api_type):
    device_count = ffi.new('rif_int *', 0)
    GetDeviceCount(backend_api_type, device_count)
    return device_count[0]

        
class Context(Object, metaclass=ABCMeta):
    core_type_name = 'rif_context'

    def __init__(self, rpr_context):
        super().__init__()
        if not self._check_devices():
            raise RuntimeError("No compatible devices to create image filter")
        self._create(rpr_context)

    @abstractmethod
    def _check_devices(self):
        pass

    @abstractmethod
    def _create(self, rpr_context):
        pass

    def create_image(self, width, height, components=4):
        return Image(self, width, height, components)

    def create_frame_buffer_image(self, frame_buffer):
        return FrameBufferImage(self, frame_buffer)

    def create_frame_buffer_image_gl(self, frame_buffer):
        return FrameBufferImageGL(self, frame_buffer)

    def create_command_queue(self):
        return CommandQueue(self)

    def create_filter(self, filter_type):
        return ImageFilter(self, filter_type)

        
class ContextCPU(Context):
    def _create(self, rpr_context):
        cache_path = rpr_context.get_info_str(pyrpr.CONTEXT_CACHE_PATH)
        CreateContext(API_VERSION, BACKEND_API_OPENCL, pyrpr.CREATION_FLAGS_ENABLE_CPU, pyrpr.encode(cache_path), self)

    def _check_devices(self):
        return get_device_count(BACKEND_API_OPENCL) > 0


class ContextGPU(Context):
    def _create(self, rpr_context):
        cl_context = rpr_context.get_cl_context()
        cl_device = rpr_context.get_cl_device()
        cl_command_queue = rpr_context.get_cl_command_queue()
        cache_path = rpr_context.get_info_str(pyrpr.CONTEXT_CACHE_PATH)

        CreateContextFromOpenClContext(API_VERSION, cl_context, cl_device, cl_command_queue, pyrpr.encode(cache_path), self)

    def create_frame_buffer_image(self, frame_buffer):
        return FrameBufferImageCL(self, frame_buffer)

    def _check_devices(self):
        return get_device_count(BACKEND_API_OPENCL) > 0


class ContextMetal(Context):
    def _create(self, rpr_context):
        cache_path = rpr_context.get_info_str(pyrpr.CONTEXT_CACHE_PATH)
        metal_device = pyrpr.get_first_gpu_id_used(rpr_context.get_creation_flags())
        CreateContext(API_VERSION, BACKEND_API_METAL, metal_device, pyrpr.encode(cache_path), self)

    def create_frame_buffer_image(self, frame_buffer):
        return FrameBufferImageMetal(self, frame_buffer)

    def _check_devices(self):
        return get_device_count(BACKEND_API_METAL) > 0


class Image(Object):
    core_type_name = 'rif_image'

    def __init__(self, context, width, height, components=4):
        super().__init__()
        self.context = context
        self.width = width
        self.height = height
        self.components = components

        self._create()

    def _get_desc(self):
        desc = ffi.new('rif_image_desc *')
        desc.image_width =  self.width
        desc.image_height =  self.height
        desc.image_depth = 1
        desc.num_components = self.components
        desc.image_row_pitch = 0
        desc.image_slice_pitch = 0
        desc.type = COMPONENT_TYPE_FLOAT32
        return desc

    def _create(self):
        ContextCreateImage(self.context, self._get_desc(), ffi.NULL, self)

    def get_data(self):
        mapped_data = ffi.new('void **')
        ImageMap(self, IMAGE_MAP_READ, mapped_data)

        float_data = ffi.cast("float*", mapped_data[0])
        buffer_size = self.width * self.height * self.components * 4    # 4 floats per color components (every color component is float value)
        data = np.frombuffer(ffi.buffer(float_data, buffer_size), dtype=np.float32)\
            .reshape(self.height, self.width, self.components)

        ImageUnmap(self, mapped_data[0])

        return data


class FrameBufferImage(Image):
    def __init__(self, context, frame_buffer):
        self.frame_buffer = frame_buffer
        super().__init__(context, self.frame_buffer.width, self.frame_buffer.height)

    def update(self):
        mapped_data = ffi.new('void **')
        ImageMap(self, IMAGE_MAP_WRITE, mapped_data)
        self.frame_buffer.get_data(mapped_data[0])
        ImageUnmap(self, mapped_data[0])


class FrameBufferImageCL(FrameBufferImage):
    def _create(self):
        ContextCreateImageFromOpenClMemory(self.context, self._get_desc(), 
                                           self.frame_buffer.get_cl_mem(), False, self)

    def update(self):
        # image is updated directly
        pass


class FrameBufferImageGL(FrameBufferImage):
    def _create(self):
        ContextCreateImageFromOpenGlTexture(self.context, bgl.GL_TEXTURE_2D, 0, self.frame_buffer.gl_texture, self)

    def update(self):
        # image is updated directly
        pass


class FrameBufferImageMetal(FrameBufferImage):
    def _create(self):
        ContextCreateImageFromMetalMemory(self.context, self._get_desc(), 
                                           self.frame_buffer.get_cl_mem(), self.frame_buffer.size(), self)

    def update(self):
        # image is updated directly
        pass


class ImageFilter(Object):
    core_type_name = 'rif_image_filter'

    def __init__(self, context, filter_type):
        super().__init__()
        self.context = context
        self.parameters = {}
        ContextCreateImageFilter(self.context, filter_type, self)

    def set_parameter(self, name, value):
        if name in self.parameters and self.parameters[name] == value:
            return

        if isinstance(value, int):
            ImageFilterSetParameter1u(self, pyrpr.encode(name), value)
            self.parameters[name] = value
        elif isinstance(value, float):
            ImageFilterSetParameter1f(self, pyrpr.encode(name), value)
            self.parameters[name] = value
        elif isinstance(value, str):
            ImageFilterSetParameterString(self, pyrpr.encode(name), pyrpr.encode(value))
            self.parameters[name] = value
        elif isinstance(value, Image):
            ImageFilterSetParameterImage(self, pyrpr.encode(name), value)
            self.parameters[name] = value
        elif isinstance(value, tuple) and len(value) == 2:
            if isinstance(value[0], int):
                ImageFilterSetParameter2u(self, pyrpr.encode(name), *value)
            else:
                raise TypeError("Incorrect type for ImageFilterSetParameter*", self, name, value)
            self.parameters[name] = value
        elif isinstance(value, list) and isinstance(value[0], float):
            arr = ffi.new('float[]', value)
            ImageFilterSetParameterFloatArray(self, pyrpr.encode(name), arr, len(value))
            self.parameters[name] = (value, arr)
        elif isinstance(value, list) and isinstance(value[0], Image):
            handles = []
            for img in value:
                handles.append(img._get_handle())
            arr = ArrayObject('rif_image[]', handles)
            ImageFilterSetParameterImageArray(self,pyrpr.encode(name), arr, len(value))
            self.parameters[name] = (value, arr)
        else:
            raise TypeError("Incorrect type for ImageFilterSetParameter*", self, name, value)


class CommandQueue(Object):
    core_type_name = 'rif_command_queue'

    def __init__(self, context):
        super().__init__()
        self.context = context
        self.image_filters = {}
        ContextCreateCommandQueue(self.context, self)

    def attach_image_filter(self, image_filter, input_image, output_image):
        CommandQueueAttachImageFilter(self, image_filter, input_image, output_image)
        self.image_filters[image_filter] = (input_image, output_image)

    def detach_image_filters(self):
        for image_filter in self.image_filters.keys():
            CommandQueueDetachImageFilter(self, image_filter)

        self.image_filters.clear()

    def execute(self):
        ContextExecuteCommandQueue(self.context, self, ffi.NULL, ffi.NULL, ffi.NULL)

    def delete(self):
        self.detach_image_filters()
        super().delete()
