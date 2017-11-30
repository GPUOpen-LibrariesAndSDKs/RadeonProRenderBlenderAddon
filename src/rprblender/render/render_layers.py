#!python3

import numpy as np

import bpy

import rprblender
import rprblender.render
import rprblender.render.device
from rprblender.helpers import CallLogger
from . import logging

import pyrprimagefilters

call_logger = CallLogger(tag='render')


def prepare_image(fb_image):
    return np.flipud(fb_image)


def extract_settings(aov_settings):
    """ copy aov settings from Blender data"""
    class Settings:
        enable = aov_settings.enable
        pass_displayed = aov_settings.pass_displayed
        passes_states = list(aov_settings.passesStates)
        passes_names = [item[0] for item in aov_settings.render_passes_items]
        transparent = aov_settings.transparent

        def __eq__(self, other):
            """ used in interactive(viewport) render to check if aov needs reset"""
            return all(getattr(self, name) == getattr(other, name) for name in dir(self)
                       if not name.startswith('__'))

    return Settings()


class RenderLayers:

    displayed_layer = None

    def __init__(self, aov_settings, render_targets, is_production=False):
        logging.info('RenderLayers create...')

        self.is_production = is_production

        self.render_targets = render_targets

        self.context = render_targets.render_device.core_context
        self.alpha_combine = aov_settings.transparent

        self.init_data(aov_settings)

        self.use_denoiser = False
        self.filter_type = pyrprimagefilters.IMAGE_FILTER_BILATERAL_DENOISE

        for p in self.get_needed_passes(aov_settings):
            self.enable_aov(p)

    def get_needed_passes(self, aov_settings):
        # always create color fb(needed by RPR)
        yield 'default'

        if self.use_denoiser:
            if self.filter_type == pyrprimagefilters.IMAGE_FILTER_BILATERAL_DENOISE:
                yield 'geometric_normal'
                yield 'world_coordinate'

        if self.alpha_combine:
            yield 'opacity'

        if aov_settings is None or not aov_settings.enable:
            return

        if self.is_production:
            for i in range(len(aov_settings.passes_names)):
                state = aov_settings.passes_states[i]
                name = aov_settings.passes_names[i]
                if state and name != 'default':
                    yield name
        else:
            if 'default' != self.displayed_layer:
                yield self.displayed_layer


    def init_data(self, aov_settings):
        self.displayed_layer = aov_settings.pass_displayed if aov_settings.pass_displayed else 'default'

    def update(self, aov_settings):
        self.init_data(aov_settings)

        passes_needed = set(self.get_needed_passes(aov_settings))
        passes_all = set(aov_settings.passes_names)

        for name in passes_all:
            if name in passes_needed and not self.render_targets.is_aov_enabled(name):
                self.render_targets.enable_aov(name)
            if name not in passes_needed and self.render_targets.is_aov_enabled(name):
                self.render_targets.disable_aov(name)

    @call_logger.logged
    def prepare_image_by_layer(self, name, im, opacity):

        prepared_im = prepare_image(im)
        if opacity is not None:
            prepared_im = prepared_im.copy()
            alpha = prepare_image(opacity)[:, :, 0]
            prepared_im[..., 3] = alpha
        return np.ascontiguousarray(prepared_im)

    def enable_aov(self, aov_name):
        self.render_targets.enable_aov(aov_name)


def pass_to_aov_name(pass_name):
    return pass2aov.get(pass_name or 'Combined', None)


pass2info = {
    # standard Blender passes that are compatible with RPR by name and semantics
    'Combined': (4, "RGBA", 'COLOR'),
    'UV': (3, "UVA", 'VECTOR'),

    # standard Blender passes that can be used by RPR, for Blender <2.79, but not very compatible with RPR
    # namings - e.g. no World coordinate, we are using Vector(Speed)
    'IndexOB': (1, "X", 'VALUE'),
    'IndexMA': (1, "X", 'VALUE'),
    'Vector': (4, "XYZW", 'VECTOR'),
    'Emit': (3, "RGB", 'COLOR'),
    'Normal': (3, "XYZ", 'VECTOR'),

    # custom Blender passes, thanks to 2.79
    # https://wiki.blender.org/index.php/Dev:Ref/Release_Notes/2.79/Add-ons
    'Object Index': (3, "RGB", 'VECTOR'),
    'Material Index': (3, "RGB", 'VECTOR'),
    'World Coordinate': (3, "XYZ", 'VECTOR'),
    'Geometric Normal': (3, "XYZ", 'VECTOR'),
    'Shading Normal': (3, "XYZ", 'VECTOR'),
}

pass_and_aov = [
    ('Combined', 'default'),
    ('UV', 'uv'),
]

# Blender 2.79
use_custom_passes = (2, 78, 5) <= bpy.app.version

if use_custom_passes:
    pass2info.update({
        'Z': (1, "Z", 'VALUE'),
    })

    pass_and_aov.extend(
        [
            ('Object Index', 'object_id'),
            ('Material Index', 'material_idx'),
            ('World Coordinate', 'world_coordinate'),
            ('Geometric Normal', 'geometric_normal'),
            ('Shading Normal', 'shading_normal'),
            ('Z', 'depth'),
        ]
    )
else:
    pass2info.update({
        'Depth': (1, "Z", 'VALUE'),
    })

    pass_and_aov.extend(
        [
            ('IndexOB', 'object_id'),
            ('IndexMA', 'material_idx'),
            ('Vector', 'world_coordinate'),
            ('Emit', 'geometric_normal'),
            ('Normal', 'shading_normal'),
            ('Depth', 'depth'),
        ]
    )

aov2pass = {aov: pass_ for pass_, aov in pass_and_aov}
pass2aov = {pass_:aov for pass_, aov in pass_and_aov}
