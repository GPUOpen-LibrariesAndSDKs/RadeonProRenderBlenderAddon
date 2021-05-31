#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
''' Engine is the functionality of the rendering process, 
maintains context, processes, etc.

Other modules in this directory could be viewport, etc.
'''

''' main Render object '''

import weakref
import numpy as np

import bpy
import pyrpr

from .context import RPRContext, RPRContext2
from rprblender.export import object, instance, mesh
from rprblender.properties.view_layer import RPR_ViewLayerProperites
from . import image_filter

from rprblender.utils import logging
log = logging.Log(tag='Engine')


ITERATED_OBJECT_TYPES = ('MESH', 'LIGHT', 'CURVE', 'FONT', 'SURFACE', 'META', 'VOLUME')


class Engine:
    """ This is the basic Engine class """

    TYPE = None

    # RPRContext class
    _RPRContext = RPRContext

    def __init__(self, rpr_engine):
        self.rpr_engine = weakref.proxy(rpr_engine)
        self.rpr_context = self._RPRContext()
        self.rpr_context.engine_type = self.TYPE

        # image filters
        self.image_filter = None
        self.background_filter = None
        self.upscale_filter = None

        self.result = None

    def stop_render(self):
        self.rpr_context = None
        self.image_filter = None
        self.background_filter = None

    def _set_render_result(self, render_passes: bpy.types.RenderPasses, apply_image_filter, tile_pos, tile_size):
        """
        Sets render result to render passes
        :param render_passes: render passes to collect
        :return: images
        """
        def zeros_image(channels):
            return np.zeros((self.rpr_context.height, self.rpr_context.width, channels), dtype=np.float32)

        images = []

        x1, y1 = tile_pos
        x2, y2 = x1 + tile_size[0], y1 + tile_size[1]

        for p in render_passes:
            # finding corresponded aov

            if p.name == "Combined":
                if apply_image_filter and self.image_filter:
                    image = self.image_filter.get_data()

                    if self.background_filter:
                        # calculate background effects on denoised image and cut out by tile size
                        self.update_background_filter_inputs(tile_pos=tile_pos, color_image=image)
                        self.background_filter.run()
                        image = self.background_filter.get_data()[y1:y2, x1:x2, :]
                    else:
                        # copying alpha component from rendered image to final denoised image,
                        # because image filter changes it to 1.0
                        image[:, :, 3] = self.rpr_context.get_image()[:, :, 3]

                elif self.background_filter:
                    # calculate background effects and cut out by tile size
                    self.update_background_filter_inputs(tile_pos=tile_pos)
                    self.background_filter.run()
                    image = self.background_filter.get_data()[y1:y2, x1:x2, :]
                else:
                    image = self.rpr_context.get_image()

            elif p.name == "Color":
                image = self.rpr_context.get_image(pyrpr.AOV_COLOR)

            elif p.name == "Outline":
                # set outline to black for now
                image = zeros_image(4)

            else:
                aovs_info = RPR_ViewLayerProperites.cryptomatte_aovs_info \
                    if "Cryptomatte" in p.name else RPR_ViewLayerProperites.aovs_info
                aov = next((aov for aov in aovs_info
                            if aov['name'] == p.name), None)
                if aov and self.rpr_context.is_aov_enabled(aov['rpr']):
                    image = self.rpr_context.get_image(aov['rpr'])
                elif p.name != 'Outline':
                    log.warn(f"AOV '{p.name}' is not enabled in rpr_context "
                             f"or not found in aovs_info")
                    image = zeros_image(p.channels)

            if p.channels != image.shape[2]:
                image = image[:, :, 0:p.channels]

            images.append(image.flatten())

        # efficient way to copy all AOV images
        render_passes.foreach_set('rect', np.concatenate(images))

    def update_render_result(self, tile_pos, tile_size, layer_name="",
                             apply_image_filter=False):
        if not self.result:
            self.result = self.rpr_engine.begin_result(*tile_pos, *tile_size, layer=layer_name)
        self._set_render_result(self.result.layers[0].passes, apply_image_filter, tile_pos, tile_size)
        self.rpr_engine.update_result(self.result)

    def depsgraph_objects(self, depsgraph: bpy.types.Depsgraph, with_camera=False):
        """ Iterates evaluated objects in depsgraph with ITERATED_OBJECT_TYPES """

        object_types = ITERATED_OBJECT_TYPES if not with_camera else (ITERATED_OBJECT_TYPES + ('CAMERA',))

        for obj in depsgraph.objects:
            if obj.type in object_types:
                yield obj

    def depsgraph_instances(self, depsgraph: bpy.types.Depsgraph):
        """ Iterates evaluated instances in depsgraph with ITERATED_OBJECT_TYPES """

        # Comment from Depsgrapgh.object_instances description:
        # WARNING: only use this as an iterator, never as a sequence, and do not keep any references to its items
        for instance in depsgraph.object_instances:
            if instance.is_instance and instance.object.type in ITERATED_OBJECT_TYPES:
                yield instance

    def cache_blur_data(self, depsgraph: bpy.types.Depsgraph):
        cur_frame = depsgraph.scene.frame_current

        # set to next frame and cache blur data
        self._set_scene_frame(depsgraph.scene, cur_frame + 1, 0.0)

        try:
            for obj in self.depsgraph_objects(depsgraph, with_camera=True):
                object.cache_blur_data(self.rpr_context, obj)

            for inst in self.depsgraph_instances(depsgraph):
                instance.cache_blur_data(self.rpr_context, inst)

        finally:
            self._set_scene_frame(depsgraph.scene, cur_frame, 0.0)

    def _set_scene_frame(self, scene, frame, subframe=0.0):
        self.rpr_engine.frame_set(frame, subframe)

    def set_motion_blur_mode(self, scene):
        """ Apply engine-specific motion blur parameters """
        pass

    def setup_image_filter(self, settings):
        if self.image_filter and self.image_filter.settings == settings:
            return False

        if settings['enable']:
            if not self.image_filter:
                self._enable_image_filter(settings)

            elif self.image_filter.settings['resolution'] == settings['resolution'] \
                    and self.image_filter.settings['filter_type'] == settings['filter_type'] \
                    and self.image_filter.settings['filter_type'] != 'ML':
                self._update_image_filter(settings)

            else:
                # recreating filter
                self._disable_image_filter()
                self._enable_image_filter(settings)

        elif self.image_filter:
            self._disable_image_filter()

        return True

    def _enable_image_filter(self, settings):
        width, height = settings['resolution']

        # Enabling AOV's which are used in all filters
        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)

        if settings['filter_type'] == 'BILATERAL':
            self.rpr_context.enable_aov(pyrpr.AOV_WORLD_COORDINATE)
            self.rpr_context.enable_aov(pyrpr.AOV_OBJECT_ID)
            self.rpr_context.enable_aov(pyrpr.AOV_SHADING_NORMAL)

            inputs = {'color', 'normal', 'world_coordinate', 'object_id'}
            sigmas = {
                'color': settings['color_sigma'],
                'normal': settings['normal_sigma'],
                'world_coordinate': settings['p_sigma'],
                'object_id': settings['trans_sigma'],
            }
            params = {'radius': settings['radius']}
            self.image_filter = image_filter.ImageFilterBilateral(
                self.rpr_context.context, inputs, sigmas, params, width, height)

        elif settings['filter_type'] == 'EAW':
            self.rpr_context.enable_aov(pyrpr.AOV_WORLD_COORDINATE)
            self.rpr_context.enable_aov(pyrpr.AOV_OBJECT_ID)
            self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)
            self.rpr_context.enable_aov(pyrpr.AOV_SHADING_NORMAL)

            inputs = {'color', 'normal', 'depth', 'trans', 'world_coordinate', 'object_id'}
            sigmas = {
                'color': settings['color_sigma'],
                'normal': settings['normal_sigma'],
                'depth': settings['depth_sigma'],
                'trans': settings['trans_sigma'],
            }
            self.image_filter = image_filter.ImageFilterEaw(
                self.rpr_context.context, inputs, sigmas, {}, width, height)

        elif settings['filter_type'] == 'LWR':
            self.rpr_context.enable_aov(pyrpr.AOV_WORLD_COORDINATE)
            self.rpr_context.enable_aov(pyrpr.AOV_OBJECT_ID)
            self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)
            self.rpr_context.enable_aov(pyrpr.AOV_SHADING_NORMAL)

            inputs = {'color', 'normal', 'depth', 'trans', 'world_coordinate', 'object_id'}
            params = {
                'samples': settings['samples'],
                'halfWindow': settings['half_window'],
                'bandwidth': settings['bandwidth'],
            }
            self.image_filter = image_filter.ImageFilterLwr(
                self.rpr_context.context, inputs, {}, params, width, height)

        elif settings['filter_type'] == 'ML':
            inputs = {'color'}
            params = {}

            if not settings['ml_color_only']:
                self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)
                self.rpr_context.enable_aov(pyrpr.AOV_DIFFUSE_ALBEDO)
                self.rpr_context.enable_aov(pyrpr.AOV_SHADING_NORMAL)
                inputs |= {'normal', 'depth', 'albedo'}

            from .viewport_engine import ViewportEngine
            import pyrprimagefilters as rif
            if settings['ml_use_fp16_compute_type']:
                params['compute_type'] = rif.COMPUTE_TYPE_FLOAT16
            else:
                params['compute_type'] = rif.COMPUTE_TYPE_FLOAT

            self.image_filter = image_filter.ImageFilterML(
                self.rpr_context.context, inputs, {}, params, width, height)

        self.image_filter.settings = settings

    def _disable_image_filter(self):
        self.image_filter = None

    def _update_image_filter(self, settings):
        self.image_filter.settings = settings

        if settings['filter_type'] == 'BILATERAL':
            self.image_filter.update_sigma('color', settings['color_sigma'])
            self.image_filter.update_sigma('normal', settings['normal_sigma'])
            self.image_filter.update_sigma('world_coordinate', settings['p_sigma'])
            self.image_filter.update_sigma('object_id', settings['trans_sigma'])
            self.image_filter.update_param('radius', settings['radius'])

        elif settings['filter_type'] == 'EAW':
            self.image_filter.update_sigma('color', settings['color_sigma'])
            self.image_filter.update_sigma('normal', settings['normal_sigma'])
            self.image_filter.update_sigma('depth', settings['depth_sigma'])
            self.image_filter.update_sigma('trans', settings['trans_sigma'])

        elif settings['filter_type'] == 'LWR':
            self.image_filter.update_param('samples', settings['samples'])
            self.image_filter.update_param('halfWindow', settings['half_window'])
            self.image_filter.update_param('bandwidth', settings['bandwidth'])

    def update_image_filter_inputs(self, tile_pos=(0, 0)):
        color = self.rpr_context.get_image()

        filter_type = self.image_filter.settings['filter_type']
        if filter_type == 'BILATERAL':
            world = self.rpr_context.get_image(pyrpr.AOV_WORLD_COORDINATE)
            object_id = self.rpr_context.get_image(pyrpr.AOV_OBJECT_ID)
            shading = self.rpr_context.get_image(pyrpr.AOV_SHADING_NORMAL)

            inputs = {
                'color': color,
                'normal': shading,
                'world_coordinate': world,
                'object_id': object_id,
            }

        elif filter_type == 'EAW':
            world = self.rpr_context.get_image(pyrpr.AOV_WORLD_COORDINATE)
            object_id = self.rpr_context.get_image(pyrpr.AOV_OBJECT_ID)
            depth = self.rpr_context.get_image(pyrpr.AOV_DEPTH)
            shading = self.rpr_context.get_image(pyrpr.AOV_SHADING_NORMAL)

            inputs = {
                'color': color,
                'normal': shading,
                'depth': depth,
                'trans': object_id,
                'world_coordinate': world,
                'object_id': object_id,
            }

        elif filter_type == 'LWR':
            world = self.rpr_context.get_image(pyrpr.AOV_WORLD_COORDINATE)
            object_id = self.rpr_context.get_image(pyrpr.AOV_OBJECT_ID)
            depth = self.rpr_context.get_image(pyrpr.AOV_DEPTH)
            shading = self.rpr_context.get_image(pyrpr.AOV_SHADING_NORMAL)

            inputs = {
                'color': color,
                'normal': shading,
                'depth': depth,
                'trans': object_id,
                'world_coordinate': world,
                'object_id': object_id,
            }

        elif filter_type == 'ML':
            inputs = {'color': color}

            if not self.image_filter.settings['ml_color_only']:
                inputs['depth'] = self.rpr_context.get_image(pyrpr.AOV_DEPTH)
                inputs['albedo'] = self.rpr_context.get_image(pyrpr.AOV_DIFFUSE_ALBEDO)
                inputs['normal'] = self.rpr_context.get_image(pyrpr.AOV_SHADING_NORMAL)

        else:
            raise ValueError("Incorrect filter type", filter_type)

        for input_id, data in inputs.items():
            self.image_filter.update_input(input_id, data, tile_pos)

    def setup_background_filter(self, settings):
        if self.background_filter and self.background_filter.settings == settings:
            return False

        if settings['enable']:
            if not self.background_filter:
                self._enable_background_filter(settings)

            elif self.background_filter.settings['resolution'] == settings['resolution']:
                return False

            else:
                # recreating filter
                self._disable_background_filter()
                self._enable_background_filter(settings)

        elif self.background_filter:
            self._disable_background_filter()

        return True

    def _enable_background_filter(self, settings):
        width, height = settings['resolution']
        use_background = settings['use_background']
        use_shadow = settings['use_shadow']
        use_reflection = settings['use_reflection']

        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.enable_aov(pyrpr.AOV_OPACITY)

        inputs = {'color', 'opacity'}

        if not use_background and not use_reflection:
            # The RPR2 applies a lonely Shadow catcher as a part of Color AOV, nothing to do here
            return

        if use_shadow:
            self.rpr_context.enable_aov(pyrpr.AOV_SHADOW_CATCHER)
            inputs.add('shadow_catcher')
        if use_reflection:
            self.rpr_context.enable_aov(pyrpr.AOV_REFLECTION_CATCHER)
            inputs.add('reflection_catcher')
        if use_reflection or use_shadow:
            self.rpr_context.enable_aov(pyrpr.AOV_BACKGROUND)
            inputs.add('background')

        params = {'use_background': use_background, 'use_shadow': use_shadow, 'use_reflection': use_reflection}

        self.background_filter = image_filter.ImageFilterTransparentShadowReflectionCatcher(
            self.rpr_context.context, inputs, {}, params, width, height
        )

        self.background_filter.settings = settings

    def _disable_background_filter(self):
        self.background_filter = None

    def update_background_filter_inputs(
            self, tile_pos=(0, 0),
            color_image=None, opacity_image=None):
        """
        Update background filter input images.
        Use color_image and opacity_image as source if passed, get from AOV otherwise.
        Update catchers from AOVs if usage flags are set.
        """
        if color_image is None:
            color_image = self.rpr_context.get_image(pyrpr.AOV_COLOR)
        self.background_filter.update_input('color', color_image, tile_pos)

        if opacity_image is None:
            opacity_image = self.rpr_context.get_image(pyrpr.AOV_OPACITY)
        self.background_filter.update_input('opacity', opacity_image, tile_pos)

        # Catchers are taken directly from AOVs only when needed
        if self.rpr_context.use_shadow_catcher:
            shadow_catcher_image = self.rpr_context.get_image(pyrpr.AOV_SHADOW_CATCHER)
            self.background_filter.update_input('shadow_catcher', shadow_catcher_image, tile_pos)
        if self.rpr_context.use_reflection_catcher:
            reflection_catcher_image = self.rpr_context.get_image(pyrpr.AOV_REFLECTION_CATCHER)
            self.background_filter.update_input('reflection_catcher', reflection_catcher_image, tile_pos)
        if self.rpr_context.use_shadow_catcher or self.rpr_context.use_reflection_catcher:
            background_image = self.rpr_context.get_image(pyrpr.AOV_BACKGROUND)
            self.background_filter.update_input('background', background_image, tile_pos)

    def setup_upscale_filter(self, settings):
        if self.upscale_filter and self.upscale_filter.settings == settings:
            return False

        if settings['enable']:
            if not self.upscale_filter:
                self._enable_upscale_filter(settings)

            elif self.upscale_filter.settings['resolution'] == settings['resolution']:
                return False

            else:
                # recreating filter
                self._disable_upscale_filter()
                self._enable_upscale_filter(settings)

        elif self.upscale_filter:
            self._disable_upscale_filter()

        return True

    def _enable_upscale_filter(self, settings):
        width, height = settings['resolution']

        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)

        self.upscale_filter = image_filter.ImageFilterUpscale(
            self.rpr_context.context, {'color'}, {}, {}, width, height)

        self.upscale_filter.settings = settings

    def _disable_upscale_filter(self):
        self.upscale_filter = None
