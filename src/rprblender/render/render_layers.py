#!python3

import numpy as np

import bpy

import rprblender
import rprblender.render
import rprblender.render.device
from rprblender.helpers import CallLogger
from . import logging
import rprblender.versions as versions

import pyrpr
import pyrprimagefilters

call_logger = CallLogger(tag='render')


def prepare_image(fb_image):
    return np.flipud(fb_image)


def extract_settings(passes_aov):
    """ copy aov settings from Blender data"""

    return extract_settings_list([("", passes_aov)], 0)


def extract_settings_list(passes_aov_list, active_index):
    active_aov = passes_aov_list[active_index][1]

    # unify passes states from all layers
    unified_states = [False] * len(active_aov.passesStates)
    for p in passes_aov_list:
        if not p[1].enable:
            continue
        for i, val in enumerate(p[1].passesStates):
            unified_states[i] |= val
                          
    class Settings:
        enable = active_aov.enable
        pass_displayed = active_aov.pass_displayed
        passes_states = unified_states
        passes_names = [item[0] for item in active_aov.render_passes_items]
        transparent = active_aov.transparent

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
                yield 'object_id'

            if self.filter_type == pyrprimagefilters.IMAGE_FILTER_LWR_DENOISE or \
                            self.filter_type == pyrprimagefilters.IMAGE_FILTER_EAW_DENOISE:
                yield 'geometric_normal'
                yield 'depth'
                yield 'object_id'
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


