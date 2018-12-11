import platform
import traceback
import inspect
import ctypes
import os
import threading
import time
import functools
import sys
import numpy as np
import weakref
import bgl

import pyrprwrap
from pyrprwrap import *

import pyrprx

lib_wrapped_log_calls = False

class CoreError(Exception):
    def __init__(self, status, func_name, argv, module_name):
        for name in pyrprwrap._constants_names:
            value = getattr(pyrprwrap, name)
            if name.startswith('ERROR_') and status == value:
                status = "%s<%d>" % (name, value)
                break
       
        error_message = self.get_last_error_message(argv[0]) if len(argv) > 0 else ""

        super().__init__(
            "%s call %s(%s) returned error code <%s> with error message: '%s'" % 
                (module_name, func_name, ', '.join(str(a) for a in argv), status, error_message))

    def get_last_error_message(self, context):
        if not isinstance(context, Context):
            return ""

        ffi = pyrprwrap.ffi
        lib = pyrprwrap.lib
        rpr_context = context._get_handle() if context else ffi.NULL
        sizeParamPtr = ffi.new('size_t *', 0)

        # bypass calling ContextGetInfo through wrappers, that's why calling it directly to the lib
        state = lib.rprContextGetInfo(rpr_context, CONTEXT_LAST_ERROR_MESSAGE, 0, ffi.NULL, sizeParamPtr)
        sizeParam = sizeParamPtr[0]
        if state == SUCCESS and sizeParam >= 1:
            strData = ffi.new('char[%d]' % sizeParam)
            state = lib.rprContextGetInfo(rpr_context, CONTEXT_LAST_ERROR_MESSAGE, sizeParam, strData, ffi.NULL)
            if state == SUCCESS:
                return ffi.string(strData)

        return ""


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
        time_begin = time.perf_counter()
        result = f(*argv)
        time_end = time.perf_counter()
        log_fun(module_name+'::'+f.__name__, "done in ", time_end-time_begin)
        return result
    return wrapped


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

    alternate_relative_paths = ["../../../RadeonProImageProcessing", "../../../RadeonProRender-GLTF"]
    lib_platform = ""
    if platform.system() == "Windows":
        # preload OpenImage dll so we don't have to add PATH
        ctypes.CDLL(str(rprsdk_bin_path / 'OpenImageIO_RPR.dll'))

        lib_names = ['RadeonProRender64.dll', 'RprSupport64.dll','RadeonImageFilters64.dll', 'FreeImage.dll', 'ProRenderGLTF.dll']
        lib_platform = "Win/lib"
    elif platform.system() == "Linux":
        lib_names = ['libRadeonProRender64.so', 'libRprSupport64.so', 'libRadeonImageFilters64.so']
        lib_platform = "Linux/Ubuntu/lib64"
    elif platform.system() == "Darwin":
        lib_names = ['libRadeonProRender64.dylib', 'libRprSupport64.dylib','libRadeonImageFilters64.dylib']
    else:
        raise ValueError("Not supported OS", platform.system())

    for lib_name in lib_names:
        rpr_lib_path = rprsdk_bin_path / lib_name
        if os.path.isfile(str(rpr_lib_path)):
            ctypes.CDLL(str(rpr_lib_path))
        else:
            found = False
            for relpath in alternate_relative_paths:
                rpr_lib_path = rprsdk_bin_path / relpath / lib_platform / lib_name
                if os.path.isfile(str(rpr_lib_path)):
                    ctypes.CDLL(str(rpr_lib_path))
                    found = True
                    break

            if not found:
                print("Shared lib does not exists \"%s\"\n" % lib_name)
                assert False

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
        if wrapped.__name__ != 'RegisterPlugin':
            wrapped = wrap_core_check_success(wrapped, 'RPR')
        setattr(_module, name, wrapped)

    del _module
    

def encode(string):
    return string.encode('utf8')


def decode(bin_str):
    return bin_str.decode('utf8')


def register_plugin(path):
    return RegisterPlugin(encode(path))


