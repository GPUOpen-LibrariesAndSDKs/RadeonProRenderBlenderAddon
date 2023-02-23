#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
import platform
import traceback
import inspect
import ctypes
import time
import functools
import sys
import numpy as np
from typing import List

import bgl

import pyrprwrap
from pyrprwrap import *


class CoreError(Exception):
    def __init__(self, status, func_name, argv, module_name):
        super().__init__()
        self.status = status
        self.func_name = func_name
        self.argv = argv
        self.module_name = module_name

        for name in pyrprwrap._constants_names:
            value = getattr(pyrprwrap, name)
            if name.startswith('ERROR_') and status == value:
                status = "%s<%d>" % (name, value)
                break
       
        self.error_message = self.get_last_error_message()

    def __str__(self):
        return "%s call %s(%s) returned error code <%s> with error message: '%s'" % \
                    (self.module_name, self.func_name, ', '.join(str(a) for a in self.argv), self.status, self.error_message)

    @staticmethod
    def get_last_error_message():
        ffi = pyrprwrap.ffi
        lib = pyrprwrap.lib
        sizeParamPtr = ffi.new('size_t *', 0)

        # bypass calling ContextGetInfo through wrappers, that's why calling it directly to the lib
        state = lib.rprContextGetInfo(ffi.NULL, CONTEXT_LAST_ERROR_MESSAGE, 0, ffi.NULL, sizeParamPtr)
        sizeParam = sizeParamPtr[0]
        if state == SUCCESS and sizeParam >= 1:
            strData = ffi.new('char[%d]' % sizeParam)
            state = lib.rprContextGetInfo(ffi.NULL, CONTEXT_LAST_ERROR_MESSAGE, sizeParam, strData, ffi.NULL)
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


class _init_data:
    log_fun = None
    lib_wrapped_log_calls = False


def init(lib_dir, log_fun, lib_wrapped_log_calls):
    _init_data.log_fun = log_fun
    _init_data.lib_wrapped_log_calls = lib_wrapped_log_calls

    lib_name = {
        'Windows': "RadeonProRender64.dll",
        'Linux': "libRadeonProRender64.so",
        'Darwin': "libRadeonProRender64.dylib"
    }[platform.system()]

    ctypes.CDLL(str(lib_dir / lib_name))

    import __rpr
    try:
        lib = __rpr.lib
    except AttributeError:
        lib = __rpr.ffi.dlopen(str(lib_dir / lib_name))
    pyrprwrap.lib = lib
    pyrprwrap.ffi = __rpr.ffi
    global ffi
    ffi = __rpr.ffi

    _module = __import__(__name__)

    for name in pyrprwrap._constants_names:
        setattr(_module, name, getattr(pyrprwrap, name))
    
    for name in pyrprwrap._functions_names:
    
        wrapped = getattr(pyrprwrap, name)
        # wrap all functions here(for more flexilibity) to log call, if enabled
        # and to assert that SUCCESS is returned from them
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
        self._handle_ptr = ffi.new(self.core_type_name + '*', ffi.NULL)
        self.name = None

    def __del__(self):
        try:
            self.delete()
        except:
            _init_data.log_fun('EXCEPTION:', traceback.format_exc())

    def delete(self):
        if _init_data.lib_wrapped_log_calls:
            _init_data.log_fun('delete: ', self.name, self)

        if self._get_handle():
            ObjectDelete(self._get_handle())

    def _get_handle(self):
        return self._handle_ptr[0]

    def set_name(self, name):
        ObjectSetName(self._get_handle(), encode(name))
        self.name = name


