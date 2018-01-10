import functools
import platform
import traceback
import inspect
import ctypes

import pyrprsupportwrap
from pyrprsupportwrap import *

import pyrpr

lib_wrapped_log_calls = False


class _init_data:
    _log_fun = None


def init(log_fun, rprsdk_bin_path):

    _module = __import__(__name__)

    _init_data._log_fun = log_fun

    if "Windows" == platform.system():
        lib_name = 'RprSupport64.dll'
    elif "Linux" == platform.system():
        lib_name = 'libRprSupport64.so'
    elif "Darwin" == platform.system():
        lib_name = 'libRprSupport64.dylib'
    else:
        assert False

    import __rprx

    try:
        lib = __rprx.lib
    except AttributeError:
        lib = __rprx.ffi.dlopen(str(rprsdk_bin_path/lib_name))

    pyrprsupportwrap.lib = lib
    pyrprsupportwrap.ffi = __rprx.ffi
    global ffi
    ffi = __rprx.ffi

    for name in pyrprsupportwrap._constants_names:
        setattr(_module, name, getattr(pyrprsupportwrap, name))

    for name in pyrprsupportwrap._functions_names:

        wrapped = getattr(pyrprsupportwrap, name)

        if lib_wrapped_log_calls:
            wrapped = pyrpr.wrap_core_log_call(wrapped, log_fun, 'RPRX')
        wrapped = pyrpr.wrap_core_check_success(wrapped, 'RPRX')
        setattr(_module, name, wrapped)
    del _module


class Object:

    core_type_name = 'void*'

    def __init__(self, core_type_name=None):
        self.ffi_type_name = (core_type_name if core_type_name is not None else self.core_type_name) + '*'
        self._reset_handle()

    def _reset_handle(self):
        self._handle_ptr = ffi.new(self.ffi_type_name, ffi.NULL)

    def _get_handle(self):
        return self._handle_ptr[0]