def is_gpu_enabled(creation_flags):
    for i in range(16):
        if getattr(pyrprwrap, 'CREATION_FLAGS_ENABLE_GPU%d' % i) & creation_flags:
            return True

    return False


def get_first_gpu_id_used(creation_flags):
    for i in range(16):
        if getattr(pyrprwrap, 'CREATION_FLAGS_ENABLE_GPU%d' % i) & creation_flags:
            return i

    raise IndexError("GPU is not used", creation_flags)


class Object:
    core_type_name = 'void*'

    def __init__(self):
        self._reset_handle()
        self.name = None

    def _delete(self):
        if lib_wrapped_log_calls:
            _init_data._log_fun('delete: ', self.name, self)
        ObjectDelete(self._get_handle())
        self._reset_handle()

    def _reset_handle(self):
        self._handle_ptr = ffi.new(self.core_type_name + '*', ffi.NULL)

    def _get_handle(self):
        return self._handle_ptr[0]

    def set_name(self, name):
        ObjectSetName(self._get_handle(), encode(name))
        self.name = name


class Context(Object):
    core_type_name = 'rpr_context'

    def __init__(self, plugins, flags, props=None, cache_path=None):
        super().__init__()

        props_ptr = ffi.NULL
        if props is not None:
            props_ptr = ffi.new("rpr_context_properties[]",
                                [ffi.cast("rpr_context_properties", entry) for entry in props])

        CreateContext(API_VERSION, plugins, len(plugins), flags,
            props_ptr, encode(cache_path) if cache_path else ffi.NULL,
            self)

        # Currently we create only one material system
        self.material_system = MaterialSystem(self)

        self.aovs = {}
        self.parameters = {}
        self.scenes = set()
        self.scene = None
        self.cameras = set()
        self.meshes = set()
        self.instances = set()
        self.lights = set()
        self.hetero_volumes = set()
        self.frame_buffers = set()
        self.post_effects = set()
        self.images = set()
        self.composites = set()

    def __del__(self):
        self._delete()

    def _delete(self):
        for pe in self.post_effects:
            ContextDetachPostEffect(self, pe)
        
        self.material_system._delete()
            
        self.set_scene(None)

        for objects in [self.post_effects,
                        self.scenes,
                        self.composites, # before framebuffers
                        self.frame_buffers,
                        self.cameras,
                        self.lights,
                        self.instances,  # before meshes
                        self.meshes,
                        self.hetero_volumes,
                        self.images,
                        ]:
            for obj in objects:
                obj._delete()
            objects.clear()

        super()._delete()

    #
    # Creating objects functions
    #

    def create_scene(self):
        return Scene(self)

    def set_scene(self, scene):
        ContextSetScene(self, scene)
        self.scene = scene
   
    def create_camera(self):
        return Camera(self)

    def create_mesh(self, vertices, normals, texcoords, 
                 vertex_indices, normal_indices, texcoord_indices, 
                 num_face_vertices):
        
        return Mesh(self, vertices, normals, texcoords, 
                    vertex_indices, normal_indices, texcoord_indices, 
                    num_face_vertices)

    def create_instance(self, mesh):
        return Instance(self, mesh)

    def create_hetero_volume(self, gridSizeX, gridSizeY, gridSizeZ, 
                             indices:np.array, indicesListTopology, 
                             grid_data:np.array):
        return HeteroVolume(self, gridSizeX, gridSizeY, gridSizeZ, 
                            indices, indicesListTopology, 
                            grid_data)

    def create_light(self, light_type):
        if light_type == 'point':
            return PointLight(self)
        if light_type == 'spot':
            return SpotLight(self)
        if light_type == 'directional':
            return DirectionalLight(self)
        if light_type == 'ies':
            return IESLight(self)
        if light_type == 'environment':
            return EnvironmentLight(self)

        raise KeyError("No such light type", light_type)

    def attach_post_effect(self, post_effect_type):
        return PostEffect(self, post_effect_type)

    def create_frame_buffer(self, width, height, use_gl=False):
        if use_gl:
            return FrameBufferGL(self, width, height)
        else: 
            return FrameBuffer(self, width, height)

    def create_composite(self, in_type):
        return Composite(self, in_type)

    def create_image(self, data: np.array):
        return Image(self, data)

    def create_image_file(self, path):
        return ImageFile(self, path)

    def create_buffer(self, data: np.array, element_type):
        return Buffer(self, data, element_type)

    #
    # Render functions
    #
    def render(self):
        ContextRender(self)

    def render_tile(self, xmin, xmax, ymin, ymax):
        ContextRenderTile(self, xmin, xmax, ymin, ymax)

    def attach_aov(self, aov, frame_buffer):
        if aov in self.aovs:
            self.detach_aov(aov)

        self.aovs[aov] = frame_buffer
        frame_buffer.aov = aov
        ContextSetAOV(self, aov, frame_buffer)

    def detach_aov(self, aov):
        self.aovs[aov].aov = None
        ContextSetAOV(self, aov, None)
        del self.aovs[aov]

    def set_parameter(self, name, param):
        if self:
            if self.parameters.get(name, None) == param:
                return

        if isinstance(param, int):
            ContextSetParameter1u(self, encode(name), param)
        elif isinstance(param, bool):
            ContextSetParameter1u(self, encode(name), int(param))
        elif isinstance(param, float):
            ContextSetParameter1f(self, encode(name), param)
        elif isinstance(param, str):
            ContextSetParameterString(self, encode(name), encode(param))
        elif isinstance(param, tuple) and len(param) == 3:
            ContextSetParameter3f(self, encode(name), *param)
        elif isinstance(param, tuple) and len(param) == 4:
            ContextSetParameter4f(self, encode(name), *param)
        else:
            raise TypeError("Incorrect type for ContextSetParameter*", self, name, param)

        if self:
            self.parameters[name] = param

    #
    # Info functions
    #
    def get_info_int(self, context_info):
        size = ffi.new('size_t *', 0)
        ContextGetInfo(self, context_info, 0, ffi.NULL, size)
        return size[0]

    def get_info_str(self, context_info):
        size = self.get_info_int(context_info)
        ptr = ffi.new('char[]', size)
        ContextGetInfo(self, context_info, size, ptr, ffi.NULL)
        return decode(ffi.string(ptr))

    def get_creation_flags(self):
        creation_flags = ffi.new("rpr_creation_flags*", 0)
        ContextGetInfo(self, CONTEXT_CREATION_FLAGS, sys.getsizeof(creation_flags), creation_flags, ffi.NULL)
        return creation_flags[0]

    def _get_cl_info(self, cl_type, cl_str_type):
        val = ffi.new('%s *' % cl_str_type)
        ContextGetInfo(self, cl_type, sys.getsizeof(val), val, ffi.NULL)
        return val[0]

    def get_cl_context(self):
        return self._get_cl_info(CL_CONTEXT, 'rpr_cl_context')

    def get_cl_device(self):
        return self._get_cl_info(CL_DEVICE, 'rpr_cl_device')

    def get_cl_command_queue(self):
        return self._get_cl_info(CL_COMMAND_QUEUE, 'rpr_cl_command_queue')