class Context(Object):
    ''' Context wraps the rpr_context type with useful methods '''
    core_type_name = 'rpr_context'

    plugin_id = -1
    cache_path = None
    cpu_device = None
    gpu_devices = []

    @classmethod
    def register_plugin(cls, lib_path, cache_path):
        cls.plugin_id = RegisterPlugin(encode(str(lib_path)))
        if cls.plugin_id == -1:
            error_msg = CoreError.get_last_error_message()
            raise RuntimeError("Plugin is not registered", lib_path, error_msg)

        cls.cache_path = cache_path

    @classmethod
    def load_devices(cls):
        # getting available devices
        def get_device(create_flag, info_flag):
            try:
                context = cls(create_flag)
                device_name = context.get_info_str(info_flag)
                if not device_name:
                    return None

                return {'flag': create_flag, 'name': device_name.strip()}

            except CoreError as err:
                if err.status == ERROR_UNSUPPORTED or platform.system() == "Darwin":
                    return None

                raise err

        cls.cpu_device = get_device(CREATION_FLAGS_ENABLE_CPU, CONTEXT_CPU_NAME)
        cls.gpu_devices = []
        for i in range(16):
            create_flag = getattr(pyrprwrap, 'CREATION_FLAGS_ENABLE_GPU%d' % i)
            create_flag = create_flag if platform.system() != 'Darwin' \
                               else (create_flag | CREATION_FLAGS_ENABLE_METAL)
            device = get_device(create_flag, getattr(pyrprwrap, 'CONTEXT_GPU%d_NAME' % i))
            if not device:
                break

            cls.gpu_devices.append(device)

    def __init__(self, flags: [set, int], props: list = None, use_cache=True):
        super().__init__()
        self.aovs = {}
        self.parameters = {}

        if isinstance(flags, set):
            flags_ = 0
            for flag in flags:
                flags_ |= flag
            flags = flags_

        props_ptr = ffi.NULL
        if props is not None:
            props_ptr = ffi.new("rpr_context_properties[]",
                                [ffi.cast("rpr_context_properties", entry) for entry in props])

        if not self.cache_path.is_dir():
            self.cache_path.mkdir(parents=True)

        CreateContext(API_VERSION, [self.plugin_id], 1, flags,
            props_ptr, encode(str(self.cache_path)) if use_cache and self.cache_path else ffi.NULL,
            self)

    def set_parameter(self, key, param):
        if isinstance(param, int):
            ContextSetParameterByKey1u(self, key, param)
        elif isinstance(param, bool):
            ContextSetParameterByKey1u(self, key, int(param))
        elif isinstance(param, float):
            ContextSetParameterByKey1f(self, key, param)
        elif isinstance(param, str):
            ContextSetParameterByKeyString(self, key, encode(param))
        elif isinstance(param, tuple) and len(param) == 3:
            ContextSetParameterByKey3f(self, key, *param)
        elif isinstance(param, tuple) and len(param) == 4:
            ContextSetParameterByKey4f(self, key, *param)
        else:
            raise TypeError("Incorrect type for ContextSetParameter*", self, key, param)

        if self:
            # self could be None
            self.parameters[key] = param

    def set_scene(self, scene):
        ContextSetScene(self, scene)

    def render(self):
        ContextRender(self)

    def abort_render(self):
        ContextAbortRender(self)
        
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

    def set_aov_index_lookup(self, key, r, g, b, a):
        ContextSetAOVindexLookup(self, key, r, g, b, a)

    def get_info_size(self, context_info):
        size = ffi.new('size_t *', 0)
        ContextGetInfo(self, context_info, 0, ffi.NULL, size)
        return size[0]

    def get_info_int(self, context_info):
        ptr = ffi.new('int *', 0)
        ContextGetInfo(self, context_info, 4, ptr, ffi.NULL)
        return ptr[0]

    def get_info_str(self, context_info):
        size = self.get_info_size(context_info)
        ptr = ffi.new('char[]', size)
        ContextGetInfo(self, context_info, size, ptr, ffi.NULL)
        return decode(ffi.string(ptr))

    def get_creation_flags(self):
        creation_flags = ffi.new("rpr_creation_flags*", 0)
        ContextGetInfo(self, CONTEXT_CREATION_FLAGS, sys.getsizeof(creation_flags), creation_flags, ffi.NULL)
        return creation_flags[0]

    def get_info(self, context_info, str_type):
        val = ffi.new('%s *' % str_type)
        ContextGetInfo(self, context_info, sys.getsizeof(val), val, ffi.NULL)
        return val[0]


class Scene(Object):
    core_type_name = 'rpr_scene'

    def __init__(self, context):
        super().__init__()
        self.context = context
        self.objects = set()
        self.camera = None
        self.subdivision_camera = None
        self.environment_light = None
        self.background_image = None
        self.environment_overrides = {}
        ContextCreateScene(self.context, self)

    def delete(self):
        self.clear()
        super().delete()

    def attach(self, obj):
        if isinstance(obj, Shape):
            SceneAttachShape(self, obj)
        elif isinstance(obj, AreaLight):
            SceneAttachShape(self, obj.mesh)
        elif isinstance(obj, Light):
            SceneAttachLight(self, obj)
        elif isinstance(obj, HeteroVolume):
            SceneAttachHeteroVolume(self, obj)
        elif isinstance(obj, Curve):
            SceneAttachCurve(self, obj)
        else:
            raise TypeError("Incorrect type for SceneAttach*", self, obj)

        self.objects.add(obj)

    def detach(self, obj):
        if isinstance(obj, Shape):
            SceneDetachShape(self, obj)
        elif isinstance(obj, AreaLight):
            SceneDetachShape(self, obj.mesh)
        elif isinstance(obj, Light):
            SceneDetachLight(self, obj)
        elif isinstance(obj, HeteroVolume):
            SceneDetachHeteroVolume(self, obj)
        elif isinstance(obj, Curve):
            SceneDetachCurve(self, obj)
        else:
            raise TypeError("Incorrect type for SceneDetach*", self, obj)
 
        self.objects.remove(obj)

    def clear(self):
        self.set_background_image(None)

        for override_type in tuple(self.environment_overrides.keys()):
            self.remove_environment_override(override_type)
        if self.environment_light:
            self.remove_environment_light()

        SceneClear(self)
        self.camera = None
        self.subdivision_camera = None
        self.objects = set()

    def set_camera(self, camera):
        self.camera = camera
        SceneSetCamera(self, self.camera)

    def set_subdivision_camera(self, camera):
        """ Keep subdivision camera reference if used """
        self.subdivision_camera = camera

    def add_environment_light(self, light):
        self.environment_light = light
        self.attach(light)

    def remove_environment_light(self):
        self.detach(self.environment_light)
        self.environment_light = None

    def set_background_image(self, image):
        self.background_image = image
        SceneSetBackgroundImage(self, image)

    def set_background_color(self, r, g, b):
        self.set_background_image(
            ImageData(self.context, np.full((2, 2, 4), (r, g, b, 1.0), dtype=np.float32)))

    def add_environment_override(self, core_id, light):
        self.environment_overrides[core_id] = light
        EnvironmentLightSetEnvironmentLightOverride(self.environment_light, core_id, light)

    def remove_environment_override(self, core_id):
        EnvironmentLightSetEnvironmentLightOverride(self.environment_light, core_id, None)
        del self.environment_overrides[core_id]


