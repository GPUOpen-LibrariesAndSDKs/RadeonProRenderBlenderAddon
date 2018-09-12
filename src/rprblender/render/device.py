import gc

import numpy as np

import pyrpr
from pyrpr import ffi
import pyrprx
import pyrpropencl
import pyrprimagefilters

import rprblender.render
from rprblender import config, logging, images
import rprblender.render.render_layers
import rprblender.helpers as helpers

import sys
import bpy

logged = helpers.CallLogger(tag='render.device').logged


class AOV:

    def __init__(self, aov_name, context, render_resolution):
        self.context = context
        self.aov = rprblender.render.render_layers.aov_info[aov_name]['rpr']
        self.width, self.height = render_resolution
        self.render_buffer = pyrpr.FrameBuffer(self.context, self.width, self.height)

        self.attached = False

    def attach(self):
        self.context.set_aov(self.aov, self.render_buffer)
        self.attached = True

    def detach(self):
        if self.attached:
            self.context.set_aov(self.aov, None)
            self.attached = False

    def clear(self):
        self.render_buffer.clear()

    def get_core_frame_buffer_image(self):
        return self.render_buffer.get_data()

    def __del__(self):
        self.detach()


class PostEffectManager:
    def __init__(self, context):
        self._core_context = context
        self._post_effects = {}

    def attach(self, pe_type, params = None):
        post_effect = pyrpr.PostEffect(self._core_context, pe_type)
        self._post_effects[pe_type] = post_effect

        if params:
            for key, value in params.items():
                post_effect.set_parameter(key, value)

        post_effect.attach()

    def clear(self):
        for post_effect in self._post_effects.values():
            post_effect.detach()

        self._post_effects.clear()

    def __del__(self):
        self.clear()


class RenderTargets:

    def __init__(self, render_device, render_resolution):
        self.render_device = render_device

        self.frame_buffer_tonemapped = None

        self.aovs = {}

        self.attached = False

        self.render_resolution = render_resolution

        # create fb for applying posteffects
        self.frame_buffer_tonemapped = pyrpr.FrameBuffer(self.render_device.context, *render_resolution)

    def attach(self):
        assert not self.attached
        for aov in self.aovs.values():
            aov.attach()
        self.attached = True

    def detach(self):
        if self.attached:
            for aov in self.aovs.values():
                aov.detach()
            self.attached = False

    def clear(self):
        for aov in self.aovs.values():
            aov.clear()

    def get_image(self, aov_name='default'):
        name = aov_name
        if name not in self.aovs:
            return None
        with rprblender.render.core_operations(raise_error=True):
            fb_image = self.aovs[name].get_core_frame_buffer_image()

        return fb_image

    def get_frame_buffer(self, aov_name='default'):
        name = aov_name
        if name not in self.aovs:
            # logging.info("Looking for unknown aov",name)
            return None
        return self.aovs[aov_name].render_buffer

    def get_resolved_image(self, fb):
        self.frame_buffer_tonemapped.clear()
        fb.resolve(self.frame_buffer_tonemapped)
        return self.get_frame_buffer_image(self.frame_buffer_tonemapped)

    def get_frame_buffer_image(self, fb):
        return get_image(*self.render_resolution, fb)

    def enable_aov(self, aov_name):
        if aov_name in self.aovs:
            return

        aov = AOV(aov_name, self.render_device.context, self.render_resolution)
        self.aovs[aov_name] = aov

        if self.attached:
            aov.attach()

        logging.info('added aov:', aov_name)

    def disable_aov(self, aov_name):
        if aov_name in self.aovs:
            logging.info('removing aov:', aov_name)
            self.aovs.pop(aov_name).detach()

    def is_aov_enabled(self, aov_name):
        return aov_name in self.aovs


class RenderDevice:

    @logged
    def __init__(self, is_production, context_flags, context_props=None):
        self.context = rprblender.render.create_context(rprblender.render.ensure_core_cache_folder(),
                                                             context_flags, context_props)
        self.context.set_parameter('xflip', False)
        self.context.set_parameter('yflip', True)
        self.context.set_parameter('preview', not is_production)

        self.core_material_system = pyrpr.MaterialSystem(self.context)
        self.core_uber_rprx_context = pyrprx.Context(self.core_material_system)

        self.render_target = None  # type:RenderTargets

        self.core_image_cache = images.core_image_cache
        self.core_downscaled_image_cache = images.core_downscaled_image_cache
        self.downscaled_image_size = images.downscaled_image_size

        self.update_downscaled_image_size(is_production)


    @logged
    def __del__(self):
        self.core_image_cache.purge_for_context(self.context)
        self.core_downscaled_image_cache.purge_for_context(self.context)
        del self.downscaled_image_size[self.context]

        if config.debug:
            referrers = gc.get_referrers(self.context)
            assert 1 == len(referrers), (referrers, self.context)

    def attach_render_target(self, render_target):
        if self.render_target:
            self.render_target.detach()
        self.render_target = render_target
        self.render_target.attach()

    def detach_render_target(self, render_target):
        self.render_target.detach()
        self.render_target = None

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


@logged
def get_core_frame_buffer_image(width, height, render_buffer):
    return render_buffer.get_data()

def get_image(width, height, render_buffer):
    return get_core_frame_buffer_image(width, height, render_buffer)