class Scene(Object):
    core_type_name = 'rpr_scene'

    def __init__(self, context):
        super().__init__()
        self.objects = set()
        self.camera = None
        self.environments = {}
        ContextCreateScene(context, self)
        context.scenes.add(self)

    def _delete(self):
        self.clear()
        super()._delete()

    def attach(self, obj):
        if isinstance(obj, Shape):
            SceneAttachShape(self, obj)
        elif isinstance(obj, Light):
            SceneAttachLight(self, obj)
        elif isinstance(obj, HeteroVolume):
            SceneAttachHeteroVolume(self, obj)
        else:
            raise TypeError("Incorrect type for SceneAttach*", self, obj)

        self.objects.add(obj)

    def detach(self, obj):
        if isinstance(obj, Shape):
            SceneDetachShape(self, obj)
        elif isinstance(obj, Light):
            SceneDetachLight(self, obj)
        elif isinstance(obj, HeteroVolume):
            SceneDetachHeteroVolume(self, obj)
        else:
            raise TypeError("Incorrect type for SceneDetach*", self, obj)
 
        self.objects.remove(obj)

    def clear(self):
        for obj in tuple(self.objects):
            self.detach(obj)
        for override in tuple(self.environments.keys()):
            self.remove_environment(override)

        self.set_camera(None)
        SceneClear(self)

    def set_camera(self, camera):
        self.camera = camera
        SceneSetCamera(self, self.camera)

    def add_environment(self, override, light):
        self.environments[override] = light
        SceneSetEnvironmentOverride(self, override, light)

    def remove_environment(self, override):
        del self.environments[override]
        SceneSetEnvironmentOverride(self, override, None)


