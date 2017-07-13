import platform
import traceback
import inspect
import ctypes

import pyrprwrap
from pyrprwrap import *

import functools

lib_wrapped_log_calls = False


class CoreError(Exception):

    def __init__(self, status, func_name, argv, module_name):
        for name in pyrprwrap._constants_names:
            value = getattr(pyrprwrap, name)
            if name.startswith('ERROR_') and status == value:
                status = "%s<%d>" % (name, value)
                break
        super().__init__(
            "%s call %s(%s) returned error code: <%s>"%(
                module_name, func_name, ', '.join(str(a) for a in argv), status))


def wrap_core_check_success(f, module_name):
    @functools.wraps(f)
    def wrapped(*argv):
        status = f(*argv)
        if SUCCESS != status:
            raise CoreError(status, f.__name__, argv, module_name)
        return status
    return wrapped

def wrap_core_log_call(f, log_fun, module_name):
    signature = inspect.signature(f)

    @functools.wraps(f)
    def wrapped(*argv):
        log_fun(module_name+'::'+f.__name__, ', '.join(p.name+': '+str(value) for p, value in zip(signature.parameters.values(), argv)))
        #log_fun(f.__name__, ', '.join(p.name for p in signature.parameters.values()))

        result = f(*argv)
        log_fun(module_name+'::'+f.__name__, "done")
        return result
    return wrapped


import threading

global_lock = threading.Lock()


def wrap_core_sync(f):
    @functools.wraps(f)
    def wrapper(*argv):
        with global_lock:
            return f(*argv)
    return wrapper


class _init_data:
    _log_fun = None


def init(log_fun, sync_calls=True, rprsdk_bin_path=None):

    _module = __import__(__name__)

    _init_data._log_fun = log_fun

    if "Windows" == platform.system():
        # preload OpenImage dll so we don't have to add PATH
        ctypes.CDLL(str(rprsdk_bin_path / 'OpenImageIO_RPR.dll'))
        lib_names = ['RadeonProRender64.dll', 'RprSupport64.dll']
    elif "Linux" == platform.system():
        lib_names = ['libRadeonProRender64.so', 'libRprSupport64.so']
    else:
        assert False

    for lib_name in lib_names:
        rpr_lib_path = rprsdk_bin_path / lib_name
        ctypes.CDLL(str(rpr_lib_path))

    import __rpr
    try:
        lib = __rpr.lib
    except AttributeError:
        lib = __rpr.ffi.dlopen(str(rprsdk_bin_path/lib_names[0]))
    pyrprwrap.lib = lib
    pyrprwrap.ffi = __rpr.ffi
    global ffi
    ffi = __rpr.ffi

    for name in pyrprwrap._constants_names:
        setattr(_module, name, getattr(pyrprwrap, name))
    
    for name in pyrprwrap._functions_names:
    
        wrapped = getattr(pyrprwrap, name)
        # wrap all functions here(for more flexilibity) to log call, if enabled
        # and to assert that SUCCESS is returned from them
        if sync_calls:
            wrapped = wrap_core_sync(wrapped)
        if lib_wrapped_log_calls:
            wrapped = wrap_core_log_call(wrapped, log_fun, 'RPR')
        if all(name not in wrapped.__name__ for name in ['RegisterPlugin', 'CreateContext']):
            wrapped = wrap_core_check_success(wrapped, 'RPR')
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
            raise

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


class Context(Object):

    core_type_name = 'rpr_context'

    def __init__(self, plugins, flags, props=None, cache_path=None, api_version=API_VERSION):
        super().__init__()

        self.create_result = CreateContext(
            api_version,
            plugins,
            len(plugins),
            flags,
            ffi.NULL if not props else props,
            cache_path.encode('latin1') if cache_path else ffi.NULL,
            self)

    def delete(self):
        super().delete()

class Scene(Object):

    core_type_name = 'rpr_scene'

    def __init__(self, context):
        super().__init__()
        ContextCreateScene(context, self)


class Shape(Object):

    core_type_name = 'rpr_shape'

class Camera(Object):

    core_type_name = 'rpr_camera'

class FrameBuffer(Object):

    core_type_name = 'rpr_framebuffer'

class MaterialSystem(Object):

    core_type_name = 'rpr_material_system'

class MaterialNode(Object):

    core_type_name = 'rpr_material_node'

class Light(Object):

    core_type_name = 'rpr_light'

class Image(Object):

    core_type_name = 'rpr_image'

class PostEffect(Object):

    core_type_name = 'rpr_post_effect'


def is_transform_matrix_valid(transform):
    import numpy as np
    # just checking for 'NaN', everything else - catch failure of SetTransform and recover
    if not np.all(np.isfinite(transform)):
        return False
    return True

