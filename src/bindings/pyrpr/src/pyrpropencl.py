import sys

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


def _context_get_info(context, cl_type, cl_str_type):
    val = ffi.new('%s *' % cl_str_type)
    pyrpr.ContextGetInfo(context, cl_type, sys.getsizeof(val), val, ffi.NULL)
    return val[0]


def get_cl_context(context):
    return _context_get_info(context, CONTEXT, 'rpr_cl_context')


def get_cl_device(context):
    return _context_get_info(context, DEVICE, 'rpr_cl_device')


def get_cl_command_queue(context):
    return _context_get_info(context, COMMAND_QUEUE, 'rpr_cl_command_queue')


def get_mem_object(frame_buffer):
    cl_mem = ffi.new('rpr_cl_mem *')
    pyrpr.FrameBufferGetInfo(frame_buffer, MEM_OBJECT, sys.getsizeof(cl_mem), cl_mem, ffi.NULL)
    return cl_mem[0]