class Shape(Object):
    core_type_name = 'rpr_shape'

    def set_transform(self, transform:np.array, transpose=True): # Blender needs matrix to be transposed
        ShapeSetTransform(self, transpose, ffi.cast('float*', transform.ctypes.data))

    def set_linear_motion(self, x, y, z):
        ShapeSetLinearMotion(self, x, y, z)

    def set_angular_motion(self, x, y, z, w):
        ShapeSetAngularMotion(self, x, y, z, w)

    def set_scale_motion(self, x, y, z):
        ShapeSetScaleMotion(self, x, y, z)

    def set_shadow_catcher(self, shadow_catcher):
        ShapeSetShadowCatcher(self, shadow_catcher)

    def set_shadow(self, casts_shadow):
        ShapeSetShadow(self, casts_shadow)

    def set_visibility(self, visible):
        ShapeSetVisibility(self, visible)

    def set_visibility_ex(self, visibility_type, visible):
        if API_VERSION >= 0x010032000:
            flags = {
                "visible.light": SHAPE_VISIBILITY_LIGHT,
                "visible.refraction.glossy": SHAPE_VISIBILITY_GLOSSY_REFRACTION,
                "visible.reflection.glossy": SHAPE_VISIBILITY_GLOSSY_REFLECTION,
                "visible.diffuse": SHAPE_VISIBILITY_DIFFUSE,
                "visible.transparent": SHAPE_VISIBILITY_TRANSPARENT,
                "visible.refraction": SHAPE_VISIBILITY_REFRACTION,
                "visible.reflection": SHAPE_VISIBILITY_REFLECTION,
                "visible.shadow": SHAPE_VISIBILITY_SHADOW,
                "visible.primary": SHAPE_VISIBILITY_PRIMARY_ONLY_FLAG,
                }
            ShapeSetVisibilityFlag(self, flags[visibility_type], visible)
        else:
            ShapeSetVisibilityEx(self, encode(visibility_type), visible)

    def set_visibility_in_specular(self, visible):
        ShapeSetVisibilityInSpecular(self, visible)

    def set_visibility_primary_only(self, visible):
        if API_VERSION >= 0x010032000:
            ShapeSetVisibilityFlag(self, SHAPE_VISIBILITY_PRIMARY_ONLY_FLAG, visible)
        else:
            ShapeSetVisibilityPrimaryOnly(self, visible)

    def set_subdivision_factor(self, factor):
        ShapeSetSubdivisionFactor(self, factor)

    def set_auto_adapt_subdivision_factor(self, framebuffer, camera, factor):
        ShapeAutoAdaptSubdivisionFactor(self, framebuffer, camera, factor)

    def set_subdivision_boundary_interop(self, boundary):
        ShapeSetSubdivisionBoundaryInterop(self, boundary)

    def set_subdivision_crease_weight(self, factor):
        ShapeSetSubdivisionCreaseWeight(self, factor)

    def set_light_group_id(self, group_id):
        ShapeSetLightGroupID(self, group_id)