class Shape(Object):
    core_type_name = 'rpr_shape'

    def __init__(self, context):
        super().__init__()
        self.context = context
        self.shadow_catcher = False
        self.reflection_catcher = False
        self.is_visible = True

        self.materials = []
        self.volume_material = None
        self.displacement_material = None
        self.hetero_volume = None

        self.subdivision = None     # { 'factor': int, 'boundary': int, 'crease_weight': float }
        self.is_portal_light = False

    def delete(self):
        if self.materials:
            self.set_material(None)
        if self.volume_material:
            self.set_volume_material(None)
        if self.displacement_material:
            self.set_displacement_material(None)
        if self.hetero_volume:
            self.set_hetero_volume(None)

        super().delete()

    def set_material(self, material):
        if self.materials:
            ShapeSetMaterial(self, None)
            self.materials.clear()

        if material:
            ShapeSetMaterial(self, material)
            self.materials.append(material)

    def set_material_faces(self, material, face_indices: np.array):
        ShapeSetMaterialFaces(self, material, ffi.cast('rpr_int*', face_indices.ctypes.data), len(face_indices))
        self.materials.append(material)

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

    def set_transform(self, transform:np.array, transpose=True): # Blender needs matrix to be transposed
        ShapeSetTransform(self, transpose, ffi.cast('float*', transform.ctypes.data))

    def set_motion_transform(self, transform:np.array, transpose=True, time_index=1): # Blender needs matrix to be transposed
        ShapeSetMotionTransform(self, transpose, ffi.cast('float*', transform.ctypes.data), time_index)

    def set_shadow_catcher(self, shadow_catcher):
        ShapeSetShadowCatcher(self, shadow_catcher)
        self.shadow_catcher = shadow_catcher

    def set_shadow_color(self, r, g, b):
        ShapeSetShadowColor(self, r, g, b)

    def set_reflection_catcher(self, reflection_catcher):
        ShapeSetReflectionCatcher(self, reflection_catcher)
        self.reflection_catcher = reflection_catcher

    def set_shadow(self, casts_shadow):
        # 1.330 removes SetShadow(), use visibility Flag.
        self.set_visibility_ex("visible.shadow", casts_shadow)

    def set_visibility(self, visible):
        self.is_visible = visible
        ShapeSetVisibility(self, visible)

    def set_visibility_ex(self, visibility_type, visible):
        flags = {
            "visible.light": SHAPE_VISIBILITY_LIGHT,
            "visible.refraction.glossy": SHAPE_VISIBILITY_GLOSSY_REFRACTION,
            "visible.reflection.glossy": SHAPE_VISIBILITY_GLOSSY_REFLECTION,
            "visible.diffuse": SHAPE_VISIBILITY_DIFFUSE,
            "visible.transparent": SHAPE_VISIBILITY_TRANSPARENT,
            "visible.refraction": SHAPE_VISIBILITY_REFRACTION,
            "visible.reflection": SHAPE_VISIBILITY_REFLECTION,
            "visible.shadow": SHAPE_VISIBILITY_SHADOW,
            "visible.receive_shadow": SHAPE_VISIBILITY_RECEIVE_SHADOW,
            "visible.primary": SHAPE_VISIBILITY_PRIMARY_ONLY_FLAG,
            }
        ShapeSetVisibilityFlag(self, flags[visibility_type], visible)

    def set_visibility_in_specular(self, visible):
        ShapeSetVisibilityInSpecular(self, visible)

    def set_visibility_primary_only(self, visible):
        ShapeSetVisibilityFlag(self, SHAPE_VISIBILITY_PRIMARY_ONLY_FLAG, visible)

    def set_subdivision_factor(self, factor):
        ShapeSetSubdivisionFactor(self, factor)

    def set_auto_adapt_subdivision_factor(self, framebuffer, camera, factor):
        ShapeAutoAdaptSubdivisionFactor(self, framebuffer, camera, factor)

    def set_subdivision_boundary_interop(self, boundary):
        ShapeSetSubdivisionBoundaryInterop(self, boundary)

    def set_subdivision_crease_weight(self, factor):
        ShapeSetSubdivisionCreaseWeight(self, factor)

    def set_subdivision_auto_ratio_cap(self, auto_ratio_cap):
        ShapeSetSubdivisionAutoRatioCap(self, auto_ratio_cap)

    def set_light_group_id(self, group_id):
        ShapeSetLightGroupID(self, group_id)

    def set_portal_light(self, is_portal):
        self.is_portal_light = is_portal

    def mark_static(self, is_static):
        ShapeMarkStatic(self, is_static)

    def set_vertex_value(self, index: int, indices, values):
        ShapeSetVertexValue(self, index, ffi.cast("rpr_int *", indices.ctypes.data),
                            ffi.cast("float *", values.ctypes.data), len(indices))

    def set_vertex_colors(self, colors):
        indices = np.arange(len(colors), dtype=np.int32)

        # index is 0-3 index (use for r,g,b,a)
        for i in range(4):
            values = np.ascontiguousarray(colors[:, i], dtype=np.float32)
            self.set_vertex_value(i, indices, values)

    def set_id(self, id):
        ShapeSetObjectID(self, id)

    def set_contour_ignore(self, ignore_in_contour):
        ShapeSetContourIgnore(self, ignore_in_contour)


