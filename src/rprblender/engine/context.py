import threading

import pyrpr


class RPRContext:
    """ Manager of pyrpr calls.  Also includes threading lock to make sure
        calls aren't made simultaneously """
    def __init__(self):
        self.context = None
        self.material_system = None
        self.width = None
        self.height = None
        self.gl_interop = None

        # scene and objects
        self.scene = None
        self.objects = {}
        self.particles = {}
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

    def init(self, context_flags, context_props):
        self.context = pyrpr.Context(context_flags, context_props)
        self.material_system = pyrpr.MaterialSystem(self.context)
        self.gl_interop = bool(context_flags & pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP)

        # context settings
        self.context.set_parameter('xflip', False)
        self.context.set_parameter('yflip', False)
        #if helpers.use_mps():
        #    self.context.set_parameter('metalperformanceshader', True)
        #self.context.set_parameter('ooctexcache', helpers.get_ooc_cache_size(is_preview))

        self.post_effect = pyrpr.PostEffect(self.context, pyrpr.POST_EFFECT_NORMALIZATION)

        self.scene = pyrpr.Scene(self.context)
        self.context.set_scene(self.scene)

    def __del__(self):
        if self.context:
            self.disable_aovs()

    def clear_frame_buffers(self):
        for fbs in self.frame_buffers_aovs.values():
            fbs['aov'].clear()

    def render(self, restart=False, tile=None):
        if restart:
            self.clear_frame_buffers()

        if tile is None:
            self.context.render()
        else:
            self.context.render_tile(*tile)

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

    def resolve(self):
        for fbs in self.frame_buffers_aovs.values():
            fbs['aov'].resolve(fbs['res'])

            if self.composite:
                self.composite.compute(self.frame_buffers_aovs[pyrpr.AOV_COLOR]['composite'])
                if self.gl_interop:
                    self.frame_buffers_aovs[pyrpr.AOV_COLOR]['composite'].resolve(self.frame_buffers_aovs[pyrpr.AOV_COLOR]['gl'])

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

    def sync_catchers(self):
        self.use_shadow_catcher = False
        self.use_reflection_catcher = False

        for obj in self.scene.objects:
            if not self.use_shadow_catcher and isinstance(obj, pyrpr.Shape) and obj.shadow_catcher:
                self.use_shadow_catcher = True
            if not self.use_reflection_catcher and isinstance(obj, pyrpr.Shape) and obj.reflection_catcher:
                self.use_reflection_catcher = True
            # break early if both catchers were found
            if self.use_shadow_catcher and self.use_reflection_catcher:
                break

        if self.use_shadow_catcher or self.use_reflection_catcher:
            if not self.composite:
                self._enable_catchers()
        else:
            if self.composite:
                self._disable_catchers()

    def _enable_catchers(self):
        """ Enable composite for one or two active catchers
        RC+SC: background * (1 - min(alpha + shadow_catcher, 1)) + color * (alpha + reflection_catcher)
        SC only: background * (1 - min(alpha + shadow_catcher, 1)) + color * alpha
        RC only: background * (1 - alpha) + color * (alpha + reflection_catcher)
        """
        # Enable required AOVs
        self.enable_aov(pyrpr.AOV_COLOR)
        self.enable_aov(pyrpr.AOV_OPACITY)
        self.enable_aov(pyrpr.AOV_BACKGROUND)
        if self.use_shadow_catcher:
            self.enable_aov(pyrpr.AOV_SHADOW_CATCHER)
        if self.use_reflection_catcher:
            self.enable_aov(pyrpr.AOV_REFLECTION_CATCHER)

        # Composite frame buffer
        self.frame_buffers_aovs[pyrpr.AOV_COLOR]['composite'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
        self.frame_buffers_aovs[pyrpr.AOV_COLOR]['composite'].set_name('default_composite')
        if self.gl_interop:
            # splitting resolved and gl framebuffers
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = pyrpr.FrameBuffer(self.context, self.width,
                                                                                self.height)
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'].set_name('default_res')

        # Composite calculation elements frame buffers
        color = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        color.set_name('composite_aov_color')
        color.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'])

        background = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        background.set_name('composite_aov_background')
        background.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_BACKGROUND]['res'])

        alpha = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        alpha.set_name('composite_aov_opacity')
        alpha.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_OPACITY]['res'])

        one = pyrpr.Composite(self.context,  pyrpr.COMPOSITE_CONSTANT)
        one.set_input('constant.input', (1.0, 1.0, 1.0, 1.0))

        # shadow catcher composite nodes
        if self.use_shadow_catcher:
            sc_composite = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
            sc_composite.set_name('composite_aov_shadowcatcher')
            sc_composite.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_SHADOW_CATCHER]['res'])

            alpha_plus_sc = pyrpr.Composite(self.context, pyrpr.COMPOSITE_ARITHMETIC)
            alpha_plus_sc.set_name("composite_alpha_with_shadowcatcher")
            alpha_plus_sc.set_input('arithmetic.color0', alpha)
            alpha_plus_sc.set_input('arithmetic.color1', sc_composite)
            alpha_plus_sc.set_input('arithmetic.op', pyrpr.MATERIAL_NODE_OP_ADD)

            bg_alpha_min = pyrpr.Composite(self.context, pyrpr.COMPOSITE_ARITHMETIC)
            bg_alpha_min.set_name("composite_min_of_alpha_with_sc")
            bg_alpha_min.set_input('arithmetic.color0', alpha_plus_sc)
            bg_alpha_min.set_input('arithmetic.color1', one)
            bg_alpha_min.set_input('arithmetic.op', pyrpr.MATERIAL_NODE_OP_MIN)
        else:
            bg_alpha_min = alpha

        # reflection catcher composite nodes
        if self.use_reflection_catcher:
            rc_composite = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
            rc_composite.set_name('composite_aov_reflection_catcher')
            rc_composite.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_REFLECTION_CATCHER]['res'])

            color_coeff = pyrpr.Composite(self.context, pyrpr.COMPOSITE_ARITHMETIC)
            color_coeff.set_name('composite_color_coeff')
            color_coeff.set_input('arithmetic.color0', alpha)
            color_coeff.set_input('arithmetic.color1', rc_composite)
            color_coeff.set_input('arithmetic.op', pyrpr.MATERIAL_NODE_OP_ADD)
        else:
            color_coeff = alpha

        # Combined result calculations
        # SC: background_part = Background * (1 - min(Alpha + Shadow Catcher, 1))
        # no SC: background_part = Background * (1 - Alpha)
        background_coeff = pyrpr.Composite(self.context, pyrpr.COMPOSITE_ARITHMETIC)
        background_coeff.set_name('composite_background_coeff')
        background_coeff.set_input('arithmetic.color0', one)
        background_coeff.set_input('arithmetic.color1', bg_alpha_min)
        background_coeff.set_input('arithmetic.op', pyrpr.MATERIAL_NODE_OP_SUB)

        background_part = pyrpr.Composite(self.context, pyrpr.COMPOSITE_ARITHMETIC)
        background_part.set_name('composite_background')
        background_part.set_input('arithmetic.color0', background)
        background_part.set_input('arithmetic.color1', background_coeff)
        background_part.set_input('arithmetic.op', pyrpr.MATERIAL_NODE_OP_MUL)

        # RC: color part = Color * (Alpha + Reflection Catcher)
        # no RC: color part = Color * Alpha
        color_part = pyrpr.Composite(self.context, pyrpr.COMPOSITE_ARITHMETIC)
        color_part.set_name('composite_color_coeff')
        color_part.set_input('arithmetic.color0', color)
        color_part.set_input('arithmetic.color1', color_coeff)
        color_part.set_input('arithmetic.op', pyrpr.MATERIAL_NODE_OP_MUL)

        # result = background part + color part
        res = pyrpr.Composite(self.context, pyrpr.COMPOSITE_ARITHMETIC)
        res.set_input('arithmetic.color0', background_part)
        res.set_input('arithmetic.color1', color_part)
        res.set_input('arithmetic.op', pyrpr.MATERIAL_NODE_OP_ADD)

        self.composite = res
        self.composite.set_name("composite_result")

    def _disable_catchers(self):
        self.composite = None
        if self.gl_interop:
            # set resolved framebuffer be the same as gl
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = self.frame_buffers_aovs[pyrpr.AOV_COLOR]['gl']
        del self.frame_buffers_aovs[pyrpr.AOV_COLOR]['composite']

    def sync_auto_adapt_subdivision(self, width=0, height=0):
        if width == 0:
            width = self.width
        if height == 0:
            height = self.height

        fb = self.frame_buffers_aovs[pyrpr.AOV_COLOR]['aov']

        for obj in self.scene.objects:
            if isinstance(obj, pyrpr.Shape) and obj.subdivision is not None:
                if fb.width != width or fb.height != height:
                    # creating temporary framebuffer of required size only to set subdivision
                    fb = pyrpr.FrameBuffer(self.context, width, height)

                obj.set_auto_adapt_subdivision_factor(fb, self.scene.camera, obj.subdivision['factor'])
                obj.set_subdivision_boundary_interop(obj.subdivision['boundary'])
                obj.set_subdivision_crease_weight(obj.subdivision['crease_weight'])

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
            light = pyrpr.PointLight(self.context)
        elif light_type == 'spot':
            light = pyrpr.SpotLight(self.context)
        elif light_type == 'directional':
            light = pyrpr.DirectionalLight(self.context)
        elif light_type == 'ies':
            light = pyrpr.IESLight(self.context)
        else:
            raise KeyError("No such light type", light_type)

        self.objects[key] = light
        return light

    def create_environment_light(self):
        return pyrpr.EnvironmentLight(self.context)

    def create_area_light(
            self, key,
            vertices, normals, uvs,
            vertex_indices, normal_indices, uv_indices,
            num_face_vertices
    ):
        mesh = pyrpr.Mesh(
            self.context,
            vertices, normals, uvs,
            vertex_indices, normal_indices, uv_indices,
            num_face_vertices
        )
        light = pyrpr.AreaLight(mesh, self.material_system)
        self.objects[key] = light
        return light

    def create_mesh(
            self, key,
            vertices, normals, uvs,
            vertex_indices, normal_indices, uv_indices,
            num_face_vertices
    ):
        mesh = pyrpr.Mesh(
            self.context,
            vertices, normals, uvs,
            vertex_indices, normal_indices, uv_indices,
            num_face_vertices
        )
        self.objects[key] = mesh
        return mesh

    def create_instance(self, key, mesh):
        instance = pyrpr.Instance(self.context, mesh)
        self.objects[key] = instance
        return instance

    def create_curve(self, key, control_points, uvs, radius):
        curve = pyrpr.Curve(self.context, control_points, uvs, radius)
        self.particles[key] = curve
        return curve

    def create_hetero_volume(self, key):
        volume = pyrpr.HeteroVolume(self.context)
        self.volumes[key] = volume
        return volume

    def create_camera(self, key=None):
        camera = pyrpr.Camera(self.context)
        if key:
            self.objects[key] = camera
        return camera

    def create_material_node(self, material_type):
        return pyrpr.MaterialNode(self.material_system, material_type)

    def set_material_node_key(self, key, material_node):
        self.material_nodes[key] = material_node

    def set_material_node_as_material(self, key, material_node):
        self.materials[key] = material_node

    def create_image_file(self, key, filepath):
        image = pyrpr.ImageFile(self.context, filepath)
        if key:
            self.images[key] = image
        return image

    def create_image_data(self, key, data):
        image = pyrpr.ImageData(self.context, data)
        if key:
            self.images[key] = image
        return image

    def create_buffer(self, data, dtype):
        return pyrpr.Buffer(self.context, data, dtype)

    def set_parameter(self, name, param):
        if param == self.context.parameters.get(name, None):
            return False

        self.context.set_parameter(name, param)
        return True

    def get_parameter(self, name):
        return self.context.parameters[name]

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

        self.remove_particles(key)
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

    def remove_particles(self, base_obj_key):
        keys = tuple(k for k in self.particles.keys() if k[0] == base_obj_key)
        for k in keys:
            particle = self.particles.pop(k)
            self.scene.detach(particle)

    def remove_volumes(self, base_obj_key):
        keys = tuple(k for k in self.volumes.keys() if k[0] == base_obj_key)
        for k in keys:
            volume = self.volumes.pop(k)
            self.scene.detach(volume)

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