class Mesh(Shape):
    def __init__(self, context, vertices, normals, texcoords, 
                 vertex_indices, normal_indices, texcoord_indices, 
                 num_face_vertices):
        super().__init__()
        self.material = None
        self.x_material = None    # pyrprx.Material
        self.volume_material = None
        self.displacement_material = None
        self.hetero_volume = None

        if texcoords is None:
            texcoords_ptr = ffi.NULL
            texcoords_count = 0
            texcoords_nbytes = 0
            texcoords_ind_ptr = ffi.NULL
            texcoords_ind_nbytes = 0
        else:
            texcoords_ptr = ffi.cast("float *", texcoords.ctypes.data)
            texcoords_count = len(texcoords)
            texcoords_nbytes = texcoords[0].nbytes
            texcoords_ind_ptr = ffi.cast('rpr_int*', texcoord_indices.ctypes.data)
            texcoords_ind_nbytes = texcoord_indices[0].nbytes

        ContextCreateMesh(context,
                 ffi.cast("float *", vertices.ctypes.data), len(vertices), vertices[0].nbytes,
                 ffi.cast("float *", normals.ctypes.data), len(normals), normals[0].nbytes, 
                 texcoords_ptr, texcoords_count, texcoords_nbytes, 
                 ffi.cast('rpr_int*', vertex_indices.ctypes.data), vertex_indices[0].nbytes, 
                 ffi.cast('rpr_int*', normal_indices.ctypes.data), normal_indices[0].nbytes,
                 texcoords_ind_ptr, texcoords_ind_nbytes, 
                 ffi.cast('rpr_int*', num_face_vertices.ctypes.data), len(num_face_vertices),
                 self)
        context.meshes.add(self)

    def _delete(self):
        if self.material:
            self.set_material(None)
        if self.x_material:
            self.x_material.detach(self)
        if self.volume_material:
            self.set_volume_material(None)
        if self.displacement_material:
            self.set_displacement_material(None)
        if self.hetero_volume:
            self.set_hetero_volume(None)

        super()._delete()

    def set_material(self, node):
        self.material = node
        ShapeSetMaterial(self, self.material)

    def set_volume_material(self, node):
        self.volume_material = node
        ShapeSetVolumeMaterial(self, self.volume_material)

    def set_displacement_material(self, node):
        self.displacement_material = node
        ShapeSetDisplacementMaterial(self, self.displacement_material)

    def set_displacement_scale(self, minscale, maxscale):
        ShapeSetDisplacementScale(self, minscale, maxscale)

    def set_hetero_volume(self, hetero_volume):
        self.hetero_volume = hetero_volume
        ShapeSetHeteroVolume(self, self.hetero_volume)


class Instance(Shape):
    def __init__(self, context, mesh):
        super().__init__()
        self.mesh = mesh
        ContextCreateInstance(context, mesh, self)
        context.instances.add(self)

    def set_material(self, mat_node):
        pass

    def set_volume_material(self, node):
        pass

    def set_displacement_material(self, node):
        pass

    def set_displacement_scale(self, minscale, maxscale):
        pass

    def set_hetero_volume(self, hetero_volume):
        pass


class HeteroVolume(Object):
    core_type_name = 'rpr_hetero_volume'

    def __init__(self, context, 
                 gridSizeX, gridSizeY, gridSizeZ, 
                 indices:np.array, indicesListTopology, 
                 grid_data:np.array):
        super().__init__()

        ContextCreateHeteroVolume(
            context, self,
            gridSizeX, gridSizeY, gridSizeZ,
            ffi.cast('const size_t *', indices.ctypes.data), len(indices), indicesListTopology, 
            ffi.cast('const float *', grid_data.ctypes.data), grid_data.nbytes, 0)
        context.hetero_volumes.add(self)

    def set_transform(self, transform:np.array, transpose=True): # Blender needs matrix to be transposed
        HeteroVolumeSetTransform(self, transpose, ffi.cast('float*', transform.ctypes.data))