class Curve(Object):
    core_type_name = 'rpr_curve'

    def __init__(self, context, control_points, points_radii, uvs):
        def to_segments(n):
            """Index iterator which splits curve with n points to segments by 4"""
            m = n - 1
            for s in range(0, m, 3):
                yield s
                yield s + 1
                yield min(s + 2, m)
                yield min(s + 3, m)

        def iter_segments_radii():
            """ Get root and tip radii for each curve segment """
            for e in range(0, curve_length, 4):
                yield points_radii[segment_steps[e]]
                yield points_radii[segment_steps[e + 3]]

        super().__init__()
        self.context = context
        self.material = None

        num_curves = control_points.shape[0]
        segment_steps = np.fromiter(to_segments(control_points.shape[1]), dtype=np.int32)
        curve_length = len(segment_steps)

        # converting control_points to points splitted by segments
        points = np.fromiter(
            (elem for i in range(num_curves)
                  for step in segment_steps
                  for elem in control_points[i, step]),
            dtype=np.float32
        ).reshape(-1, 3)

        if uvs is None:
            uvs_ptr = ffi.NULL
        else:
            uvs_ptr = ffi.cast("float *", uvs.ctypes.data)
       
        segments_per_curve = curve_length // 4
        # create list of indices 0-control_points length
        indices = np.arange(len(points), dtype=np.uint32)

        # list full radius values for each curve
        curve_radii = np.fromiter(iter_segments_radii(), dtype=np.float32)
        radii = np.full((num_curves, len(curve_radii)), curve_radii, dtype=np.float32)

        is_tapered = not np.all(radii == curve_radii[0])

        # create list of segments per curve num_segments = length / 4
        segments = np.full(num_curves, segments_per_curve, dtype=np.int32)
        
        ContextCreateCurve(self.context, self,
            len(points), ffi.cast("float *", points.ctypes.data), points[0].nbytes,
            len(indices), num_curves,
            ffi.cast('rpr_uint*', indices.ctypes.data), ffi.cast("float *", radii.ctypes.data),
            uvs_ptr,
            ffi.cast('rpr_int*', segments.ctypes.data),
            1 if is_tapered else 0)
        
    def delete(self):
        self.set_material(None)
        super().delete()

    def set_material(self, material):
        CurveSetMaterial(self, material)
        self.material = material

    def set_transform(self, transform:np.array, transpose=True): # Blender needs matrix to be transposed
        CurveSetTransform(self, transpose, ffi.cast('float*', transform.ctypes.data))


class Mesh(Shape):
    def __init__(self, context, vertices, normals, uvs: List[np.array],
                 vertex_indices, normal_indices, uv_indices: List[np.array],
                 num_face_vertices, mesh_info):
        super().__init__(context)

        self.poly_count = 0 if vertices is None else len(num_face_vertices) 

        mesh_info_ptr = ffi.NULL
        if mesh_info:
            mesh_info_ptr = ffi.new(f"rpr_mesh_info[{2 * len(mesh_info) + 1}]")
            i = 0
            for key, val in mesh_info.items():
                mesh_info_ptr[i] = key
                mesh_info_ptr[i + 1] = val
                i += 2
            mesh_info_ptr[i] = 0

        if vertices is None:
            ContextCreateMeshEx2(
                self.context,
                ffi.NULL, 0, 0,
                ffi.NULL, 0, 0,
                ffi.NULL, 0, 0,
                0,
                ffi.NULL, ffi.NULL,
                ffi.NULL,
                ffi.NULL, 0,
                ffi.NULL, 0,
                ffi.NULL, ffi.NULL,
                ffi.NULL, 0,
                mesh_info_ptr,
                self
            )
            return

        if len(uvs) > 1 or mesh_info_ptr:
            # several UVs set present
            texcoords_layers_num = len(uvs)
            texcoords_uvs = ffi.new("float *[]", texcoords_layers_num)
            texcoords_count = np.zeros(texcoords_layers_num, dtype=np.uint64)
            texcoords_nbytes = np.zeros(texcoords_layers_num, dtype=np.int32)
            texcoords_ind = ffi.new("rpr_int *[]", texcoords_layers_num)
            texcoords_ind_nbytes = np.zeros(texcoords_layers_num, dtype=np.int32)

            for i, uvs_set in enumerate(uvs):
                texcoords_uvs[i] = ffi.cast('float *', uvs_set.ctypes.data)
                texcoords_count[i] = len(uvs_set)
                texcoords_nbytes[i] = uvs_set[0].nbytes
                texcoords_ind[i] = ffi.cast('rpr_int *', uv_indices[i].ctypes.data)
                texcoords_ind_nbytes[i] = uv_indices[i][0].nbytes

            ContextCreateMeshEx2(
                self.context,
                ffi.cast("float *", vertices.ctypes.data), len(vertices), vertices[0].nbytes,
                ffi.cast("float *", normals.ctypes.data), len(normals), normals[0].nbytes,
                ffi.NULL, 0, 0,
                texcoords_layers_num,
                texcoords_uvs, ffi.cast('size_t *', texcoords_count.ctypes.data),
                ffi.cast('rpr_int *', texcoords_nbytes.ctypes.data),
                ffi.cast('rpr_int*', vertex_indices.ctypes.data), vertex_indices[0].nbytes,
                ffi.cast('rpr_int*', normal_indices.ctypes.data), normal_indices[0].nbytes,
                texcoords_ind, ffi.cast('rpr_int*', texcoords_ind_nbytes.ctypes.data),
                ffi.cast('rpr_int*', num_face_vertices.ctypes.data), len(num_face_vertices),
                mesh_info_ptr,
                self
            )

        else:
            if uvs:
                # single UVs set
                uv = uvs[0]
                indices = uv_indices[0]
                texcoords_ptr = ffi.cast("float *", uv.ctypes.data)
                texcoords_count = len(uv)
                texcoords_nbytes = uv[0].nbytes
                texcoords_ind_ptr = ffi.cast('rpr_int*', indices.ctypes.data)
                texcoords_ind_nbytes = indices[0].nbytes
            else:
                # No UVs data found
                texcoords_ptr = ffi.NULL
                texcoords_count = 0
                texcoords_nbytes = 0
                texcoords_ind_ptr = ffi.NULL
                texcoords_ind_nbytes = 0

            ContextCreateMesh(
                self.context,
                ffi.cast("float *", vertices.ctypes.data), len(vertices), vertices[0].nbytes,
                ffi.cast("float *", normals.ctypes.data), len(normals), normals[0].nbytes,
                texcoords_ptr, texcoords_count, texcoords_nbytes,
                ffi.cast('rpr_int*', vertex_indices.ctypes.data), vertex_indices[0].nbytes,
                ffi.cast('rpr_int*', normal_indices.ctypes.data), normal_indices[0].nbytes,
                texcoords_ind_ptr, texcoords_ind_nbytes,
                ffi.cast('rpr_int*', num_face_vertices.ctypes.data), len(num_face_vertices),
                self
            )


