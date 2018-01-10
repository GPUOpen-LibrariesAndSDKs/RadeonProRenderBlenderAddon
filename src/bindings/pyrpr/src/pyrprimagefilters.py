import functools
import platform
import traceback
import inspect
import ctypes
import os
import sys

import pyrprimagefilterswrap
from pyrprimagefilterswrap import *

import pyrpr

lib_wrapped_log_calls = False


class _init_data:
    _log_fun = None


def init(log_fun, rprsdk_bin_path):
    _module = __import__(__name__)

    _init_data._log_fun = log_fun

    lib_platform = ""
    rel_path = "../../../RadeonProImageProcessing"
    if "Windows" == platform.system():
        lib_name = 'RadeonImageFilters64.dll'
        lib_platform = "Win/lib"
    elif "Linux" == platform.system():
        lib_name = 'libRadeonImageFilters64.so'
        lib_platform = "Linux/Ubuntu/lib64"
    elif "Darwin" == platform.system():
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
            raise

    def delete(self):
        if self._handle_ptr and self._get_handle():
            del self._handle_ptr

    def _reset_handle(self):
        self._handle_ptr = ffi.new(self.ffi_type_name, ffi.NULL)

    def _get_handle(self):
        return self._handle_ptr[0]

class ArrayObject:
    def __init__(self, core_type_name, init_data):
        self._handle_ptr = ffi.new(core_type_name, init_data)

    def __del__(self):
        del self._handle_ptr

class RifContext(Object):
    core_type_name = 'rif_context'

class RifCommandQueue(Object):
    core_type_name = 'rif_command_queue'

class RifImageFilter(Object):
    core_type_name = 'rif_image_filter'

class RifImage(Object):
    core_type_name = 'rif_image'