class Camera(Object):
    core_type_name = 'rpr_camera'

    def __init__(self, context):
        super().__init__()
        ContextCreateCamera(context, self)
        context.cameras.add(self)

    def set_mode(self, mode):
        CameraSetMode(self, mode)

    def look_at(self, pos, at, up):
        CameraLookAt(self, pos[0], pos[1], pos[2], 
                     at[0], at[1], at[2], 
                     up[0], up[1], up[2])

    def set_lens_shift(self, shiftx, shifty):
        CameraSetLensShift(self, shiftx, shifty)

    def set_focal_length(self, flength):
        CameraSetFocalLength(self, flength)

    def set_sensor_size(self, width, height):
        CameraSetSensorSize(self, width, height)

    def set_f_stop(self, fstop):
        CameraSetFStop(self, fstop)

    def set_aperture_blades(self, num_blades):
        CameraSetApertureBlades(self, num_blades)

    def set_focus_distance(self, fdist):
        CameraSetFocusDistance(self, fdist)

    def set_ortho(self, width, height):
        CameraSetOrthoWidth(self, width)
        CameraSetOrthoHeight(self, height)

    def set_angular_motion(self, x, y, z, w):
        CameraSetAngularMotion(self, x, y, z, w)

    def set_linear_motion(self, x, y, z):
        CameraSetLinearMotion(self, x, y, z)

    def set_exposure(self, exposure):
        CameraSetExposure(self, exposure)

    def set_clip_plane(self, near, far):
        CameraSetNearPlane(self, near)
        CameraSetFarPlane(self, far)

    def set_transform(self, transform:np.array, transpose=True): # Blender needs matrix to be transposed
        CameraSetTransform(self, transpose, ffi.cast('float*', transform.ctypes.data))


class FrameBuffer(Object):
    core_type_name = 'rpr_framebuffer'

    def __init__(self, context, width, height):
        super().__init__()
        self.context = weakref.ref(context)
        self.width = width
        self.height = height
        self.aov = None
        self._create()
        context.frame_buffers.add(self)

    def _delete(self):
        if self.aov is not None:
            self.context().detach_aov(self.aov)
             
        return super()._delete()

    def _create(self):
        desc = ffi.new("rpr_framebuffer_desc*")
        desc.fb_width, desc.fb_height = self.width, self.height
        ContextCreateFrameBuffer(self.context(), (4, COMPONENT_TYPE_FLOAT32), desc, self)

    def resize(self, width, height):
        if self.width == width and self.height == height:
            return

        aov = self.aov
        self._delete()

        self.width = width
        self.height = height
        self._create()

        if aov is not None:
            self.context().attach_aov(aov, self)

    def clear(self):
        FrameBufferClear(self)

    def resolve(self, resolved_fb):
        ContextResolveFrameBuffer(self.context(), self, resolved_fb, True)

    def get_data(self, buf=None):
        if buf:
            FrameBufferGetInfo(self, FRAMEBUFFER_DATA, self.size(), ffi.cast('float*', buf), ffi.NULL)
            return buf

        data = np.empty((self.height, self.width, 4), dtype=np.float32)
        FrameBufferGetInfo(self, FRAMEBUFFER_DATA, self.size(), ffi.cast('float*', data.ctypes.data), ffi.NULL)
        return data

    def size(self):
        return self.height*self.width*16    # 16 bytes = 4 channels of float32 values per pixel

    def save_to_file(self, file_path):
        FrameBufferSaveToFile(self, encode(file_path))

    def get_cl_mem(self):
        cl_mem = ffi.new('rpr_cl_mem *')
        FrameBufferGetInfo(self, CL_MEM_OBJECT, sys.getsizeof(cl_mem), cl_mem, ffi.NULL)
        return cl_mem[0]


