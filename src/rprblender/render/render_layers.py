#!python3
import bpy
# import math
# from . import rpraddon
import numpy as np
import pyrpr
from pyrpr import ffi

import rprblender
import rprblender.render
from rprblender.helpers import CallLogger
from . import logging

call_logger = CallLogger(tag='render')


@call_logger.logged
def get_core_frame_buffer_image(width, height, render_buffer):
    fb_data_size_ptr = ffi.new('size_t*', 0)
    pyrpr.FrameBufferGetInfo(render_buffer, pyrpr.FRAMEBUFFER_DATA, 0, ffi.NULL, fb_data_size_ptr);

    fb_data_size = fb_data_size_ptr[0]

    arr = np.empty((height, width, 4), dtype=np.float32)
    assert arr.nbytes == fb_data_size, (arr.nbytes, fb_data_size)

    pyrpr.FrameBufferGetInfo(render_buffer, pyrpr.FRAMEBUFFER_DATA, fb_data_size,
                             ffi.cast('float*', arr.ctypes.data), ffi.NULL);

    # pyrpr.FrameBufferClear(self.render_buffer)
    return arr


def prepare_image(fb_image):
    im = np.flipud(fb_image)
    # divide by 4-th component(pixel accumulation/exposure)
    w = im[:, :, 3]  # type: np.ndarray
    if np.all(0 != w):
        im /= np.repeat(w[:, :, np.newaxis], 4, axis=2)
    return im


def get_image(width, height, render_buffer):
    with rprblender.render.core_operations(raise_error=True):
        fb_image = get_core_frame_buffer_image(width, height, render_buffer)
    return fb_image


def extract_settings(render_settings):
    aov_settings = render_settings.passes_aov

    class Settings:
        enable = aov_settings.enable
        pass_displayed = aov_settings.pass_displayed
        passes_states = list(aov_settings.passesStates)
        passes_names = [item[0] for item in aov_settings.render_passes_items]
        transparent = aov_settings.transparent

    return Settings()


class AOV:
    def convert_name_to_rpr_aov(self, name):
        if name == 'default':
            return pyrpr.AOV_COLOR
        elif name == 'opacity':
            return pyrpr.AOV_OPACITY
        elif name == 'world_coordinate':
            return pyrpr.AOV_WORLD_COORDINATE
        elif name == 'uv':
            return pyrpr.AOV_UV
        elif name == 'material_idx':
            return pyrpr.AOV_MATERIAL_IDX
        elif name == 'geometric_normal':
            return pyrpr.AOV_GEOMETRIC_NORMAL
        elif name == 'shading_normal':
            return pyrpr.AOV_SHADING_NORMAL
        elif name == 'depth':
            return pyrpr.AOV_DEPTH
        elif name == 'object_id':
            return pyrpr.AOV_OBJECT_ID
        assert False

    def __init__(self, aov_name, context, render_resolution):
        self.context = context
        self.aov = self.convert_name_to_rpr_aov(aov_name)
        desc = ffi.new("rpr_framebuffer_desc*")
        self.width, self.height = render_resolution
        desc.fb_width, desc.fb_height = self.width, self.height

        fmt = (4, pyrpr.COMPONENT_TYPE_FLOAT32)
        self.render_buffer = pyrpr.FrameBuffer()
        pyrpr.ContextCreateFrameBuffer(context, fmt, desc, self.render_buffer)
        pyrpr.ContextSetAOV(context, self.aov, self.render_buffer)

    def clear(self):
        pyrpr.FrameBufferClear(self.render_buffer)

    def get_core_frame_buffer_image(self):
        return get_core_frame_buffer_image(self.width, self.height, self.render_buffer)

    def __del__(self):
        pyrpr.ContextSetAOV(self.context, self.aov, ffi.NULL)
        # pyrpr.ObjectDelete(self.render_buffer)


