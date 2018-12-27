import platform

import pyrprsupportwrap
from pyrprsupportwrap import *

import pyrpr

lib_wrapped_log_calls = False


class _init_data:
    _log_fun = None


def init(log_fun, rprsdk_bin_path):

    _module = __import__(__name__)

    _init_data._log_fun = log_fun

    if platform.system() == "Windows":
        lib_name = 'RprSupport64.dll'
    elif platform.system() == "Linux":
        lib_name = 'libRprSupport64.so'
    elif platform.system() == "Darwin":
        lib_name = 'libRprSupport64.dylib'
    else:
        raise ValueError("Not supported OS", platform.system())

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



class Context(Object):
    core_type_name = 'rprx_context'

    def __init__(self, material_system):
        super().__init__()
        self.material_system = material_system
        CreateContext(self.material_system, 0, self)

    def __del__(self):
        DeleteContext(self)


class Material(Object):
    core_type_name = 'rprx_material'

    def __init__(self, context, material_type):
        super().__init__()
        self.context = context
        self.parameters = {}
        self.material_nodes = {}
        CreateMaterial(self.context, material_type, self)

    def __del__(self):
        MaterialDelete(self.context, self)

    def commit(self):
        MaterialCommit(self.context, self)

    def set_input(self, name, value):
        if value is None or isinstance(value, pyrpr.MaterialNode):
            MaterialSetParameterN(self.context, self, name, value)
        elif isinstance(value, int):
            MaterialSetParameterU(self.context, self, name, value)
        elif isinstance(value, tuple) and len(value) == 4:
            MaterialSetParameterF(self.context, self, name, *value)
        else:
            raise TypeError("Incorrect type for MaterialSetParameter*", self, name, value)

        self.parameters[name] = value

    def attach(self, shape):
        ShapeAttachMaterial(self.context, shape, self)
        
    def detach(self, shape):
        ShapeDetachMaterial(self.context, shape, self)

    def attach_to_node(self, input_name, material_node):
        MaterialAttachMaterial(self.context, material_node, pyrpr.encode(input_name), self)
        self.commit()

    def detach_from_node(self, input_name, material_node):
        MaterialDetachMaterial(self.context, material_node, pyrpr.encode(input_name), self)