aov_info = {'default': 
                {'name': 'Combined',
                 'old_name': 'Combined', 
                 'old_use_pass': 'use_pass_combined',
                 'descr': 'Full Combined RGBA buffer',
                 'channel': 'RGBA', 
                 'rpr': pyrpr.AOV_COLOR,
                 'order': 1},
            'depth': 
                {'name': 'Depth',
                 'old_name': 'Depth', 
                 'old_use_pass': 'use_pass_z',
                 'descr': 'Depth Z values',
                 'channel': 'Z', 
                 'rpr': pyrpr.AOV_DEPTH,
                 'order': 2},
            'uv': 
                {'name': 'UV', 
                 'old_name': 'UV',
                 'old_use_pass': 'use_pass_uv',
                 'channel': 'UVA', 
                 'rpr': pyrpr.AOV_UV,
                 'order': 3},
            'object_id': 
                {'name': 'Object Index', 
                 'old_name': 'IndexOB',
                 'old_use_pass': 'use_pass_object_index',
                 'channel': 'X', 
                 'rpr': pyrpr.AOV_OBJECT_ID,
                 'order': 4},
            'material_idx': 
                {'name': 'Material Index', 
                 'old_name': 'IndexMA',
                 'old_use_pass': 'use_pass_material_index',
                 'channel': 'X', 
                 'rpr': pyrpr.AOV_MATERIAL_IDX,
                 'order': 5},
            'world_coordinate': 
                {'name': 'World Coordinate', 
                 'old_name': 'Vector',
                 'old_use_pass': 'use_pass_vector',
                 'channel': 'XYZ', 
                 'rpr': pyrpr.AOV_WORLD_COORDINATE,
                 'order': 6},
            'geometric_normal': 
                {'name': 'Geometric Normal', 
                 'old_name': 'Normal',
                 'old_use_pass': 'use_pass_normal',
                 'channel': 'XYZ', 
                 'rpr': pyrpr.AOV_GEOMETRIC_NORMAL,
                 'order': 7},
            'shading_normal': 
                {'name': 'Shading Normal', 
                 'channel': 'XYZ', 
                 'rpr': pyrpr.AOV_SHADING_NORMAL,
                 'order': 8},
            'object_group_id': 
                {'name': 'Group Index', 
                 'channel': 'X', 
                 'rpr': pyrpr.AOV_OBJECT_GROUP_ID,
                 'order': 9},
            'shadow_catcher': 
                {'name': 'Shadow Catcher', 
                 'old_name': 'Shadow',
                 'old_use_pass': 'use_pass_shadow',
                 'channel': 'RGBA', 
                 'rpr': pyrpr.AOV_SHADOW_CATCHER,
                 'order': 10},
            'background': 
                {'name': 'Background', 
                 'old_name': 'Env',
                 'old_use_pass': 'use_pass_environment',
                 'channel': 'RGB', 
                 'rpr': pyrpr.AOV_BACKGROUND,
                 'order': 11},
            'emission': 
                {'name': 'Emission', 
                 'old_name': 'Emit',
                 'old_use_pass': 'use_pass_emit',
                 'channel': 'RGB', 
                 'rpr': pyrpr.AOV_EMISSION,
                 'order': 12},
            'velocity': 
                {'name': 'Velocity', 
                 'descr': 'Velocity Vector',
                 'channel': 'XYZ', 
                 'rpr': pyrpr.AOV_VELOCITY,
                 'order': 13},
            'direct_illumination': 
                {'name': 'Direct Illumination', 
                 'channel': 'RGB', 
                 'rpr': pyrpr.AOV_DIRECT_ILLUMINATION,
                 'order': 14},
            'indirect_illumination': 
                {'name': 'Indirect Illumination', 
                 'channel': 'RGB', 
                 'rpr': pyrpr.AOV_INDIRECT_ILLUMINATION,
                 'order': 15},
            'ambient_occlusion': 
                {'name': 'Ambient Occlusion', 
                 'old_name': 'AO',
                 'old_use_pass': 'use_pass_ambient_occlusion',
                 'channel': 'RGB', 
                 'rpr': pyrpr.AOV_AO,
                 'order': 16},
            'direct_diffuse': 
                {'name': 'Direct Diffuse', 
                 'old_name': 'DiffDir',
                 'old_use_pass': 'use_pass_diffuse_direct',
                 'channel': 'RGB', 
                 'rpr': pyrpr.AOV_DIRECT_DIFFUSE,
                 'order': 17},
            'direct_reflect': 
                {'name': 'Direct Reflection', 
                 'old_name': 'GlossDir',
                 'old_use_pass': 'use_pass_glossy_direct',
                 'channel': 'RGB', 
                 'rpr': pyrpr.AOV_DIRECT_REFLECT,
                 'order': 18},
            'indirect_diffuse': 
                {'name': 'Indirect Diffuse', 
                 'old_name': 'DiffInd',
                 'old_use_pass': 'use_pass_diffuse_indirect',
                 'channel': 'RGB', 
                 'rpr': pyrpr.AOV_INDIRECT_DIFFUSE,
                 'order': 19},
            'indirect_reflect': 
                {'name': 'Indirect Reflection', 
                 'old_name': 'GlossInd',
                 'old_use_pass': 'use_pass_glossy_indirect',
                 'channel': 'RGB', 
                 'rpr': pyrpr.AOV_INDIRECT_REFLECT,
                 'order': 20},
            'refract': 
                {'name': 'Refraction', 
                 'old_name': 'Refract',
                 'old_use_pass': 'use_pass_refraction',
                 'channel': 'RGB', 
                 'rpr': pyrpr.AOV_REFRACT,
                 'order': 21},
            'volume': 
                {'name': 'Volume', 
                 'channel': 'RGB', 
                 'rpr': pyrpr.AOV_VOLUME,
                 'order': 22},
            'opacity': 
                {'name': 'Opacity', 
                 'channel': 'A', 
                 'rpr': pyrpr.AOV_OPACITY,
                 'order': 23},
            }

if versions.is_blender_support_aov():
    pass2aov = {val['name']: key for key, val in aov_info.items()}
else:
    pass2aov = {val['old_name']: key for key, val in aov_info.items() if val.get('old_name', None)}

def pass_to_aov_name(pass_name):
    return pass2aov.get(pass_name or 'Combined', None)

def register_pass(render_engine, scene, render_layer, pass_name):
    pass_item = aov_info.get(pass_name, None)
    if not pass_item:
        return
    blender_type = 'VALUE'
    channel_type = pass_item['channel']
    # convert from channel to blender type
    if 'RGB' in channel_type:
        blender_type = 'COLOR'
    elif channel_type in {'XYZ', 'UVA'}:
        blender_type = 'VECTOR'

    render_engine.register_pass(scene, render_layer, pass_item['name'], len(channel_type), 
                                channel_type, blender_type)