class Instance(Shape):
    def __init__(self, context, mesh):
        super().__init__(context)
        self.mesh = mesh
        ContextCreateInstance(self.context, mesh, self)


class Grid(Object):
    """ HeteroVolume grid data """
    core_type_name = 'rpr_grid'

    def __init__(self, context):
        super().__init__()
        self.context = context

    @staticmethod
    def init_from_3d_array(context, grid_data: np.ndarray):
        grid = Grid(context)

        x, y, z = grid_data.shape
        grid_data = grid_data.reshape(-1)

        indices = np.nonzero(grid_data)[0]
        data = np.ascontiguousarray(grid_data[indices])

        ContextCreateGrid(
            grid.context, grid,
            x, y, z,
            ffi.cast('const size_t *', indices.ctypes.data), len(indices),
            GRID_INDICES_TOPOLOGY_I_U64,
            ffi.cast('const float *', data.ctypes.data), data.nbytes,
            0
        )

        return grid

    @staticmethod
    def init_from_array_indices(context, x, y, z, grid_data, indices):
        grid = Grid(context)

        ContextCreateGrid(
            grid.context, grid,
            x, y, z,
            ffi.cast('const unsigned int *', indices.ctypes.data), len(indices),
            GRID_INDICES_TOPOLOGY_XYZ_U32,
            ffi.cast('const float *', grid_data.ctypes.data), grid_data.nbytes,
            0
        )

        return grid


class HeteroVolume(Object):
    """ Heterogeneous volume voxels grid object to scatter and emit light """
    core_type_name = 'rpr_hetero_volume'

    set_grid_func = {'density': HeteroVolumeSetDensityGrid,
                     'albedo': HeteroVolumeSetAlbedoGrid,
                     'emission': HeteroVolumeSetEmissionGrid}
    set_lookup_func = {'density': HeteroVolumeSetDensityLookup,
                       'albedo': HeteroVolumeSetAlbedoLookup,
                       'emission': HeteroVolumeSetEmissionLookup}

    def __init__(self, context):
        super().__init__()
        self.context = context
        ContextCreateHeteroVolume(self.context, self)

        # keep volume grids while volume exists
        self.grids = {}

    def set_transform(self, transform: np.array, transpose=True):  # Blender needs matrix to be transposed
        HeteroVolumeSetTransform(self, transpose, ffi.cast('float*', transform.ctypes.data))

    def set_grid(self, grid_type, grid):
        self.set_grid_func[grid_type](self, grid)
        self.grids[grid_type] = grid

    def set_lookup(self, grid_type, lookup: np.array):
        self.set_lookup_func[grid_type](self, ffi.cast('const float *', lookup.ctypes.data),
                                        len(lookup))


class Camera(Object):
    core_type_name = 'rpr_camera'

    def __init__(self, context):
        super().__init__()
        self.context = context
        ContextCreateCamera(self.context, self)

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
        if fstop is None:
            # if disabled fstop will be max float
            CameraSetFStop(self, np.finfo(np.float32).max)
        else:
            CameraSetFStop(self, fstop)

    def set_aperture_blades(self, num_blades):
        CameraSetApertureBlades(self, num_blades)

    def set_focus_distance(self, fdist):
        CameraSetFocusDistance(self, fdist)

    def set_ortho(self, width, height):
        CameraSetOrthoWidth(self, width)
        CameraSetOrthoHeight(self, height)

    def set_motion_transform(self, transform:np.array, transpose=True, time_index = 1): # Blender needs matrix to be transposed
        CameraSetMotionTransform(self, transpose, ffi.cast('float*', transform.ctypes.data), time_index)

    def set_exposure(self, exposure):
        CameraSetExposure(self, exposure)

    def set_clip_plane(self, near, far):
        CameraSetNearPlane(self, near)
        CameraSetFarPlane(self, far)

    def set_transform(self, transform:np.array, transpose=True): # Blender needs matrix to be transposed
        CameraSetTransform(self, transpose, ffi.cast('float*', transform.ctypes.data))


