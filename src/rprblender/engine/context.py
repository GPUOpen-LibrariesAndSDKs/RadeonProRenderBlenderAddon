import pyrpr
import pyrprx

from . import image_filter


class RPRContext:
    def __init__(self):
        self.context = None
        self.material_system = None
        self.x_context = None
        self.width = None
        self.height = None
        self.gl_interop = None

        # scene and objects
        self.scene = None
        self.objects = {}
        self.meshes = {}

        # TODO: probably better make nodes more close to materials in one data structure
        self.material_nodes = {}
        self.materials = {}

        self.images = {}
        self.post_effect = None

        # list of frame buffers for AOVs
        self.frame_buffers_aovs = {}

        # shadow catcher
        self.sc_composite = None

        # image filter
        self.image_filter = None
        self.image_filter_settings = None

    def init(self, context_flags, context_props):
        self.context = pyrpr.Context(context_flags, context_props)
        self.material_system = pyrpr.MaterialSystem(self.context)
        self.x_context = pyrprx.Context(self.material_system)
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

    def render(self, tile=None):
        if tile is None:
            self.context.render()
        else:
            self.context.render_tile(*tile)

    def get_image(self, aov_type=pyrpr.AOV_COLOR):
        if aov_type == pyrpr.AOV_COLOR and self.image_filter:
            return self.image_filter.get_data()

        return self.get_frame_buffer(aov_type).get_data()

    def get_frame_buffer(self, aov_type):
        if aov_type == pyrpr.AOV_COLOR:
            if self.gl_interop:
                if self.image_filter and self.image_filter_settings['filter_type'] == 'eaw':
                    # temporary fix of EAW filter cause it doesn't work with gl_interop
                    raise RuntimeError("Color frame_buffer is not available because EAW image filter is used with gl_interop")
                    
                return self.frame_buffers_aovs[pyrpr.AOV_COLOR]['gl']

            if self.image_filter:
                raise RuntimeError("Color frame_buffer is not available because image filter is used")
            
            if self.sc_composite:
                return self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc']

        return self.frame_buffers_aovs[aov_type]['res']

    def resolve(self):
        for fbs in self.frame_buffers_aovs.values():
            fbs['aov'].resolve(fbs['res'])

    def resolve_extras(self):
        if self.sc_composite:
            self.sc_composite.compute(self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc'])
            if self.gl_interop and not self.image_filter:
                self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc'].resolve(self.frame_buffers_aovs[pyrpr.AOV_COLOR]['gl'])

        if self.image_filter:
            self.image_filter.run()

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

        rif_settings = self.image_filter_settings
        if rif_settings:
            self._disable_image_filter()

        sc = self.sc_composite is not None
        if sc:
            self._disable_shadow_catcher()

        for fbs in self.frame_buffers_aovs.values():
            for fb in fbs.values():
                fb.resize(self.width, self.height)

        if sc:
            self._enable_shadow_catcher()

        if rif_settings:
            self._enable_image_filter(rif_settings)
        
    def setup_image_filter(self, settings):
        if self.image_filter_settings != settings:
            if settings['enable']:
                if not self.image_filter:
                    self._enable_image_filter(settings)
                    return

                if self.image_filter_settings['filter_type'] == settings['filter_type']:
                    self._update_image_filter(settings)
                    return

                #recreating filter
                self._disable_image_filter()
                self._enable_image_filter(settings)

            elif self.image_filter:
                self._disable_image_filter()

    def _enable_image_filter(self, settings):
        self.image_filter_settings = settings

        self.enable_aov(pyrpr.AOV_COLOR)
        self.enable_aov(pyrpr.AOV_WORLD_COORDINATE)
        self.enable_aov(pyrpr.AOV_OBJECT_ID)
        self.enable_aov(pyrpr.AOV_SHADING_NORMAL)
        self.enable_aov(pyrpr.AOV_DEPTH)

        if self.gl_interop and not self.sc_composite:
            # splitting resolved and gl framebuffers
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'].set_name('0_res')

        color_fb = self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc'] if self.sc_composite else self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res']
        world_fb = self.frame_buffers_aovs[pyrpr.AOV_WORLD_COORDINATE]['res']
        object_fb = self.frame_buffers_aovs[pyrpr.AOV_OBJECT_ID]['res']
        shading_fb = self.frame_buffers_aovs[pyrpr.AOV_SHADING_NORMAL]['res']
        depth_fb = self.frame_buffers_aovs[pyrpr.AOV_DEPTH]['res']
        frame_buffer_gl = self.frame_buffers_aovs[pyrpr.AOV_COLOR].get('gl', None)

        if settings['filter_type'] == 'BILATERAL':
            inputs = {
                'color': color_fb,
                'normal': shading_fb,
                'world_coordinate': world_fb,
                'object_id': object_fb,
            }
            sigmas = {
                'color': settings['color_sigma'],
                'normal': settings['normal_sigma'],
                'world_coordinate': settings['p_sigma'],
                'object_id': settings['trans_sigma'],
            }
            params = {'radius': settings['radius']}
            self.image_filter = image_filter.ImageFilterBilateral(self.context, inputs, sigmas, params, self.width, self.height, frame_buffer_gl)

        elif settings['filter_type'] == 'EAW':
            inputs = {
                'color': color_fb,
                'normal': shading_fb,
                'depth': depth_fb,
                'trans': object_fb,
                'world_coordinate': world_fb,
                'object_id': object_fb,
            }
            sigmas = {
                'color': settings['color_sigma'],
                'normal': settings['normal_sigma'],
                'depth': settings['depth_sigma'],
                'trans': settings['trans_sigma'],
            }
            self.image_filter = image_filter.ImageFilterEaw(self.context, inputs, sigmas, {}, self.width, self.height, None)
                                                         # temporary fix of EAW filter cause it doesn't work with gl_interop

        elif settings['filter_type'] == 'LWR':
            inputs = {
                'color': color_fb,
                'normal': shading_fb,
                'depth': depth_fb,
                'trans': object_fb,
                'world_coordinate': world_fb,
                'object_id': object_fb,
            }
            params = {
                'samples': settings['samples'],
                'halfWindow': settings['half_window'],
                'bandwidth': settings['bandwidth'],
            }
            self.image_filter = image_filter.ImageFilterLwr(self.context, inputs, {}, params, self.width, self.height, frame_buffer_gl)

    def _disable_image_filter(self):
        self.image_filter = None
        self.image_filter_settings = None
        if self.gl_interop and not self.sc_composite:
            # set resolved framebuffer be the same as gl
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = self.frame_buffers_aovs[pyrpr.AOV_COLOR]['gl']

    def _update_image_filter(self, settings):
        self.image_filter_settings = settings

        if settings['filter_type'] == 'bilateral':
            self.image_filter.update_sigma('color', settings['color_sigma'])
            self.image_filter.update_sigma('normal', settings['normal_sigma'])
            self.image_filter.update_sigma('world_coordinate', settings['p_sigma'])
            self.image_filter.update_sigma('object_id', settings['trans_sigma'])
            self.image_filter.update_param('radius', settings['radius'])
        elif settings['filter_type'] == 'eaw':
            self.image_filter.update_sigma('color', settings['color_sigma']);
            self.image_filter.update_sigma('normal', settings['normal_sigma'])
            self.image_filter.update_sigma('depth', settings['depth_sigma'])
            self.image_filter.update_sigma('trans', settings['trans_sigma'])
        elif settings['filter_type'] == 'lwr':
            self.image_filter.update_param('samples', settings['samples']);
            self.image_filter.update_param('halfWindow', settings['half_window']);
            self.image_filter.update_param('bandwidth', settings['bandwidth']);

    def sync_shadow_catcher(self):
        use_shadow_catcher = False
        for obj in self.scene.objects:
            if isinstance(obj, pyrpr.Shape) and obj.shadow_catcher:
                use_shadow_catcher = True
                break

        if use_shadow_catcher:
            if not self.sc_composite:
                # enable shadow catcher with recreating image filter if needed
                rif_settings = self.image_filter_settings
                if rif_settings:
                    self._disable_image_filter()

                self._enable_shadow_catcher()

                if rif_settings:
                    self._enable_image_filter(rif_settings)
        else:
            if self.sc_composite:
                # disable shadow catcher with recreating image filter if needed
                rif_settings = self.image_filter_settings
                if rif_settings:
                    self._disable_image_filter()

                self._disable_shadow_catcher()

                if rif_settings:
                    self._enable_image_filter(rif_settings)

    def _enable_shadow_catcher(self):
        self.enable_aov(pyrpr.AOV_COLOR)
        self.enable_aov(pyrpr.AOV_OPACITY)
        self.enable_aov(pyrpr.AOV_BACKGROUND)
        self.enable_aov(pyrpr.AOV_SHADOW_CATCHER)

        self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
        self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc'].set_name('default_sc')
        if self.gl_interop:
            # splitting resolved and gl framebuffers
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'].set_name('default_res')
        
        zero = pyrpr.Composite(self.context,  pyrpr.COMPOSITE_CONSTANT)
        zero.set_input('constant.input', (0.0, 0.0, 0.0, 1.0))

        color = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        color.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'])
        
        background = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        background.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_BACKGROUND]['res'])
        
        opacity = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        opacity.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_OPACITY]['res'])

        sc = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        sc.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_SHADOW_CATCHER]['res'])

        sc_norm = pyrpr.Composite(self.context, pyrpr.COMPOSITE_NORMALIZE)
        sc_norm.set_input('normalize.color', sc)
        sc_norm.set_input('normalize.aovtype', pyrpr.AOV_SHADOW_CATCHER)

        # Combine color and background buffers using COMPOSITE_LERP_VALUE
        lerp1 = pyrpr.Composite(self.context, pyrpr.COMPOSITE_LERP_VALUE)
        lerp1.set_input('lerp.color0', background)
        lerp1.set_input('lerp.color1', color)
        lerp1.set_input('lerp.weight', opacity)

        lerp2 = pyrpr.Composite(self.context, pyrpr.COMPOSITE_LERP_VALUE)
        lerp2.set_input('lerp.color0', lerp1)
        lerp2.set_input('lerp.color1', zero)
        lerp2.set_input('lerp.weight', sc_norm)

        self.sc_composite = lerp2

    def _disable_shadow_catcher(self):
        self.sc_composite = None
        if self.gl_interop:
            # set resolved framebuffer be the same as gl
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = self.frame_buffers_aovs[pyrpr.AOV_COLOR]['gl']
        del self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc']

    def sync_auto_adapt_subdivision(self):
        for obj in self.scene.objects:
            if isinstance(obj, pyrpr.Shape) and obj.subdivision is not None:
                obj.set_auto_adapt_subdivision_factor(self.frame_buffers_aovs[pyrpr.AOV_COLOR]['aov'],
                                                      self.scene.camera, obj.subdivision['factor'])
                obj.set_subdivision_boundary_interop(obj.subdivision['boundary'])
                obj.set_subdivision_crease_weight(obj.subdivision['crease_weight'])

    #
    # OBJECT'S CREATION FUNCTIONS
    #
    def create_light(self, key, light_type):
        if light_type == 'point':
            light = pyrpr.PointLight(self.context)
        elif light_type == 'spot':
            light = pyrpr.SpotLight(self.context)
        elif light_type == 'directional':
            light = pyrpr.DirectionalLight(self.context)
        elif light_type == 'ies':
            light = pyrpr.IESLight(self.context)
        elif light_type == 'environment':
            light = pyrpr.EnvironmentLight(self.context)
        else:
            raise KeyError("No such light type", light_type)

        self.objects[key] = light
        return light

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
            self, key, mesh_key,
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
        self.meshes[mesh_key] = mesh
        self.objects[key] = mesh
        return mesh

    def create_instance(self, key, mesh):
        instance = pyrpr.Instance(self.context, mesh)
        self.objects[key] = instance
        return instance

    def create_camera(self, key):
        camera = pyrpr.Camera(self.context)
        self.objects[key] = camera
        return camera

    def create_material_node(self, key, material_type):
        node = pyrpr.MaterialNode(self.material_system, material_type)

        # key could be None for supported nodes which no need to add into material_nodes
        if key:
            self.material_nodes[key] = node

        node.set_name(str(key) if key else str(material_type))
        return node

    def create_x_material_node(self, key, material_type):
        node = pyrprx.Material(self.x_context, material_type)
        self.material_nodes[key] = node
        return node

    def set_material_node_as_material(self, key, material_node):
        self.materials[key] = material_node

    def arithmetic_node_value(self, val1, val2, op_type):
        def to_vec4(val):
            if isinstance(val, float):
                return (val, val, val, val)
            if len(val) == 3:
                return (*val, 1.0)
            return val

        def create_arithmetic_node():
            node = self.create_material_node(None, pyrpr.MATERIAL_NODE_ARITHMETIC)
            node.set_input('op', op_type)
            node.set_input('color0', val1)
            node.set_input('color1', val2)
            return node

        if isinstance(val1, (pyrpr.MaterialNode, pyrprx.Material)) or isinstance(val2, (pyrpr.MaterialNode, pyrprx.Material)):
            return create_arithmetic_node()

        val1 = to_vec4(val1)
        val2 = to_vec4(val2)

        if op_type == pyrpr.MATERIAL_NODE_OP_MUL:
            return (val1[0] * val2[0], val1[1] * val2[1], val1[2] * val2[2], val1[3] * val2[3])

        if op_type == pyrpr.MATERIAL_NODE_OP_SUB:
            return (val1[0] - val2[0], val1[1] - val2[1], val1[2] - val2[2], val1[3] - val2[3])

        if op_type == pyrpr.MATERIAL_NODE_OP_ADD:
            return (val1[0] + val2[0], val1[1] + val2[1], val1[2] + val2[2], val1[3] + val2[3])

        if op_type == pyrpr.MATERIAL_NODE_OP_MAX:
            return (max(val1[0], val2[0]), max(val1[1], val2[1]), max(val1[2], val2[2]), max(val1[3], val2[3]))

        return create_arithmetic_node()

    def mul_node_value(self, val1, val2):
        return self.arithmetic_node_value(val1, val2, pyrpr.MATERIAL_NODE_OP_MUL)

    def add_node_value(self, val1, val2):
        return self.arithmetic_node_value(val1, val2, pyrpr.MATERIAL_NODE_OP_ADD)

    def sub_node_value(self, val1, val2):
        return self.arithmetic_node_value(val1, val2, pyrpr.MATERIAL_NODE_OP_SUB)

    def max_node_value(self, val1, val2):
        return self.arithmetic_node_value(val1, val2, pyrpr.MATERIAL_NODE_OP_MAX)

    def create_image_file(self, key, filepath):
        image = pyrpr.ImageFile(self.context, filepath)
        image.set_name(key)
        self.images[key] = image
        return image

    def create_image_data(self, key, data):
        image = pyrpr.ImageData(self.context, data)
        image.set_name(key)
        self.images[key] = image
        return image

    def set_parameter(self, name, param):
        self.context.set_parameter(name, param)

    def remove_object(self, key):
        def get_mesh_key(mesh):
            for key, m in self.meshes.items():
                if m == mesh:
                    return key

            raise KeyError("No such mesh", mesh)

        obj = self.objects.pop(key)
        self.scene.detach(obj)

        if isinstance(obj, pyrpr.Mesh):
            # TODO: This is temporary decision how to remove meshes. It has to be improved.

            # check if mesh is not used in other instances then delete it also
            used = False
            for o in self.objects.values():
                if isinstance(o, pyrpr.Instance) and o.mesh == obj:
                    used = True
                    break

            if not used:
                del self.meshes[get_mesh_key(obj)]

    def remove_image(self, key):
        del self.images[key]

    def remove_material(self, key):
        # removing all corresponded nodes
        for node_key in tuple(self.material_nodes.keys()):
            if node_key[0] == key:
                del self.material_nodes[node_key]

        del self.materials[key]
