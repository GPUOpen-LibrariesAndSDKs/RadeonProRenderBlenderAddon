import pyrpr

from . import image_filter
import threading


class RPRContext:
    """ Manager of pyrpr calls.  Also includes threading lock to make sure
        calls aren't made simultaneously """
    def __init__(self):
        self.context = None
        self.material_system = None
        self.width = None
        self.height = None
        self.gl_interop = None
        self.lock = threading.Lock()

        # scene and objects
        self.scene = None
        self.objects = {}
        self.particles = {}
        self.volumes = {}

        self.do_motion_blur = False
        self.is_preview = False

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
        with self.lock:
            if restart:
                self.clear_frame_buffers()

            if tile is None:
                self.context.render()
            else:
                self.context.render_tile(*tile)

    def get_image(self, aov_type=pyrpr.AOV_COLOR):
        with self.lock:
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
        with self.lock:
            for fbs in self.frame_buffers_aovs.values():
                fbs['aov'].resolve(fbs['res'])

    def resolve_extras(self):
        if self.sc_composite:
            with self.lock:
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

                # recreating filter
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
        self.enable_aov(pyrpr.AOV_DIFFUSE_ALBEDO)

        if self.gl_interop and not self.sc_composite:
            # splitting resolved and gl framebuffers
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'].set_name('0_res')

        if self.sc_composite:
            color_fb = self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc']
        else:
            color_fb = self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res']
        world_fb = self.frame_buffers_aovs[pyrpr.AOV_WORLD_COORDINATE]['res']
        object_fb = self.frame_buffers_aovs[pyrpr.AOV_OBJECT_ID]['res']
        shading_fb = self.frame_buffers_aovs[pyrpr.AOV_SHADING_NORMAL]['res']
        depth_fb = self.frame_buffers_aovs[pyrpr.AOV_DEPTH]['res']
        albedo_fb = self.frame_buffers_aovs[pyrpr.AOV_DIFFUSE_ALBEDO]['res']
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

        elif settings['filter_type'] == 'ML':
            inputs = {
                'color': color_fb,
                'normal': shading_fb,
                'depth': depth_fb,
                'albedo': albedo_fb,
            }
            self.image_filter = image_filter.ImageFilterML(self.context, inputs, {}, {}, self.width, self.height, frame_buffer_gl)

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
            self.image_filter.update_sigma('color', settings['color_sigma'])
            self.image_filter.update_sigma('normal', settings['normal_sigma'])
            self.image_filter.update_sigma('depth', settings['depth_sigma'])
            self.image_filter.update_sigma('trans', settings['trans_sigma'])
        elif settings['filter_type'] == 'lwr':
            self.image_filter.update_param('samples', settings['samples'])
            self.image_filter.update_param('halfWindow', settings['half_window'])
            self.image_filter.update_param('bandwidth', settings['bandwidth'])

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
        zero.set_name('sc_composite_zero')
        zero.set_input('constant.input', (0.0, 0.0, 0.0, 1.0))

        color = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        color.set_name('sc_composite_aov_color_color')
        color.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'])

        background = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        background.set_name('sc_composite_aov_background')
        background.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_BACKGROUND]['res'])

        opacity = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        opacity.set_name('sc_composite_aov_opacity')
        opacity.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_OPACITY]['res'])

        sc = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        sc.set_name('sc_composite_aov_shadowcatcher')
        sc.set_input('framebuffer.input', self.frame_buffers_aovs[pyrpr.AOV_SHADOW_CATCHER]['res'])

        # Combine color and background buffers using COMPOSITE_LERP_VALUE
        lerp1 = pyrpr.Composite(self.context, pyrpr.COMPOSITE_LERP_VALUE)
        lerp1.set_name('sc_composite_lerp1')
        lerp1.set_input('lerp.color0', background)
        lerp1.set_input('lerp.color1', color)
        lerp1.set_input('lerp.weight', opacity)

        lerp2 = pyrpr.Composite(self.context, pyrpr.COMPOSITE_LERP_VALUE)
        lerp2.set_name('sc_composite_result')
        lerp2.set_input('lerp.color0', lerp1)
        lerp2.set_input('lerp.color1', zero)
        lerp2.set_input('lerp.weight', sc)

        self.sc_composite = lerp2

    def _disable_shadow_catcher(self):
        self.sc_composite = None
        if self.gl_interop:
            # set resolved framebuffer be the same as gl
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = self.frame_buffers_aovs[pyrpr.AOV_COLOR]['gl']
        del self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc']

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

    def remove_object(self, key):
        obj = self.objects.pop(key)

        if isinstance(obj, pyrpr.Mesh):
            # removing and detaching related instances
            instance_keys = tuple(k for k in self.objects.keys()
                                    if isinstance(k, tuple) and k[0] == key)
            for k in instance_keys:
                instance = self.objects.pop(k)
                self.scene.detach(instance)

        self.remove_particles(key)
        self.remove_volumes(key)

        if obj:
            self.scene.detach(obj)

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
