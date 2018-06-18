import gc

import numpy as np

import pyrpr
from pyrpr import ffi
import pyrprx
import pyrpropencl
import pyrprimagefilters

import rprblender.render
from rprblender import config, logging, images
from rprblender.helpers import CallLogger
from rprblender.helpers import isMetalOn
import rprblender.render.render_layers

import sys
import bpy

logged = CallLogger(tag='render.device').logged


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
        assert not self.attached
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


class PostEffect:

    def __init__(self, core_post_effect):
        self.core_post_effect = core_post_effect

    def set_param_float(self, name, value):
        pyrpr.PostEffectSetParameter1f(self.core_post_effect, name, value)

    def set_param_int(self, name, value):
        pyrpr.PostEffectSetParameter1u(self.core_post_effect, name, value)


class PostEffectUpdate:

    def __init__(self, render_device):
        self.posteffects_needed = []
        self.render_device = render_device

    def enable(self, post_effect_name) -> PostEffect:
        self.posteffects_needed.append(post_effect_name)
        return PostEffect(self.render_device.attach_posteffect(post_effect_name))


class PostEffectChain:

    def __init__(self, render_device):
        self.render_device = render_device

    def start_update(self):
        # remove all posteffects
        # TODO: possible optimization is to leave this for later
        # and don't delete used effects. BUT post-effects attachments order matters.
        # this will make this code a bit more complex. Right now I don't see need for extra complexity.
        for post_effect in list(self.render_device.post_effects):
            self.render_device.detach_posteffect(post_effect)

        return PostEffectUpdate(self.render_device)


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

    @logged
    def __del__(self):
        self.aovs.clear()
        del self.frame_buffer_tonemapped

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
        pyrpr.ContextResolveFrameBuffer(self.render_device.core_context, fb, self.frame_buffer_tonemapped)
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
    def __init__(self, is_production, context_flags):
        self.core_context = rprblender.render.create_context(rprblender.render.ensure_core_cache_folder(), context_flags)
        pyrpr.ContextSetParameter1u(self.core_context, b'xflip', 0)
        pyrpr.ContextSetParameter1u(self.core_context, b'yflip', 1)
        pyrpr.ContextSetParameter1u(self.core_context, b'preview', 0 if is_production else 1)
        self.core_material_system = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(self.core_context, 0, self.core_material_system)

        self.core_uber_rprx_context = pyrprx.Object('rprx_context')
        pyrprx.CreateContext(self.core_material_system, 0, self.core_uber_rprx_context)

        self.post_effects = {}

        self.render_target = None  # type:RenderTargets
        self.rif_context = None

        self.update_downscaled_image_size(is_production)


    @logged
    def __del__(self):
        images.core_image_cache.purge_for_context(self.core_context)
        images.core_downscaled_image_cache.purge_for_context(self.core_context)
        del images.downscaled_image_size[self.core_context]

        del self.core_material_system
        del self.post_effects

        pyrprx.DeleteContext(self.core_uber_rprx_context)
        del self.core_uber_rprx_context

        if config.debug:
            referrers = gc.get_referrers(self.core_context)
            assert 1 == len(referrers), (referrers, self.core_context)

    # rif context used for denoising
    def create_rif_context(self):
        if self.rif_context:
            return

        try:
            creation_flags = pyrpr.ffi.new("rpr_creation_flags*", 0)
            pyrpr.ContextGetInfo(self.core_context, pyrpr.CONTEXT_CREATION_FLAGS, sys.getsizeof(creation_flags),
                                 creation_flags, pyrpr.ffi.NULL)

            self.rif_context = pyrprimagefilters.RifContext()

            # Todo : remove this when image filters supports metal
            if creation_flags[0] & pyrpr.CREATION_FLAGS_ENABLE_CPU:
                pyrprimagefilters.CreateContext(pyrprimagefilters.API_VERSION, pyrprimagefilters.BACKEND_API_OPENCL,
                                                pyrprimagefilters.PROCESSOR_CPU, 0, pyrprimagefilters.ffi.NULL,
                                                self.rif_context)
            elif creation_flags[0] & pyrpr.CREATION_FLAGS_ENABLE_METAL:
                 pyrprimagefilters.CreateContext(pyrprimagefilters.API_VERSION, pyrprimagefilters.BACKEND_API_METAL,
                                                 pyrprimagefilters.PROCESSOR_CPU, 0, pyrprimagefilters.ffi.NULL,
                                                 self.rif_context)
            else:
                # Obtain OpenCL context
                cl_context = pyrpropencl.ffi.new("rpr_cl_context*")
                pyrpr.ContextGetInfo(self.core_context, pyrpropencl.CONTEXT, sys.getsizeof(cl_context),
                                    cl_context, pyrpropencl.ffi.NULL)

                cl_device = pyrpropencl.ffi.new("rpr_cl_device*")
                pyrpr.ContextGetInfo(self.core_context, pyrpropencl.DEVICE, sys.getsizeof(cl_device),
                                     cl_device, pyrpropencl.ffi.NULL)

                cl_command_queue = pyrpropencl.ffi.new("rpr_cl_command_queue*")
                pyrpr.ContextGetInfo(self.core_context, pyrpropencl.COMMAND_QUEUE, sys.getsizeof(cl_command_queue),
                                     cl_command_queue, pyrpropencl.ffi.NULL)

                pyrprimagefilters.CreateContextFromOpenClContext(pyrprimagefilters.API_VERSION, cl_context[0], cl_device[0],
                                                                 cl_command_queue[0], pyrprimagefilters.ffi.NULL,
                                                                 self.rif_context)

            # Create command queue for filtering
            self.rif_command_queue = pyrprimagefilters.RifCommandQueue()
            pyrprimagefilters.ContextCreateCommandQueue(self.rif_context, self.rif_command_queue)

        except pyrpr.CoreError:
            self.rif_context = None
            logging.error("Denoiser will not work, hardware is not entirely supported this release.", tag="device.create_rif_context")
            raise


    def get_rif_context(self):
        return self.rif_context

    def attach_render_target(self, render_target):
        if self.render_target:
            self.render_target.detach()
        self.render_target = render_target
        self.render_target.attach()

    def detach_render_target(self, render_target):
        self.render_target.detach()
        self.render_target = None

    def attach_posteffect(self, name):
        if name not in self.post_effects:
            post_effect = pyrpr.PostEffect()
            self.post_effects[name] = post_effect
            pyrpr.ContextCreatePostEffect(self.core_context, name, post_effect)
            pyrpr.ContextAttachPostEffect(self.core_context, post_effect)
        return self.post_effects[name]

    def detach_posteffect(self, post_effect):
        pyrpr.ContextDetachPostEffect(self.core_context, self.post_effects[post_effect])
        self.post_effects[post_effect].delete()
        del self.post_effects[post_effect]

    def update_downscaled_image_size(self, is_production):
        settings = bpy.context.scene.rpr.render
        size = None
        if (not is_production or settings.downscale_textures_production) and \
                    settings.downscale_textures_size != 'NONE':
            if settings.downscale_textures_size == 'AUTO':
                size = images.get_automatic_compression_size(bpy.context.scene)
            else:
                size = int(settings.downscale_textures_size)
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