class FrameBuffer(Object):
    core_type_name = 'rpr_framebuffer'
    channels = 4    # core requires always 4 channels

    def __init__(self, context, width, height):
        super().__init__()
        self.context = context
        self.width = width
        self.height = height
        self.aov = None
        self._create()

    def delete(self):
        if self.aov is not None:
            self.context.detach_aov(self.aov)
             
        return super().delete()

    def _create(self):
        desc = ffi.new("rpr_framebuffer_desc*")
        desc.fb_width, desc.fb_height = self.width, self.height
        ContextCreateFrameBuffer(self.context, (self.channels, COMPONENT_TYPE_FLOAT32), desc, self)

    def resize(self, width, height):
        if self.width == width and self.height == height:
            return

        aov = self.aov
        self.delete()

        self.width = width
        self.height = height
        self._create()

        if aov is not None:
            self.context.attach_aov(aov, self)

    def clear(self):
        FrameBufferClear(self)

    def resolve(self, resolved_fb, normalize_only=True):
        ContextResolveFrameBuffer(self.context, self, resolved_fb, normalize_only)
        
    def get_data(self, buf=None):
        if buf:
            FrameBufferGetInfo(self, FRAMEBUFFER_DATA, self.size(), ffi.cast('float*', buf), ffi.NULL)
            return buf

        data = np.empty((self.height, self.width, self.channels), dtype=np.float32)
        FrameBufferGetInfo(self, FRAMEBUFFER_DATA, self.size(), ffi.cast('float*', data.ctypes.data), ffi.NULL)
        return data

    def size(self):
        return self.width * self.height * self.channels * 4    # 4 bytes = sizeof(float32)

    def save_to_file(self, file_path):
        FrameBufferSaveToFile(self, encode(file_path))

    def get_cl_mem(self):
        cl_mem = ffi.new('rpr_cl_mem *')
        FrameBufferGetInfo(self, CL_MEM_OBJECT, sys.getsizeof(cl_mem), cl_mem, ffi.NULL)
        return cl_mem[0]


class FrameBufferGL(FrameBuffer):
    def __init__(self, context, width, height):
        super().__init__(context, width, height)

    def _create(self):
        textures = bgl.Buffer(bgl.GL_INT, [1,])
        bgl.glGenTextures(1, textures)
        self.texture_id = textures[0]

        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.texture_id)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_S, bgl.GL_REPEAT)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_T, bgl.GL_REPEAT)

        bgl.glTexImage2D(
            bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA if platform.system() == 'Darwin' else bgl.GL_RGBA16F,
            self.width, self.height, 0,
            bgl.GL_RGBA, bgl.GL_FLOAT,
            bgl.Buffer(bgl.GL_FLOAT, [self.width, self.height, self.channels])
        )

        ContextCreateFramebufferFromGLTexture2D(self.context, bgl.GL_TEXTURE_2D, 0, self.texture_id, self)

    def delete(self):
        super().delete()
        textures = bgl.Buffer(bgl.GL_INT, [1,], [self.texture_id, ])
        bgl.glDeleteTextures(1, textures)


class Composite(Object):
    core_type_name = 'rpr_composite'

    def __init__(self, context, in_type):
        super().__init__()
        self.context = context
        self.inputs = {}
        ContextCreateComposite(self.context, in_type, self)

    def set_input(self, name, in_value):
        if name == 'arithmetic.op':
            CompositeSetInputOp(self, encode(name), in_value)
        elif isinstance(in_value, int):
            CompositeSetInput1u(self, encode(name), in_value)
        elif isinstance(in_value, float):
            CompositeSetInput4f(self, encode(name), in_value, in_value, in_value, in_value)
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

    ### MATH OPERATIONS ###
    def _arithmetic_helper(self, rpr_operation, other1=None, other2=None, reverse=False):
        result = Composite(self.context, COMPOSITE_ARITHMETIC)
        result.set_input('arithmetic.op', rpr_operation)

        if other1 is None:
            result.set_input('arithmetic.color0', self)

        else:
            if isinstance(other1, (float, tuple)):
                data = other1
                other1 = Composite(self.context, COMPOSITE_CONSTANT)
                other1.set_input('constant.input', data)

            if other2 is None:
                if reverse:
                    result.set_input('arithmetic.color0', other1)
                    result.set_input('arithmetic.color1', self)
                else:
                    result.set_input('arithmetic.color0', self)
                    result.set_input('arithmetic.color1', other1)

            else:
                if isinstance(other2, (float, tuple)):
                    data = other2
                    other2 = Composite(self.context, COMPOSITE_CONSTANT)
                    other2.set_input('constant.input', data)

                result.set_input('arithmetic.color0', self)
                result.set_input('arithmetic.color1', other1)
                result.set_input('arithmetic.color1', other2)

        return result

    def __add__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_ADD, other)

    def __sub__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_SUB, other)

    def __mul__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_MUL, other)

    def __truediv__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_DIV, other)

    def __radd__(self, other):
        return self + other

    def __rsub__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_SUB, other, None, True)

    def __rmul__(self, other):
        return self * other

    def __rtruediv__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_DIV, other, None, True)

    def min(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_MIN, other)

    def max(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_MAX, other)

    def get_channel(self, key):
        rpr_operation = {
            0: MATERIAL_NODE_OP_SELECT_X,
            1: MATERIAL_NODE_OP_SELECT_Y,
            2: MATERIAL_NODE_OP_SELECT_Z,
            3: MATERIAL_NODE_OP_SELECT_W,
        }[key]

        return self._arithmetic_helper(rpr_operation)

    def __gt__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_GREATER, other)

    def __ge__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_GREATER_OR_EQUAL, other)

    def __lt__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_LOWER, other)

    def __le__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_LOWER_OR_EQUAL, other)

    def __eq__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_EQUAL, other)

    def __ne__(self, other):
        return self._arithmetic_helper(MATERIAL_NODE_OP_NOT_EQUAL, other)

    def if_else(self, if_value, else_value):
        return self._arithmetic_helper(MATERIAL_NODE_OP_TERNARY, if_value, else_value)


