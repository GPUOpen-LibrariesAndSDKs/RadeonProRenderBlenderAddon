import sys
import threading
import pyrpr
import pyrprx
from rprblender import logging
from . import image_filter
from . import create_context


class Context:
    def __init__(self, is_preview, width, height, context_flags, context_props=None):
        self.context = create_context(context_flags, context_props)
        self.material_system = pyrpr.MaterialSystem(self.context)
        self.x_context = pyrprx.Context(self.material_system)

        self.width = width
        self.height = height
        self.gl_interop = is_preview and (context_flags & pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP)
        self.render_lock = threading.Lock()
        self.iterations = 0
        self.resolved_iterations = 0

        # list of frame buffers for AOVs
        self.frame_buffers_aovs = {}

        # shadow catcher
        self.sc_composite = None

        # image filter
        self.image_filter = None
        self.image_filter_settings = None
        
        # context settings
        self.context.set_parameter('xflip', False)
        self.context.set_parameter('yflip', False)
        self.context.set_parameter('preview', is_preview)
        #if helpers.use_mps():
        #    self.context.set_parameter('metalperformanceshader', True)
        #self.context.set_parameter('ooctexcache', helpers.get_ooc_cache_size(is_preview))

        self.context.attach_post_effect(pyrpr.POST_EFFECT_NORMALIZATION)
    
        self.scenes = []
        self.scene = None
        self.objects = []

    def __del__(self):
        self.disable_aovs()

    def __call__(self):
        return self.context

    def clear_frame_buffers(self):
        with self.render_lock:
            for fbs in self.frame_buffers_aovs.values():
                fbs['aov'].clear()
            self.iterations = 0
            self.resolved_iterations = 0
  
    def render(self, region=None):
        with self.render_lock:
            if region is None:
                self.context.render()
            else:
                self.context.render_tile(*region)
            self.iterations += 1

    def get_image(self, aov_type=pyrpr.AOV_COLOR):
        if aov_type == pyrpr.AOV_COLOR and self.image_filter:
            return self.image_filter.get_data()

        return self.get_frame_buffer(aov_type).get_data()

    def get_frame_buffer(self, aov_type):
        if aov_type == pyrpr.AOV_COLOR:
            if self.gl_interop and \
                    self.image_filter and self.image_filter_settings['filter_type'] != 'eaw':
                    # temporary fix of EAW filter cause it doesn't work with gl_interop
                return self.frame_buffers_aovs[pyrpr.AOV_COLOR]['gl']
            if self.image_filter:
                return None
            if self.sc_composite:
                return self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc']

        return self.frame_buffers_aovs[aov_type]['res']

    def resolve(self):
        with self.render_lock:
            if self.iterations == self.resolved_iterations:
                return

            for fbs in self.frame_buffers_aovs.values():
                fbs['aov'].resolve(fbs['res'])
            
            self.resolved_iterations = self.iterations

        if self.sc_composite:
            self.sc_composite.compute(self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc'])
            if self.gl_interop and not self.image_filter:
                self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc'].resolve(self.frame_buffers_aovs['default']['gl'])

        if self.image_filter:
            self.image_filter.run()

    def enable_aov(self, aov_type):
        if self.is_aov_enabled(aov_type):
            return

        fbs = {}
        fbs['aov'] = self.context.create_frame_buffer(self.width, self.height)
        fbs['aov'].set_name("%d_aov" % aov_type)
        self.context.attach_aov(aov_type, fbs['aov'])
        if aov_type == pyrpr.AOV_COLOR and self.gl_interop:
            fbs['res'] = self.context.create_frame_buffer(self.width, self.height, True)
            fbs['gl'] = fbs['res']      # resolved and gl framebuffers are the same
            fbs['gl'].set_name("%d_gl" % aov_type)
        else:
            fbs['res'] = self.context.create_frame_buffer(self.width, self.height)
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
        if self.width == width and self.height == height:
            return

        self.width = width
        self.height = height
        with self.render_lock:
            rif_settings = self.image_filter_settings
            if rif_settings:
                self._disable_image_filter()

            sc = self.sc_composite is not None
            if sc:
                self._disable_shadow_catcher()

            for fbs in self.frame_buffers_aovs.values():
                for fb in fbs.values():
                    fb.resize(self.width, self.height)
            
            self.iterations = 0
            self.resolved_iterations = 0

            if sc:
                self._enable_shadow_catcher()

            if rif_settings:
                self._enable_image_filter(rif_settings)
        
    def setup_image_filter(self, settings):
        if self.image_filter_settings != settings:
            with self.render_lock:
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
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = self.context.create_frame_buffer(self.width, self.height)
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'].set_name('default_res')

        color_fb = self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc'] if self.sc_composite else self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res']
        world_fb = self.frame_buffers_aovs[pyrpr.AOV_WORLD_COORDINATE]['res']
        object_fb = self.frame_buffers_aovs[pyrpr.AOV_OBJECT_ID]['res']
        shading_fb = self.frame_buffers_aovs[pyrpr.AOV_SHADING_NORMAL]['res']
        depth_fb = self.frame_buffers_aovs[pyrpr.AOV_DEPTH]['res']
        frame_buffer_gl = self.frame_buffers_aovs[pyrpr.AOV_COLOR].get('gl', None)

        if settings['filter_type'] == 'bilateral':
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

        elif settings['filter_type'] == 'eaw':
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

        elif settings['filter_type'] == 'lwr':
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

    def setup_shadow_catcher(self, use_shadow_catcher):
        with self.render_lock:
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

        self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc'] = self.context.create_frame_buffer(self.width, self.height)
        self.frame_buffers_aovs[pyrpr.AOV_COLOR]['sc'].set_name('default_sc')
        if self.gl_interop:
            # splitting resolved and gl framebuffers
            self.frame_buffers_aovs[pyrpr.AOV_COLOR]['res'] = self.context.create_frame_buffer(self.width, self.height)
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