class FrameBufferGL(FrameBuffer):
    def _create(self):
        textures = bgl.Buffer(bgl.GL_INT, [1,])
        bgl.glGenTextures(1, textures)
        self.gl_texture = textures[0]

        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.gl_texture)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_S, bgl.GL_REPEAT)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_T, bgl.GL_REPEAT)
        buf = bgl.Buffer(bgl.GL_FLOAT, [self.width, self.height, 4])
        bgl.glTexImage2D(bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA, self.width, self.height, 0, bgl.GL_RGBA, bgl.GL_FLOAT, buf)

        ContextCreateFramebufferFromGLTexture2D(self.context(), bgl.GL_TEXTURE_2D, 0, self.gl_texture, self)

    def _delete(self):
        super()._delete()
        textures = bgl.Buffer(bgl.GL_INT, [1,], [self.gl_texture,])
        bgl.glDeleteTextures(1, textures)


class Composite(Object):
    core_type_name = 'rpr_composite'

    def __init__(self, context, in_type):
        super().__init__()
        self.inputs = {}
        ContextCreateComposite(context, in_type, self)
        context.composites.add(self)

    def _delete(self):
        # TODO: probably we need to unset compositors and frame_buffers from inputs
        super()._delete()

    def set_input(self, name, in_value):
        if isinstance(in_value, int):
            CompositeSetInput1u(self, encode(name), in_value)
        elif isinstance(in_value, tuple) and len(in_value) == 4:
            CompositeSetInput4f(self, encode(name), *in_value)
        elif isinstance(in_value, Composite):
            CompositeSetInputC(self, encode(name), in_value)
        elif isinstance(in_value, FrameBuffer):
            CompositeSetInputFb(self, encode(name), in_value)
        else:
            raise TypeError("Incorrect type for  CompositeSetInput*", self, name, in_value)

        self.inputs[name] = in_value

    def compute(self, fb):
        CompositeCompute(self, fb)


class MaterialSystem(Object):
    core_type_name = 'rpr_material_system'

    def __init__(self, context):
        super().__init__()
        ContextCreateMaterialSystem(context, 0, self)
        self.nodes = set()
        self.x_context = pyrprx.Context(self)

    def _delete(self):
        for node in self.nodes:
            node._delete()
        self.nodes.clear()

        self.x_context._delete()

        super()._delete()

    def create_node(self, in_type):
        return MaterialNode(self, in_type)

    def create_material(self, material_type):
       return self.x_context.create_material(material_type)


class MaterialNode(Object):
    core_type_name = 'rpr_material_node'

    def __init__(self, mat_sys, in_type):
        super().__init__()
        self.inputs = {}
        self.x_inputs = {}
        MaterialSystemCreateNode(mat_sys, in_type, self)
        mat_sys.nodes.add(self)

    def _delete(self):
        for param, x_mat in self.x_inputs.items():
            x_mat.detach_from_node(param, self)
        
            super()._delete()

        # TODO: probably we need to unset images and buffers from inputs

    def set_input(self, in_input, in_value):
        if in_value is None or isinstance(in_value, MaterialNode):
            MaterialNodeSetInputN(self, encode(in_input), in_value)
        elif isinstance(in_value, int):
            MaterialNodeSetInputU(self, encode(in_input), in_value)
        elif isinstance(in_value, tuple) and len(in_value) == 4:
            MaterialNodeSetInputF(self, encode(in_input), *in_value)
        elif isinstance(in_value, Image):
            MaterialNodeSetInputImageData(self, encode(in_input), in_value)
        elif isinstance(in_value, Buffer):
            MaterialNodeSetInputBufferData(self, encode(in_input), in_value)
        else:
            raise TypeError("Incorrect type for MaterialNodeSetInput*", self, in_input, in_value)

        self.inputs[in_input] = in_value


class Light(Object):
    core_type_name = 'rpr_light'

    def set_transform(self, transform:np.array, transpose=True): # Blender needs matrix to be transposed
        LightSetTransform(self, transpose, ffi.cast('float*', transform.ctypes.data))

    def set_group_id(self, group_id):
        LightSetGroupId(self, group_id)


