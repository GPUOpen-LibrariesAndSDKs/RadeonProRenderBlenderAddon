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
        desc = ffi.new("rpr_framebuffer_desc*")
        self.width, self.height = render_resolution
        desc.fb_width, desc.fb_height = self.width, self.height

        fmt = (4, pyrpr.COMPONENT_TYPE_FLOAT32)
        self.render_buffer = pyrpr.FrameBuffer()
        pyrpr.ContextCreateFrameBuffer(context, fmt, desc, self.render_buffer)
        self.core_context = context

        self.attached = False

    def attach(self):
        pyrpr.ContextSetAOV(self.core_context, self.aov, self.render_buffer)
        self.attached = True

    def detach(self):
        if self.attached:
            pyrpr.ContextSetAOV(self.context, self.aov, ffi.NULL)
            self.attached = False

    def clear(self):
        pyrpr.FrameBufferClear(self.render_buffer)

    def get_core_frame_buffer_image(self):
        return get_core_frame_buffer_image(self.width, self.height, self.render_buffer)

    def __del__(self):
        self.detach()


class PostEffectManager:
    def __init__(self, core_context):
        self._core_context = core_context
        self._post_effects = {}

    def attach(self, name, params = None):
        post_effect = pyrpr.PostEffect()
        pyrpr.ContextCreatePostEffect(self._core_context, name, post_effect)
        self._post_effects[name] = post_effect

        if params:
            for key, value in params.items():
                if type(value) == int:
                    pyrpr.PostEffectSetParameter1u(post_effect, key.encode('latin1'), value)
                elif type(value) == float:
                    pyrpr.PostEffectSetParameter1f(post_effect, key.encode('latin1'), value)
                else:
                    raise NotImplementedError("Not supported value type with key=%s", key)

        pyrpr.ContextAttachPostEffect(self._core_context, post_effect)

    def clear(self):
        for post_effect in self._post_effects.values():
            pyrpr.ContextDetachPostEffect(self._core_context, post_effect)

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
        desc = ffi.new("rpr_framebuffer_desc*")
        desc.fb_width, desc.fb_height = render_resolution
        fmt = (4, pyrpr.COMPONENT_TYPE_FLOAT32)
        self.frame_buffer_tonemapped = pyrpr.FrameBuffer()
        pyrpr.ContextCreateFrameBuffer(self.render_device.core_context, fmt, desc, self.frame_buffer_tonemapped)

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
        pyrpr.FrameBufferClear(self.frame_buffer_tonemapped)
        pyrpr.ContextResolveFrameBuffer(self.render_device.core_context, fb, self.frame_buffer_tonemapped, False)
        return self.get_frame_buffer_image(self.frame_buffer_tonemapped)

    def get_frame_buffer_image(self, fb):
        return get_image(*self.render_resolution, fb)

    def enable_aov(self, aov_name):
        if aov_name in self.aovs:
            return

        aov = AOV(aov_name, self.render_device.core_context, self.render_resolution)
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
        self.core_context = rprblender.render.create_context(rprblender.render.ensure_core_cache_folder(),
                                                             context_flags, context_props)
        pyrpr.ContextSetParameter1u(self.core_context, b'xflip', 0)
        pyrpr.ContextSetParameter1u(self.core_context, b'yflip', 1)
        pyrpr.ContextSetParameter1u(self.core_context, b'preview', 0 if is_production else 1)
        self.core_material_system = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(self.core_context, 0, self.core_material_system)

        self.core_uber_rprx_context = pyrprx.Object('rprx_context')
        pyrprx.CreateContext(self.core_material_system, 0, self.core_uber_rprx_context)

        self.render_target = None  # type:RenderTargets

        self.update_downscaled_image_size(is_production)


    @logged
    def __del__(self):
        images.core_image_cache.purge_for_context(self.core_context)
        images.core_downscaled_image_cache.purge_for_context(self.core_context)
        del images.downscaled_image_size[self.core_context]

        pyrprx.DeleteContext(self.core_uber_rprx_context)

        if config.debug:
            referrers = gc.get_referrers(self.core_context)
            assert 1 == len(referrers), (referrers, self.core_context)

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
        images.downscaled_image_size[self.core_context] = size


@logged
def get_core_frame_buffer_image(width, height, render_buffer):
    fb_data_size_ptr = ffi.new('size_t*', 0)
    pyrpr.FrameBufferGetInfo(render_buffer, pyrpr.FRAMEBUFFER_DATA, 0, ffi.NULL, fb_data_size_ptr);

    fb_data_size = fb_data_size_ptr[0]

    arr = np.empty((height, width, 4), dtype=np.float32)
    assert arr.nbytes == fb_data_size, (arr.nbytes, fb_data_size)

    pyrpr.FrameBufferGetInfo(render_buffer, pyrpr.FRAMEBUFFER_DATA, fb_data_size,
                             ffi.cast('float*', arr.ctypes.data), ffi.NULL);
    return arr


def get_image(width, height, render_buffer):
    return get_core_frame_buffer_image(width, height, render_buffer)