class RenderLayers:
    def add_aov(self, aov_name):
        if aov_name in self.aovs:
            return

        self.aovs[aov_name] = AOV(aov_name, self.context, self.render_resolution)
        logging.info('added aov: "%s", ok' % aov_name)

    def is_aov_changed(self, aov_settings):
        bits_count = 0
        new_hash = 0

        # pass_displayed
        index = next(i for i, name in enumerate(aov_settings.passes_names) if name == aov_settings.pass_displayed)
        new_hash |= 1 << (index + bits_count)
        bits_count += len(aov_settings.passes_names)

        # enable
        if aov_settings.enable:
            new_hash |= 1 << bits_count
        bits_count += 1

        # passes
        for i in range(len(aov_settings.passes_states)):
            if aov_settings.passes_states[i]:
                new_hash |= 1 << (i + bits_count)
        bits_count += len(aov_settings.passes_states)

        if self.aov_hash == new_hash:
            return False

        # logging.info("aov is changed")
        self.aov_hash = new_hash
        return True

    def __init__(self, aov_settings, context, render_resolution):
        logging.info('RenderLayers create...')

        self.aov_hash = -1

        self.aovs = {}
        self.context = context
        self.render_resolution = render_resolution
        self.alpha_combine = aov_settings.transparent

        self.init_data(aov_settings)

    def init_data(self, aov_settings):
        self.enable = aov_settings is not None and aov_settings.enable

        # create by default
        self.add_aov('default')
        if self.alpha_combine:
            self.add_aov('opacity')

        if not self.enable:
            self.displayed_layer = 'default'
            return

        self.displayed_layer = aov_settings.pass_displayed

        for i in range(len(aov_settings.passes_names)):
            state = aov_settings.passes_states[i]
            name = aov_settings.passes_names[i]
            if state or name == self.displayed_layer and name != 'default':
                self.add_aov(name)

    def data_was_changed(self, aov_settings):
        # remove unused
        for i in range(len(aov_settings.passes_names)):
            state = aov_settings.passes_states[i]
            name = aov_settings.passes_names[i]
            if name == 'default':
                continue
            if not state or not aov_settings.enable:
                if name in self.aovs:
                    logging.info('remove: ', name)
                    del self.aovs[name]

        # create new & set displayed
        self.init_data(aov_settings)

    def get_image(self, aov_name=''):
        name = aov_name if aov_name != '' else self.displayed_layer
        if name not in self.aovs:
            return None
        with rprblender.render.core_operations(raise_error=True):
            fb_image = self.aovs[name].get_core_frame_buffer_image()

        return fb_image

    def get_frame_buffer(self):
        return self.aovs['default'].render_buffer

    def prepare_image_by_layer(self, name, im):
        prepared_im = prepare_image(im)
        if self.alpha_combine and 'opacity' in self.aovs:
            with rprblender.render.core_operations(raise_error=True):
                fb_opacity = self.aovs['opacity'].get_core_frame_buffer_image()
                opacity_im = prepare_image(fb_opacity)

            color = prepared_im[:, :, 0:3]
            alpha = opacity_im[:, :, 0:1]
            prepared_im = np.append(color, alpha, axis=2)

        return np.ascontiguousarray(prepared_im)

        # @staticmethod
        # def pass_to_aov_name(pass_name):
        #     if pass_name == 'VECTOR':
        #         return 'world_coordinate'
        #     if pass_name == 'UV':
        #         return 'uv'
        #     if pass_name == 'MATERIAL_INDEX':
        #         return 'material_idx'
        #     if pass_name == 'EMIT':
        #         return 'geometric_normal'
        #     if pass_name == 'NORMAL':
        #         return 'shading_normal'
        #     if pass_name == 'Z':
        #         return 'depth'
        #     if pass_name == 'OBJECT_INDEX':
        #         return 'object_id'
        #     return 'default'  # and 'COMBINED'


def pass_to_aov_name(pass_name):
    return pass2aov.get(pass_name or 'Combined', None)


pass2info = {
    # standard Blender passes that are compatible with RPR by name and semantics
    'Combined': (4, "RGBA", 'COLOR'),
    'Depth': (1, "Z", 'VALUE'),
    'Normal': (3, "XYZ", 'VECTOR'),
    'UV': (3, "UVA", 'VECTOR'),

    # standard Blender passes that can be used by RPR, for Blender <2.79, but not very compatible with RPR
    # namings - e.g. no World coordinate, we are using Vector(Speed)
    'IndexOB': (1, "X", 'VALUE'),
    'IndexMA': (1, "X", 'VALUE'),
    'Vector': (4, "XYZW", 'VECTOR'),
    'Emit': (3, "RGB", 'COLOR'),

    # custom Blender passes, thanks to 2.79
    # https://wiki.blender.org/index.php/Dev:Ref/Release_Notes/2.79/Add-ons
    'Object Index': (3, "RGB", 'COLOR'),
    'Material Index': (3, "RGB", 'COLOR'),
    'World Coordinate': (3, "XYZ", 'VECTOR'),
    'Geometric Normal': (3, "XYZ", 'VECTOR'),
}

pass2aov = {
    'Combined': 'default',
    'Depth': 'depth',
    'Normal': 'shading_normal',
    'UV': 'uv',
}

# Blender 2.79
use_custom_passes = (2, 78, 5) <= bpy.app.version

if use_custom_passes:
    pass2aov.update(
        {
            'Object Index': 'object_id',
            'Material Index': 'material_idx',
            'World Coordinate': 'world_coordinate',
            'Geometric Normal': 'geometric_normal',
        }
    )
else:
    pass2aov.update(
        {
            'IndexOB': 'object_id',
            'IndexMA': 'material_idx',
            'Vector': 'world_coordinate',
            'Emit': 'geometric_normal',
        }
    )

aov2pass = {aov: pass_ for pass_, aov in pass2aov.items()}
