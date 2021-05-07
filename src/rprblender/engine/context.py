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
import threading

import pyrpr
import pyrpr2

class RPRContext:
    """ Manager of pyrpr calls """

    # Classes
    _Context = pyrpr.Context
    _Scene = pyrpr.Scene

    _MaterialNode = pyrpr.MaterialNode

    _PointLight = pyrpr.PointLight
    _SphereLight = pyrpr.PointLight  # RPR 2.0 only feature, use PointLight instead
    _DirectionalLight = pyrpr.DirectionalLight
    _SpotLight = pyrpr.SpotLight
    _DiskLight = pyrpr.SpotLight
    _IESLight = pyrpr.IESLight
    _AreaLight = pyrpr.AreaLight
    _EnvironmentLight = pyrpr.EnvironmentLight

    _Camera = pyrpr.Camera
    _Mesh = pyrpr.Mesh
    _Instance = pyrpr.Instance
    _Curve = pyrpr.Curve
    _HeteroVolume = pyrpr.HeteroVolume
    _Grid = pyrpr.Grid

    _PostEffect = pyrpr.PostEffect

    def __init__(self):
        self.context = None
        self.material_system = None
        self.width = None
        self.height = None
        self.gl_interop = None
        self.engine_type = None

        # Here we'll store some useful blender data, which could be required to do some export
        self.blender_data = {}

        # scene and objects
        self.scene = None
        self.objects = {}
        self.curves = {}
        self.volumes = {}

        self.do_motion_blur = False
        self.engine_type = None

        # TODO: probably better make nodes more close to materials in one data structure
        self.material_nodes = {}
        self.materials = {}

        self.images = {}
        self.post_effect = None

        # list of frame buffers for AOVs
        self.frame_buffers_aovs = {}

        # shadow and reflection catchers
        self.composite = None
        self.use_shadow_catcher = False
        self.use_reflection_catcher = False
        self.use_transparent_background = False

        # texture compression used when images created
        self.texture_compression = False

    def init(self, context_flags, context_props, use_contour_integrator=False):
        self.context = self._Context(context_flags, context_props)
        self.material_system = pyrpr.MaterialSystem(self.context)
        self.gl_interop = pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP in context_flags

        # context settings
        self.set_parameter(pyrpr.CONTEXT_X_FLIP, False)
        self.set_parameter(pyrpr.CONTEXT_Y_FLIP, False)
        self.set_parameter(pyrpr.CONTEXT_DISPLAY_GAMMA, 1.0)

        #if helpers.use_mps():
        #    self.context.set_parameter('metalperformanceshader', True)
        #self.context.set_parameter('ooctexcache', helpers.get_ooc_cache_size(is_preview))

        if use_contour_integrator:
            self.context.set_parameter(pyrpr.CONTEXT_GPUINTEGRATOR, "gpucontour")

        self.post_effect = self._PostEffect(self.context, pyrpr.POST_EFFECT_NORMALIZATION)

        self.scene = self._Scene(self.context)
        self.context.set_scene(self.scene)

    def __del__(self):
        if self.context:
            self.disable_aovs()

    def clear_frame_buffers(self):
        for fbs in self.frame_buffers_aovs.values():
            fbs['aov'].clear()

    def clear_scene(self):
        self.scene.clear()

        self.objects = {}
        self.curves = {}
        self.volumes = {}

        self.material_nodes = {}
        self.materials = {}

        self.images = {}

    def render(self, restart=False, tile=None):
        if restart:
            self.clear_frame_buffers()

        if tile is None:
            self.context.render()
        else:
            self.context.render_tile(*tile)

    def abort_render(self):
        self.context.abort_render()

    def get_image(self, aov_type=None):
        return self.get_frame_buffer(aov_type).get_data()

    def get_frame_buffer(self, aov_type=None):
        if aov_type is not None:
            return self.frame_buffers_aovs[aov_type]['res']

        if self.gl_interop:
            return self.frame_buffers_aovs[pyrpr.AOV_COLOR]['gl']

        if self.composite:
            return self.frame_buffers_aovs[pyrpr.AOV_COLOR]['composite']

        return self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res']

    def resolve(self, aovs=None):
        if aovs:
            for aov in aovs:
                fbs = self.frame_buffers_aovs[aov]
                fbs['aov'].resolve(fbs['res'], aov != pyrpr.AOV_SHADOW_CATCHER)
        else:
            for aov, fbs in self.frame_buffers_aovs.items():
                fbs['aov'].resolve(fbs['res'], aov != pyrpr.AOV_SHADOW_CATCHER)

        if self.composite:
            if aovs and pyrpr.AOV_COLOR not in aovs:
                return

            color_aov = self.frame_buffers_aovs[pyrpr.AOV_COLOR]
            self.composite.compute(color_aov['composite'])
            if self.gl_interop:
                color_aov['composite'].resolve(color_aov['gl'])

    def enable_aov(self, aov_type):
        if self.is_aov_enabled(aov_type):
            return

        fbs = {}
        fbs['aov'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
        fbs['aov'].set_name("%d_aov" % aov_type)
        self.context.attach_aov(aov_type, fbs['aov'])
        if aov_type == pyrpr.AOV_COLOR and self.gl_interop:
            fbs['res'] = pyrpr.FrameBufferGL(self.context, self.width, self.height)
            fbs['gl'] = fbs['res']      # resolved and gl framebuffers are the same
            fbs['gl'].set_name("%d_gl" % aov_type)
        else:
            fbs['res'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
            fbs['res'].set_name("%d_res" % aov_type)

        self.frame_buffers_aovs[aov_type] = fbs

    def disable_aov(self, aov_type):
        self.context.detach_aov(aov_type)
        del self.frame_buffers_aovs[aov_type]

    def disable_aovs(self):
        for aov_type in tuple(self.frame_buffers_aovs.keys()):
            self.disable_aov(aov_type)

    def is_aov_enabled(self, aov_type):
        return aov_type in self.frame_buffers_aovs

    def set_aov_index_lookup(self, key, r, g, b, a):
        self.context.set_aov_index_lookup(key, r, g, b, a)

    def resize(self, width, height):
        self.width = width
        self.height = height

        composite = self.composite is not None
        if composite:
            self._disable_catchers()

        for fbs in self.frame_buffers_aovs.values():
            for fb in fbs.values():
                fb.resize(self.width, self.height)

        if composite:
            self._enable_catchers()

    def sync_catchers(self, use_transparent_background=None):
        prev_state = (self.use_shadow_catcher, self.use_reflection_catcher,
                      self.use_transparent_background)

        self.use_shadow_catcher = False
        self.use_reflection_catcher = False
        if self.use_transparent_background is not None:
            self.use_transparent_background = use_transparent_background
        for obj in self.scene.objects:
            if not self.use_shadow_catcher and isinstance(obj, pyrpr.Shape) and obj.shadow_catcher:
                self.use_shadow_catcher = True
            if not self.use_reflection_catcher and isinstance(obj, pyrpr.Shape) and obj.reflection_catcher:
                self.use_reflection_catcher = True
            # break early if both catchers were found
            if self.use_shadow_catcher and self.use_reflection_catcher:
                break

        state = (self.use_shadow_catcher, self.use_reflection_catcher,
                 self.use_transparent_background)
        if prev_state != state:
            if self.composite:
                self._disable_catchers()

            if any(state):
                self._enable_catchers()

            return True

        return False

    def _enable_catchers(self):
        # Experimentally found the max value of shadow catcher,
        # we'll need it to normalize shadow catcher AOV
        SHADOW_CATCHER_MAX_VALUE = 2.0

        # Enable required AOVs
        self.enable_aov(pyrpr.AOV_COLOR)
        self.enable_aov(pyrpr.AOV_OPACITY)
        self.enable_aov(pyrpr.AOV_BACKGROUND)
        if self.use_shadow_catcher:
            self.enable_aov(pyrpr.AOV_SHADOW_CATCHER)
        if self.use_reflection_catcher:
            self.enable_aov(pyrpr.AOV_REFLECTION_CATCHER)

        # Composite frame buffer
        self.frame_buffers_aovs[pyrpr.AOV_COLOR]['composite'] = pyrpr.FrameBuffer(
            self.context, self.width, self.height)
        self.frame_buffers_aovs[pyrpr.AOV_COLOR]['composite'].set_name('default_composite')
        if self.gl_interop:
            # splitting resolved and gl framebuffers
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = pyrpr.FrameBuffer(
                self.context, self.width, self.height)
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'].set_name('default_res')

        # Composite calculation elements frame buffers
        color = self.create_composite(pyrpr.COMPOSITE_FRAMEBUFFER, {
            'framebuffer.input': self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res']
        })

        alpha = self.create_composite(pyrpr.COMPOSITE_FRAMEBUFFER, {
            'framebuffer.input': self.frame_buffers_aovs[pyrpr.AOV_OPACITY]['res']
        }).get_channel(0)
        full_alpha = alpha

        if self.use_reflection_catcher or self.use_shadow_catcher:
            if self.use_reflection_catcher:
                reflection_catcher = self.create_composite(pyrpr.COMPOSITE_FRAMEBUFFER, {
                    'framebuffer.input': self.frame_buffers_aovs[pyrpr.AOV_REFLECTION_CATCHER][
                        'res']
                }).get_channel(0)
                full_alpha += reflection_catcher

            background = self.create_composite(pyrpr.COMPOSITE_FRAMEBUFFER, {
                'framebuffer.input': self.frame_buffers_aovs[pyrpr.AOV_BACKGROUND]['res']
            })

            self.composite = background * (1.0 - full_alpha) + color * full_alpha

            if self.use_shadow_catcher:
                shadow_catcher = self.create_composite(pyrpr.COMPOSITE_FRAMEBUFFER, {
                    'framebuffer.input': self.frame_buffers_aovs[pyrpr.AOV_SHADOW_CATCHER]['res']
                }).get_channel(0)
                shadow_catcher_norm = (shadow_catcher / SHADOW_CATCHER_MAX_VALUE).min(1.0)

                self.composite *= (1.0 - shadow_catcher_norm) * (1.0, 1.0, 1.0, 0.0) + \
                                  (0.0, 0.0, 0.0, 1.0)

                if self.use_transparent_background:
                    full_alpha = (full_alpha + shadow_catcher_norm).min(1.0)

        else:
            self.composite = color

        if self.use_transparent_background:
            self.composite = full_alpha * ((0.0, 0.0, 0.0, 1.0) + self.composite * (1.0, 1.0, 1.0, 0.0))

    def _disable_catchers(self):
        self.composite = None
        if self.gl_interop:
            # set resolved framebuffer be the same as gl
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = self.frame_buffers_aovs[pyrpr.AOV_COLOR]['gl']
        del self.frame_buffers_aovs[pyrpr.AOV_COLOR]['composite']

    def sync_auto_adapt_subdivision(self, width=0, height=0):
        camera = self.scene.subdivision_camera
        if not camera:
            camera = self.scene.camera
        if width == 0:
            width = self.width
        if height == 0:
            height = self.height

        objects_with_adaptive_subdivision = self._get_adaptive_subdivision_objects()

        if not objects_with_adaptive_subdivision:
            return

        fb = self.frame_buffers_aovs[pyrpr.AOV_COLOR]['aov']
        if fb.width != width or fb.height != height:
            # creating temporary FrameBuffer of required size only to set subdivision
            fb = pyrpr.FrameBuffer(self.context, width, height)

        for obj in objects_with_adaptive_subdivision:
            obj.set_auto_adapt_subdivision_factor(fb, camera, obj.subdivision['factor'])
            obj.set_subdivision_boundary_interop(obj.subdivision['boundary'])
            obj.set_subdivision_crease_weight(obj.subdivision['crease_weight'])

    def _get_adaptive_subdivision_objects(self):
        return tuple(obj for obj in self.scene.objects
                     if isinstance(obj, pyrpr.Shape) and obj.subdivision is not None)

    def sync_portal_lights(self):
        """ Attach active Portal Light objects to active environment light """
        light = self.scene.environment_light
        if not light:
            return

        portals = set(obj for obj in self.scene.objects if isinstance(obj, pyrpr.Shape) and obj.is_portal_light)
        # detach disabled portals
        for obj in light.portals - portals:
            light.detach_portal(self.scene, obj)

        # attach added portal lights
        for obj in portals - light.portals:
            light.attach_portal(self.scene, obj)

    #
    # OBJECT'S CREATION FUNCTIONS
    #
    def create_empty_object(self, key):
        self.objects[key] = None
        return None

    def create_light(self, key, light_type):
        if light_type == 'point':
            light = self._PointLight(self.context)
        elif light_type == 'sphere':
            light = self._SphereLight(self.context)
        elif light_type == 'spot':
            light = self._SpotLight(self.context)
        elif light_type == 'disk':
            light = self._DiskLight(self.context)
        elif light_type == 'directional':
            light = self._DirectionalLight(self.context)
        elif light_type == 'ies':
            light = self._IESLight(self.context)
        else:
            raise KeyError("No such light type", light_type)

        self.objects[key] = light
        return light

    def create_environment_light(self):
        return self._EnvironmentLight(self.context)

    def create_area_light(
            self, key,
            vertices, normals, uvs,
            vertex_indices, normal_indices, uv_indices,
            num_face_vertices
    ):
        mesh = self._Mesh(
            self.context,
            vertices, normals, uvs,
            vertex_indices, normal_indices, uv_indices,
            num_face_vertices
        )
        light = self._AreaLight(mesh, self.material_system)
        self.objects[key] = light
        return light

    def create_mesh(
            self, key,
            vertices, normals, uvs,
            vertex_indices, normal_indices, uv_indices,
            num_face_vertices
    ):
        mesh = self._Mesh(
            self.context,
            vertices, normals, uvs,
            vertex_indices, normal_indices, uv_indices,
            num_face_vertices
        )
        self.objects[key] = mesh
        return mesh

    def create_instance(self, key, mesh):
        instance = self._Instance(self.context, mesh)
        self.objects[key] = instance
        return instance

    def create_curve(self, key, control_points, points_radii, uvs):
        curve = self._Curve(self.context, control_points, points_radii, uvs)
        self.curves[key] = curve
        return curve

    def create_hetero_volume(self, key):
        volume = self._HeteroVolume(self.context)
        self.volumes[key] = volume
        return volume

    def create_camera(self, key=None):
        camera = self._Camera(self.context)
        if key:
            self.objects[key] = camera
        return camera

    def create_material_node(self, material_type):
        return self._MaterialNode(self.material_system, material_type)

    def set_material_node_key(self, key, material_node):
        self.material_nodes[key] = material_node

    def set_material_node_as_material(self, key, material_node):
        self.materials[key] = material_node

    def create_image_file(self, key, filepath):
        image = pyrpr.ImageFile(self.context, filepath)
        image.set_compression(self.texture_compression)
        if key:
            self.images[key] = image
        return image

    def create_image_data(self, key, data):
        image = pyrpr.ImageData(self.context, data)
        image.set_compression(self.texture_compression)
        if key:
            self.images[key] = image
        return image

    def create_tiled_image(self, key):
        # Tiled images are unsupported by Tahoe
        return None

    def create_buffer(self, data, dtype):
        return pyrpr.Buffer(self.context, data, dtype)

    def create_composite(self, in_type, inputs=None):
        composite = pyrpr.Composite(self.context, in_type)
        if inputs:
            for key, value in inputs.items():
                composite.set_input(key, value)

        return composite

    def create_grid_from_3d_array(self, data):
        return self._Grid.init_from_3d_array(self.context, data)

    def create_grid_from_array_indices(self, x, y, z, data, indices):
        return self._Grid.init_from_array_indices(self.context, x, y, z, data, indices)

    def set_parameter(self, key, param):
        if param == self.context.parameters.get(key, None):
            return False

        self.context.set_parameter(key, param)
        return True

    def get_parameter(self, name, default=None):
        return self.context.parameters.get(name, default)

    def get_info(self, context_info: int, value_type: type):
        if value_type is int:
            return self.context.get_info_int(context_info)

        if value_type is str:
            return self.context.get_info_str(context_info)

        raise ValueError("Incorrect value_type for RPRContext.get_info", value_type)

    def remove_object(self, key):
        obj = self.objects[key]

        if isinstance(obj, pyrpr.Mesh):
            # removing and detaching related instances
            instance_keys = tuple(k for k in self.objects.keys()
                                    if isinstance(k, tuple) and k[0] == key)
            for k in instance_keys:
                instance = self.objects.pop(k)
                self.scene.detach(instance)

        self.remove_curves(key)
        self.remove_volumes(key)

        if isinstance(obj, pyrpr.Mesh):
            # checking if object has direct instances,
            # in this case we don't remove/detach object, just hiding it
            has_instances = next((True for o in self.objects.values()
                                       if isinstance(o, pyrpr.Instance) and o.mesh is obj), False)
            if has_instances:
                obj.set_visibility(False)
                return

        if obj:
            self.scene.detach(obj)

        del self.objects[key]

    def remove_curves(self, base_obj_key):
        keys = tuple(k for k in self.curves.keys() if k[0] == base_obj_key)
        for k in keys:
            particle = self.curves.pop(k)
            self.scene.detach(particle)

    def has_curves(self, base_obj_key):
        return bool(next((k for k in self.curves.keys() if k[0] == base_obj_key), None))

    def remove_volumes(self, base_obj_key):
        keys = tuple(k for k in self.volumes.keys() if k[0] == base_obj_key)
        for k in keys:
            volume = self.volumes.pop(k)
            self.scene.detach(volume)

    def has_volumes(self, base_obj_key):
        return bool(next((k for k in self.volumes.keys() if k[0] == base_obj_key), None))

    def remove_image(self, key):
        del self.images[key]

    def remove_material(self, key):
        # removing child materials
        for mat_key in tuple(self.materials.keys()):
            if isinstance(mat_key, tuple) and mat_key[0] == key:
                self.remove_material(mat_key)

        # removing all corresponded nodes
        for node_key in tuple(self.material_nodes.keys()):
            if node_key[0] == key:
                del self.material_nodes[node_key]

        del self.materials[key]


class RPRContext2(RPRContext):
    """ Manager of pyrpr calls """

    # Classes
    _Context = pyrpr2.Context

    _Mesh = pyrpr2.Mesh
    _Instance = pyrpr2.Instance

    _AreaLight = pyrpr2.AreaLight
    _SphereLight = pyrpr2.SphereLight
    _DiskLight = pyrpr2.DiskLight
    _PostEffect = pyrpr2.PostEffect

    def init(self, context_flags, context_props, use_contour_integrator=False):
        context_flags -= {pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP}
        super().init(context_flags, context_props, use_contour_integrator)

    def sync_catchers(self, use_transparent_background=False):
        pass

    def sync_auto_adapt_subdivision(self, width=0, height=0):
        if height == 0:
            height = self.height

        objects_with_adaptive_subdivision = self._get_adaptive_subdivision_objects()
        if not objects_with_adaptive_subdivision:
            return

        auto_ratio_cap = 1.0 / height

        for obj in objects_with_adaptive_subdivision:
            obj.set_subdivision_factor(obj.subdivision['level'])
            obj.set_subdivision_auto_ratio_cap(auto_ratio_cap)
            obj.set_subdivision_boundary_interop(obj.subdivision['boundary'])
            obj.set_subdivision_crease_weight(obj.subdivision['crease_weight'])

    def set_render_update_callback(self, func):
        self.context.set_render_update_callback(func)

    def create_tiled_image(self, key):
        image = pyrpr2.TiledImage(self.context)

        return image

    def sync_portal_lights(self):
        # portals are not supported or needed in rpr2
        return