class EnvironmentLight(Light):
    def __init__(self, context):
        super().__init__()
        self.portals = set()
        self.image = None
        ContextCreateEnvironmentLight(context, self)
        context.lights.add(self)

    def set_image(self, image):
        self.image = image
        EnvironmentLightSetImage(self, self.image)

    def set_intensity_scale(self, intensity_scale):
        EnvironmentLightSetIntensityScale(self, intensity_scale)

    def attach_portal(self, scene, portal):
        EnvironmentLightAttachPortal(scene, self, portal)
        self.portals.add(portal)

    def detach_portal(self, scene, portal):
        EnvironmentLightDetachPortal(scene, self, portal)
        self.portals.remove(portal)


class IESLight(Light):
    def __init__(self, context):
        super().__init__()
        ContextCreateIESLight(context, self)
        context.lights.add(self)

    def set_radiant_power(self, r, g, b):
        IESLightSetRadiantPower3f(self, r, g, b)

    def set_image_from_file(self, image_path, nx, ny):
        IESLightSetImageFromFile(self, encode(image_path), nx, ny)


class PointLight(Light):
    def __init__(self, context):
        super().__init__()
        ContextCreatePointLight(context, self)
        context.lights.add(self)

    def set_radiant_power(self, r, g, b):
        PointLightSetRadiantPower3f(self, r, g, b)


class SpotLight(Light):
    def __init__(self, context):
        super().__init__()
        ContextCreateSpotLight(context, self)
        context.lights.add(self)

    def set_radiant_power(self, r, g, b):
        SpotLightSetRadiantPower3f(self, r, g, b)

    def set_cone_shape(self, iangle, oangle):
        SpotLightSetConeShape(self, iangle, oangle)


class DirectionalLight(Light):
    def __init__(self, context):
        super().__init__()
        ContextCreateDirectionalLight(context, self)
        context.lights.add(self)

    def set_radiant_power(self, r, g, b):
        DirectionalLightSetRadiantPower3f(self, r, g, b)

    def set_shadow_softness(self, coeff):
        DirectionalLightSetShadowSoftness(self, coeff)


class ImageBase(Object):
    core_type_name = 'rpr_image'

    def set_gamma(self, gamma):
        ImageSetGamma(self, gamma)

    def set_wrap(self, wrap_type):
        ImageSetWrap(self, wrap_type)


class Image(ImageBase):
    def __init__(self, context, data: np.array):
        super().__init__()

        components = data.shape[2]
        desc = ffi.new("rpr_image_desc*")
        desc.image_width = data.shape[1]
        desc.image_height = data.shape[0]
        desc.image_depth = 0
        desc.image_row_pitch = desc.image_width * ffi.sizeof('rpr_float') * components
        desc.image_slice_pitch = 0

        ContextCreateImage(context, (components, COMPONENT_TYPE_FLOAT32), desc, ffi.cast("float *", data.ctypes.data), self)
        context.images.add(self)


class ImageFile(ImageBase):
    def __init__(self, context, path):
        super().__init__()

        self.path = path
        ContextCreateImageFromFile(context, encode(self.path), self)
        context.images.add(self)


class Buffer(Object):
    core_type_name = 'rpr_buffer'

    def __init__(self, context, data:np.array, element_type):
        super().__init__()

        desc = ffi.new("rpr_buffer_desc*")
        desc.nb_element = len(data)
        desc.element_type = element_type
        desc.element_channel_size = len(data[0])

        ContextCreateBuffer(context, desc, ffi.cast("float *", data.ctypes.data), self)
        context.images.add(self)


class PostEffect(Object):
    core_type_name = 'rpr_post_effect'

    def __init__(self, context, post_effect_type):
        super().__init__()
        ContextCreatePostEffect(context, post_effect_type, self)
        ContextAttachPostEffect(context, self)
        context.post_effects.add(self)

    def set_parameter(self, name, param):
        if isinstance(param, int):
            PostEffectSetParameter1u(self, encode(name), param)
        elif isinstance(param, float):
            PostEffectSetParameter1f(self, encode(name), param)
        else:
            raise TypeError("Not supported parameter type", self, name, param)
