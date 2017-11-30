import functools
import platform
import traceback
import inspect
import ctypes

import pyrpropenclwrap
from pyrpropenclwrap import *

import pyrpr

def init():

    _module = __import__(__name__)

    import __rprcl

    pyrpropenclwrap.ffi = __rprcl.ffi
    global ffi
    ffi = __rprcl.ffi

    for name in pyrpropenclwrap._constants_names:
        setattr(_module, name, getattr(pyrpropenclwrap, name))

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
            raise

    def delete(self):
        if self._handle_ptr and self._get_handle():
            ObjectDelete(self._get_handle())
            self._reset_handle()

    def _reset_handle(self):
        self._handle_ptr = ffi.new(self.ffi_type_name, ffi.NULL)

    def _get_handle(self):
        return self._handle_ptr[0]