class MaterialSystem(Object):
    core_type_name = 'rpr_material_system'

    def __init__(self, context):
        super().__init__()
        self.context = context
        ContextCreateMaterialSystem(self.context, 0, self)


class MaterialNode(Object):
    core_type_name = 'rpr_material_node'

    def __init__(self, material_system, material_type):
        super().__init__()
        self.material_system = material_system
        self.inputs = {}
        self.type = material_type
        MaterialSystemCreateNode(self.material_system, self.type, self)

    def delete(self):
        for name, value in self.inputs.items():
            if isinstance(value, MaterialNode):
                MaterialNodeSetInputNByKey(self, name, None)
            elif isinstance(value, Image):
                MaterialNodeSetInputImageDataByKey(self, name, None)
            elif isinstance(value, Buffer):
                MaterialNodeSetInputBufferDataByKey(self, name, None)
            elif isinstance(value, Grid):
                MaterialNodeSetInputGridDataByKey(self, name, None)
        self.inputs.clear()

        super().delete()

    def set_input(self, name, value):
        if isinstance(value, MaterialNode):
            MaterialNodeSetInputNByKey(self, name, value)
        elif isinstance(value, int):
            MaterialNodeSetInputUByKey(self, name, value)
        elif isinstance(value, bool):
            MaterialNodeSetInputUByKey(self, name, TRUE if value else FALSE)
        elif isinstance(value, float):
            MaterialNodeSetInputFByKey(self, name, value, value, value, value)
        elif isinstance(value, tuple) and len(value) == 3:
            MaterialNodeSetInputFByKey(self, name, *value, 1.0)
        elif isinstance(value, tuple) and len(value) == 4:
            MaterialNodeSetInputFByKey(self, name, *value)
        elif isinstance(value, Image):
            MaterialNodeSetInputImageDataByKey(self, name, value)
        elif isinstance(value, Buffer):
            MaterialNodeSetInputBufferDataByKey(self, name, value)
        elif isinstance(value, Grid):
            MaterialNodeSetInputGridDataByKey(self, name, value)
        elif isinstance(value, Light):
            MaterialNodeSetInputLightDataByKey(self, name, value)
        else:
            raise TypeError("Incorrect type for MaterialNodeSetInput*", self, name, value)

        self.inputs[name] = value

    def set_id(self, id):
        MaterialNodeSetID(self, id)


class Light(Object):
    core_type_name = 'rpr_light'

    def __init__(self, context):
        super().__init__()
        self.context = context

    def set_transform(self, transform:np.array, transpose=True): # Blender needs matrix to be transposed
        LightSetTransform(self, transpose, ffi.cast('float*', transform.ctypes.data))

    def set_group_id(self, group_id):
        LightSetGroupId(self, group_id)


class EnvironmentLight(Light):
    def __init__(self, context):
        super().__init__(context)
        self.portals = set()
        self.image = None
        ContextCreateEnvironmentLight(self.context, self)

    def delete(self):
        super().delete()

    def set_image(self, image):
        self.image = image
        if not self.image:
            self.set_color(1.0, 0.0, 1.0)
            return

        EnvironmentLightSetImage(self, image)

    def set_color(self, r, g, b):
        self.set_image(ImageData(self.context, np.full((2, 2, 4), (r, g, b, 1.0), dtype=np.float32)))

    def set_intensity_scale(self, intensity_scale):
        EnvironmentLightSetIntensityScale(self, intensity_scale)

    def attach_portal(self, scene, portal):
        self.portals.add(portal)
        EnvironmentLightAttachPortal(scene, self, portal)

    def detach_portal(self, scene, portal):
        EnvironmentLightDetachPortal(scene, self, portal)
        self.portals.remove(portal)


class IESLight(Light):
    def __init__(self, context):
        super().__init__(context)
        ContextCreateIESLight(self.context, self)

    def set_radiant_power(self, r, g, b):
        IESLightSetRadiantPower3f(self, r, g, b)

    def set_image_from_file(self, image_path, nx, ny):
        IESLightSetImageFromFile(self, encode(image_path), nx, ny)

    def set_transform(self, transform: np.array, transpose=True):
        # transform matrix has to be rotated by 90 degrees around X axis
        rot = np.array(((1, 0, 0, 0),
                        (0, 0, -1, 0),
                        (0, 1, 0, 0),
                        (0, 0, 0, 1)), dtype=np.float32)
        transform_rot = transform @ rot
        LightSetTransform(self, transpose, ffi.cast('float*', transform_rot.ctypes.data))


class PointLight(Light):
    def __init__(self, context):
        super().__init__(context)
        ContextCreatePointLight(self.context, self)

    def set_radiant_power(self, r, g, b):
        PointLightSetRadiantPower3f(self, r, g, b)

    def set_radius(self, radius):
        """ Supported in RPR 2.0 Sphere Light """
        pass


