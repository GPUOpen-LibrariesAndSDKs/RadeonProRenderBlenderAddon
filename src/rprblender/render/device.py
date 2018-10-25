import sys
import threading

import bpy

import pyrpr
import pyrprx
from rprblender import config
from rprblender import logging
from rprblender import images
from rprblender import render
from rprblender import image_filter
from rprblender.render import render_layers
import rprblender.helpers as helpers


logged = helpers.CallLogger(tag='render.device').logged

class RenderTargets:
    def __init__(self, context, is_preview, width, height):
        self.context = context
        self.width = width
        self.height = height
        self.gl_interop = is_preview and (self.context.get_creation_flags() & pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP)
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
        self.context.set_parameter('yflip', True)
        self.context.set_parameter('preview', is_preview)
        if helpers.use_mps():
            self.context.set_parameter('metalperformanceshader', True)

        self.post_effect = pyrpr.PostEffect(self.context, pyrpr.POST_EFFECT_NORMALIZATION)
        self.post_effect.attach()

    def __del__(self):
        self.post_effect.detach()

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

    def get_image(self, aov_name):
        if aov_name == 'default' and self.image_filter:
            return self.image_filter.get_data()

        return self.get_frame_buffer(aov_name).get_data()

    def get_frame_buffer(self, aov_name):
        if aov_name == 'default':
            if self.gl_interop and \
                    self.image_filter and self.image_filter.rif_filter_type != image_filter.RifFilterType.Eaw:
                    # temporary fix of EAW filter cause it doesn't work with gl_interop
                return self.frame_buffers_aovs['default']['gl']
            if self.image_filter:
                return None
            if self.sc_composite:
                return self.frame_buffers_aovs['default']['sc']

        return self.frame_buffers_aovs[aov_name]['res']

    def resolve(self):
        with self.render_lock:
            if self.iterations == self.resolved_iterations:
                return

            for fbs in self.frame_buffers_aovs.values():
                fbs['aov'].resolve(fbs['res'])
            
            self.resolved_iterations = self.iterations

        if self.sc_composite:
            self.sc_composite.compute(self.frame_buffers_aovs['default']['sc'])
            if self.gl_interop and not self.image_filter:
                self.frame_buffers_aovs['default']['sc'].resolve(self.frame_buffers_aovs['default']['gl'])

        if self.image_filter:
            self.image_filter.run()

    def enable_aov(self, aov_name):
        if self.is_aov_enabled(aov_name):
            return

        aov_type = render_layers.aov_info[aov_name]['rpr']
        fbs = {}
        fbs['aov'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
        fbs['aov'].set_name(aov_name + '_aov')
        self.context.attach_aov(aov_type, fbs['aov'])
        if aov_type == pyrpr.AOV_COLOR and self.gl_interop:
            fbs['res'] = pyrpr.FrameBufferGL(self.context, self.width, self.height)
            fbs['gl'] = fbs['res']      # resolved and gl framebuffers are the same
            fbs['gl'].set_name(aov_name + '_gl')
        else:
            fbs['res'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
            fbs['res'].set_name(aov_name + '_res')

        self.frame_buffers_aovs[aov_name] = fbs

    def disable_aov(self, aov_name):
        aov_type = render_layers.aov_info[aov_name]['rpr']
        self.context.detach_aov(aov_type)
        del self.frame_buffers_aovs[aov_name]

    def disable_aovs(self):
        for aov_name in tuple(self.frame_buffers_aovs.keys()):
            self.disable_aov(aov_name)

    def is_aov_enabled(self, aov_name):
        return aov_name in self.frame_buffers_aovs

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
                self.disable_shadow_catcher()

            for fbs in self.frame_buffers_aovs.values():
                for fb in fbs.values():
                    fb.resize(self.width, self.height)
            
            self.iterations = 0
            self.resolved_iterations = 0

            if sc:
                self.enable_shadow_catcher()

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

        self.enable_aov('default')
        self.enable_aov('world_coordinate')
        self.enable_aov('object_id')
        self.enable_aov('shading_normal')
        self.enable_aov('depth')

        if self.gl_interop and not self.sc_composite:
            # splitting resolved and gl framebuffers
            self.frame_buffers_aovs['default']['res'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
            self.frame_buffers_aovs['default']['res'].set_name('default_res')

        color_fb = self.frame_buffers_aovs['default']['sc'] if self.sc_composite else self.frame_buffers_aovs['default']['res']
        world_fb = self.frame_buffers_aovs['world_coordinate']['res']
        object_fb = self.frame_buffers_aovs['object_id']['res']
        shading_fb = self.frame_buffers_aovs['shading_normal']['res']
        depth_fb = self.frame_buffers_aovs['depth']['res']
        frame_buffer_gl = self.frame_buffers_aovs['default'].get('gl', None)

        if settings['filter_type'] == 'bilateral':
            self.image_filter = image_filter.ImageFilter(self.context, image_filter.RifFilterType.Bilateral,
                                                         self.width, self.height, frame_buffer_gl)

            self.image_filter.add_input(image_filter.RifFilterInput.Color, color_fb, settings['color_sigma'])
            self.image_filter.add_input(image_filter.RifFilterInput.Normal, shading_fb, settings['normal_sigma'])
            self.image_filter.add_input(image_filter.RifFilterInput.WorldCoordinate, world_fb, settings['p_sigma'])
            self.image_filter.add_input(image_filter.RifFilterInput.ObjectId, object_fb, settings['trans_sigma'])

            self.image_filter.add_param('radius', settings['radius'])

        elif settings['filter_type'] == 'eaw':
            self.image_filter = image_filter.ImageFilter(self.context, image_filter.RifFilterType.Eaw,
                                                         self.width, self.height, None)
                                                         # temporary fix of EAW filter cause it doesn't work with gl_interop

            self.image_filter.add_input(image_filter.RifFilterInput.Color, color_fb, settings['color_sigma']);
            self.image_filter.add_input(image_filter.RifFilterInput.Normal, shading_fb, settings['normal_sigma'])
            self.image_filter.add_input(image_filter.RifFilterInput.Depth, depth_fb, settings['depth_sigma'])
            self.image_filter.add_input(image_filter.RifFilterInput.Trans, object_fb, settings['trans_sigma'])
            self.image_filter.add_input(image_filter.RifFilterInput.WorldCoordinate, world_fb, 0.1)
            self.image_filter.add_input(image_filter.RifFilterInput.ObjectId, object_fb, 0.1)

        elif settings['filter_type'] == 'lwr':
            self.image_filter = image_filter.ImageFilter(self.context, image_filter.RifFilterType.Lwr,
                                                         self.width, self.height, frame_buffer_gl)

            self.image_filter.add_input(image_filter.RifFilterInput.Color, color_fb)
            self.image_filter.add_input(image_filter.RifFilterInput.Normal, shading_fb)
            self.image_filter.add_input(image_filter.RifFilterInput.Depth, depth_fb)
            self.image_filter.add_input(image_filter.RifFilterInput.WorldCoordinate, world_fb)
            self.image_filter.add_input(image_filter.RifFilterInput.ObjectId, object_fb)
            self.image_filter.add_input(image_filter.RifFilterInput.Trans, object_fb)

            self.image_filter.add_param('samples', settings['samples']);
            self.image_filter.add_param('halfWindow', settings['half_window']);
            self.image_filter.add_param('bandwidth', settings['bandwidth']);

        self.image_filter.attach_filter()

    def _disable_image_filter(self):
        self.image_filter = None
        self.image_filter_settings = None
        if self.gl_interop and not self.sc_composite:
            # set resolved framebuffer be the same as gl
            self.frame_buffers_aovs['default']['res'] = self.frame_buffers_aovs['default']['gl']

    def _update_image_filter(self, settings):
        self.image_filter_settings = settings

        if settings['filter_type'] == 'bilateral':
            self.image_filter.update_sigma(image_filter.RifFilterInput.Color, settings['color_sigma'])
            self.image_filter.update_sigma(image_filter.RifFilterInput.Normal, settings['normal_sigma'])
            self.image_filter.update_sigma(image_filter.RifFilterInput.WorldCoordinate, settings['p_sigma'])
            self.image_filter.update_sigma(image_filter.RifFilterInput.ObjectId, settings['trans_sigma'])
            self.image_filter.add_param('radius', settings['radius'])
        elif settings['filter_type'] == 'eaw':
            self.image_filter.update_sigma(image_filter.RifFilterInput.Color, settings['color_sigma']);
            self.image_filter.update_sigma(image_filter.RifFilterInput.Normal, settings['normal_sigma'])
            self.image_filter.update_sigma(image_filter.RifFilterInput.Depth, settings['depth_sigma'])
            self.image_filter.update_sigma(image_filter.RifFilterInput.Trans, settings['trans_sigma'])
        elif settings['filter_type'] == 'lwr':
            self.image_filter.add_param('samples', settings['samples']);
            self.image_filter.add_param('halfWindow', settings['half_window']);
            self.image_filter.add_param('bandwidth', settings['bandwidth']);

    def enable_shadow_catcher(self):
        self.enable_aov('default')
        self.enable_aov('opacity')
        self.enable_aov('background')
        self.enable_aov('shadow_catcher')

        self.frame_buffers_aovs['default']['sc'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
        self.frame_buffers_aovs['default']['sc'].set_name('default_sc')
        if self.gl_interop:
            # splitting resolved and gl framebuffers
            self.frame_buffers_aovs['default']['res'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
            self.frame_buffers_aovs['default']['res'].set_name('default_res')

        one = pyrpr.Composite(self.context,  pyrpr.COMPOSITE_CONSTANT)
        one.set_input('constant.input', (1.0, 0.0, 0.0, 0.0))
        
        zero = pyrpr.Composite(self.context,  pyrpr.COMPOSITE_CONSTANT)
        zero.set_input('constant.input', (0.0, 0.0, 0.0, 1.0))

        color = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        color.set_input('framebuffer.input', self.frame_buffers_aovs['default']['res'])
        
        background = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        background.set_input('framebuffer.input', self.frame_buffers_aovs['background']['res'])
        
        opacity = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        opacity.set_input('framebuffer.input', self.frame_buffers_aovs['opacity']['res'])

        sc = pyrpr.Composite(self.context, pyrpr.COMPOSITE_FRAMEBUFFER)
        sc.set_input('framebuffer.input', self.frame_buffers_aovs['shadow_catcher']['res'])

        sc_norm = pyrpr.Composite(self.context, pyrpr.COMPOSITE_NORMALIZE)
        sc_norm.set_input('normalize.color', sc)
        sc_norm.set_input('normalize.shadowcatcher', one)

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

    def disable_shadow_catcher(self):
        self.sc_composite = None
        if self.gl_interop:
            # set resolved framebuffer be the same as gl
            self.frame_buffers_aovs['default']['res'] = self.frame_buffers_aovs['default']['gl']
        del self.frame_buffers_aovs['default']['sc']


class RenderDevice:
    @logged
    def __init__(self, is_production, context_flags, context_props=None):
        self.context = render.create_context(render.ensure_core_cache_folder(),
                                             context_flags, context_props)
        self.material_system = pyrpr.MaterialSystem(self.context)
        self.x_context = pyrprx.Context(self.material_system)
        self.is_production = is_production
        self.render_targets = None

        self.core_image_cache = images.core_image_cache
        self.core_downscaled_image_cache = images.core_downscaled_image_cache
        self.downscaled_image_size = images.downscaled_image_size

        self.update_downscaled_image_size(is_production)

    def __del__(self):
        self.core_image_cache.purge_for_context(self.context)
        self.core_downscaled_image_cache.purge_for_context(self.context)
        del self.downscaled_image_size[self.context]

    def create_render_targets(self, width, height):
        self.render_targets = RenderTargets(self.context, not self.is_production, width, height)
        return self.render_targets

    def update_downscaled_image_size(self, is_production):
        settings = bpy.context.scene.rpr.render
        viewport_settings = helpers.get_user_settings().viewport_render_settings
        size = None
        if (not is_production or settings.downscale_textures_production) and \
                    viewport_settings.downscale_textures_size != 'NONE':
            if viewport_settings.downscale_textures_size == 'AUTO':
                size = images.get_automatic_compression_size(bpy.context.scene)
            else:
                size = int(viewport_settings.downscale_textures_size)
        self.downscaled_image_size[self.context] = size

