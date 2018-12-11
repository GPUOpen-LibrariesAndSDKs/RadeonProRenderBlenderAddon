import platform
import weakref

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
        self._handle_ptr = ffi.new(self.core_type_name + '*', ffi.NULL)

    def _get_handle(self):
        return self._handle_ptr[0]

    def _delete(self):
        pass


class Context(Object):
    core_type_name = 'rprx_context'

    def __init__(self, material_system):
        super().__init__()
        CreateContext(material_system, 0, self)

        self.materials = set()

    def create_material(self, material_type):
        return Material(self, material_type)

    def _delete(self):
        for mat in self.materials:
            mat._delete()
        self.materials.clear()
        DeleteContext(self)


class Material(Object):
    core_type_name = 'rprx_material'

    def __init__(self, context, material_type):
        super().__init__()
        self.context = weakref.ref(context)
        self.parameters = {}
        self.material_nodes = {}
        CreateMaterial(context, material_type, self)
        context.materials.add(self)

    def _delete(self):
        MaterialDelete(self.context(), self)

    def commit(self):
        MaterialCommit(self.context(), self)

    def set_parameter(self, parameter, value):
        if value is None or isinstance(value, pyrpr.MaterialNode):
            MaterialSetParameterN(self.context(), self, parameter, value)
        elif isinstance(value, int):
            MaterialSetParameterU(self.context(), self, parameter, value)
        elif isinstance(value, tuple) and len(value) == 4:
            MaterialSetParameterF(self.context(), self, parameter, *value)
        else:
            raise TypeError("Incorrect type for MaterialSetParameter*", self, parameter, value)

        self.parameters[parameter] = value

    def attach(self, mesh):
        mesh.x_material = self
        ShapeAttachMaterial(self.context(), mesh, self)
        
    def detach(self, mesh):
        mesh.x_material = None
        ShapeDetachMaterial(self.context(), mesh, self)

    def attach_to_node(self, parameter, node):
        material = node.x_inputs.get(parameter, None)
        if material:
            # detaching existing material
            MaterialAttachMaterial(self.context(), None, pyrpr.encode(parameter), material)

        node.x_inputs[parameter] = self
        MaterialAttachMaterial(self.context(), node, pyrpr.encode(parameter), self)
        self.commit()

    def detach_from_node(self, parameter, node):
        del node.x_inputs[parameter]
        MaterialAttachMaterial(self.context(), None, pyrpr.encode(parameter), self)
        self.commit()