class SpotLight(Light):
    def __init__(self, context):
        super().__init__(context)
        ContextCreateSpotLight(self.context, self)

    def set_radiant_power(self, r, g, b):
        SpotLightSetRadiantPower3f(self, r, g, b)

    def set_cone_shape(self, iangle, oangle):
        SpotLightSetConeShape(self, iangle, oangle)

    def set_radius(self, radius):
        """ Supported in RPR 2.0 Disk Light """
        pass


class DirectionalLight(Light):
    def __init__(self, context):
        super().__init__(context)
        ContextCreateDirectionalLight(self.context, self)

    def set_radiant_power(self, r, g, b):
        DirectionalLightSetRadiantPower3f(self, r, g, b)

    def set_shadow_softness_angle(self, angle):
        DirectionalLightSetShadowSoftnessAngle(self, angle)


class AreaLight(Light):
    core_type_name = ''

    def __init__(self, mesh, material_system):
        self.mesh = mesh
        self.material_system = material_system

        self.color_node = MaterialNode(self.material_system, MATERIAL_NODE_ARITHMETIC)
        self.color_node.set_input(MATERIAL_INPUT_OP, MATERIAL_NODE_OP_MUL)
        self.color_node.set_input(MATERIAL_INPUT_COLOR0, 1.0)    # for color
        self.color_node.set_input(MATERIAL_INPUT_COLOR1, 1.0)    # for image

        emissive_node = MaterialNode(self.material_system, MATERIAL_NODE_EMISSIVE)
        emissive_node.set_input(MATERIAL_INPUT_COLOR, self.color_node)

        self.mesh.set_material(emissive_node)

    def delete(self):
        # delete() should be empty
        pass

    def set_name(self, name):
        self.name = name
        self.mesh.set_name(name)

    def set_radiant_power(self, r, g, b):
        self.color_node.set_input(MATERIAL_INPUT_COLOR0, (r, g, b))

    def set_image(self, image):
        if image:
            image_node = MaterialNode(self.material_system, MATERIAL_NODE_IMAGE_TEXTURE)
            image_node.set_input(MATERIAL_INPUT_DATA, image)
            self.color_node.set_input(MATERIAL_INPUT_COLOR1, image_node)
        else:
            self.color_node.set_input(MATERIAL_INPUT_COLOR1, 1.0)

    def set_shadow(self, casts_shadow):
        self.mesh.set_shadow(casts_shadow)

    def set_visibility(self, visible):
        self.mesh.set_visibility_ex('visible.light', visible)
        self.mesh.set_visibility_ex('visible.primary', visible)

    def set_transform(self, transform:np.array, transpose=True): # Blender needs matrix to be transposed
        self.mesh.set_transform(transform, transpose)

    def set_group_id(self, group_id):
        self.mesh.set_light_group_id(group_id)

    def set_motion_transform(self, transform:np.array, transpose=True, time_index=1):
        self.mesh.set_motion_transform(transform, transpose, time_index)


class Image(Object):
    core_type_name = 'rpr_image'

    def __init__(self, context):
        super().__init__()
        self.context = context
        self._size_byte = None

    def set_gamma(self, gamma):
        ImageSetGamma(self, gamma)

    def set_wrap(self, wrap_type):
        ImageSetWrap(self, wrap_type)

    def set_colorspace(self, colorspace):
        ImageSetOcioColorspace(self, encode(colorspace))

    def set_compression(self, compression):
        ImageSetInternalCompression(self, compression)

    @property
    def size_byte(self):
        if self._size_byte is None:
            ptr = ffi.new('long long *', 0)
            ImageGetInfo(self, IMAGE_DATA_SIZEBYTE, 8, ptr, ffi.NULL)
            self._size_byte = ptr[0]

        return self._size_byte


class ImageData(Image):
    def __init__(self, context, data: np.array):
        super().__init__(context)

        components = data.shape[2]
        desc = ffi.new("rpr_image_desc*")
        desc.image_width = data.shape[1]
        desc.image_height = data.shape[0]
        desc.image_depth = 0
        desc.image_row_pitch = desc.image_width * ffi.sizeof('rpr_float') * components
        desc.image_slice_pitch = 0

        ContextCreateImage(self.context, (components, COMPONENT_TYPE_FLOAT32), desc, ffi.cast("float *", data.ctypes.data), self)


class ImageFile(Image):
    def __init__(self, context, path):
        super().__init__(context)

        self.path = path
        ContextCreateImageFromFile(self.context, encode(self.path), self)


class Buffer(Object):
    core_type_name = 'rpr_buffer'

    def __init__(self, context, data:np.array, element_type):
        super().__init__()
        self.context = context

        desc = ffi.new("rpr_buffer_desc*")
        desc.nb_element = len(data)
        desc.element_type = element_type
        desc.element_channel_size = len(data[0])

        ContextCreateBuffer(self.context, desc, ffi.cast("float *", data.ctypes.data), self)


class PostEffect(Object):
    core_type_name = 'rpr_post_effect'

    def __init__(self, context, post_effect_type):
        super().__init__()
        self.context = context
        ContextCreatePostEffect(self.context, post_effect_type, self)
        ContextAttachPostEffect(self.context, self)

    def delete(self):
        ContextDetachPostEffect(self.context, self)
        super().delete()

    def set_parameter(self, name, param):
        if isinstance(param, int):
            PostEffectSetParameter1u(self, encode(name), param)
        elif isinstance(param, float):
            PostEffectSetParameter1f(self, encode(name), param)
        else:
            raise TypeError("Not supported parameter type", self, name, param)
