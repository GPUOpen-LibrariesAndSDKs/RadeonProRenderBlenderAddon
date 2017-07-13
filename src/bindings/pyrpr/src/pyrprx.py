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


def init(log_fun):

    _module = __import__(__name__)

    _init_data._log_fun = log_fun

    import __rprx

    pyrprsupportwrap.lib = __rprx.lib
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


