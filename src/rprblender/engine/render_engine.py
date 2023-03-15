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
import socket
import time
import datetime
import math
import numpy as np
import bpy
import json

import pyrpr

from rprblender import utils
from .engine import Engine
from rprblender.export import world, camera, object, instance, particle
from rprblender.utils import render_stamp
from rprblender.utils.conversion import perfcounter_to_str, get_cryptomatte_hash
from rprblender.utils.user_settings import get_user_settings
from rprblender import bl_info
from rprblender.properties.view_layer import RPR_ViewLayerProperites


from rprblender.utils import logging
log = logging.Log(tag='RenderEngine')


MAX_RENDER_ITERATIONS = 32


class RenderEngine(Engine):
    """ Final render engine """

    TYPE = 'FINAL'

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)

        self.width = 0
        self.height = 0

        self.is_synced = False
        self.render_layer_name = None

        self.render_samples = 0
        self.current_sample = 0
        self.render_update_samples = 1
        self.render_time = 0
        self.current_render_time = 0
        self.sync_time = 0

        self.status_title = ""

        self.tile_size = None
        self.camera_data: camera.CameraData = None
        self.tile_order = None

        # settings to crontrol the contour render pass
        # needs_contour_pass means this engine should execute it
        self.needs_contour_pass = False
        self.cached_rendered_images = {}
        self.contour_pass_samples = 0

        self.world_backplate = None

        self.render_stamp_text = ""
        self.render_iteration = 0

        self.cryptomatte_allowed = False  # only Full mode supports cryptomatte AOVs

    def notify_status(self, progress, info):
        """ Display export/render status """
        self.rpr_engine.update_progress(progress)
        self.rpr_engine.update_stats(self.status_title, info)

    def _update_render_result(self, tile_pos, tile_size, layer_name="",
                              apply_image_filter=False):

        def zeros_image(channels):
            return np.zeros((self.rpr_context.height, self.rpr_context.width, channels),
                            dtype=np.float32)

        def set_render_result(render_passes: bpy.types.RenderPasses):
            images = []

            x1, y1 = tile_pos
            x2, y2 = x1 + tile_size[0], y1 + tile_size[1]

            for p in render_passes:
                if p.name == "Combined":
                    if apply_image_filter and self.image_filter:
                        image = self.image_filter.get_data()

                        if self.background_filter:
                            # calculate background effects on denoised image and cut out by tile size
                            self.update_background_filter_inputs(tile_pos=tile_pos,
                                                                 color_image=image)
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
                    image = zeros_image(p.channels)

                else:
                    aovs_info = RPR_ViewLayerProperites.cryptomatte_aovs_info \
                        if "Crypto" in p.name else RPR_ViewLayerProperites.aovs_info
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

                if self.needs_contour_pass:
                    # saving rendered image into cache_rendered_images
                    if p.name not in self.cached_rendered_images:
                        self.cached_rendered_images[p.name] = np.zeros(
                            (self.height, self.width, p.channels), dtype=np.float32)

                    self.cached_rendered_images[p.name][y1:y2, x1:x2] = image

                images.append(image.flatten())

            # efficient way to copy all AOV images
            render_passes.foreach_set('rect', np.concatenate(images))

        result = self.rpr_engine.begin_result(*tile_pos, *tile_size, layer=layer_name, view="")
        try:
            set_render_result(result.layers[0].passes)

        finally:
            self.rpr_engine.end_result(result)

    def stamp_data_add_field(self):
        result = self.rpr_engine.get_result()

        self.apply_render_stamp_to_image()

        if self.cryptomatte_allowed:
            view_layer = self.rpr_context.blender_data['depsgraph'].view_layer

            if view_layer.rpr.crytomatte_aov_material:
                self.add_cryptomatte_metadata("ViewLayer.CryptoMaterial",
                                              self.rpr_context.material_nodes_hashes, result)

            if view_layer.rpr.crytomatte_aov_object:
                self.add_cryptomatte_metadata("ViewLayer.CryptoObject",
                                              self.rpr_context.object_hashes, result)

    def add_cryptomatte_metadata(self, pass_name, manifest, result):
        pass_hash = get_cryptomatte_hash(pass_name)
        manifest = json.dumps(manifest)

        result.stamp_data_add_field(f"cryptomatte/{pass_hash}/name", pass_name)
        result.stamp_data_add_field(f"cryptomatte/{pass_hash}/hash", "MurmurHash3_32")
        result.stamp_data_add_field(f"cryptomatte/{pass_hash}/conversion", "uint32_to_float32")
        result.stamp_data_add_field(f"cryptomatte/{pass_hash}/manifest", manifest)

    def _update_render_result_contour(self, tile_pos, tile_size, layer_name=""):
        def set_render_result(render_passes: bpy.types.RenderPasses):
            images = []

            x1, y1 = tile_pos
            x2, y2 = x1 + tile_size[0], y1 + tile_size[1]

            for p in render_passes:
                if p.name == "Outline":
                    image = self.rpr_context.get_image(pyrpr.AOV_COLOR)
                else:
                    # getting required rendered image from cached_rendered_images
                    image = self.cached_rendered_images[p.name][y1:y2, x1:x2]

                images.append(image.flatten())

            # efficient way to copy all AOV images
            render_passes.foreach_set('rect', np.concatenate(images))

        result = self.rpr_engine.begin_result(*tile_pos, *tile_size, layer=layer_name, view="")
        try:
            set_render_result(result.layers[0].passes)

        finally:
            self.rpr_engine.end_result(result)

    def _render(self):
        athena_data = {}

        time_begin = time.perf_counter()
        athena_data['Start Time'] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        athena_data['End Status'] = "successful"

        self.current_sample = 0
        is_adaptive = self.rpr_context.is_aov_enabled(pyrpr.AOV_VARIANCE)
        if is_adaptive:
            all_pixels = active_pixels = self.rpr_context.width * self.rpr_context.height

        render_update_samples = self.render_update_samples

        while True:
            if self.rpr_engine.test_break():
                athena_data['End Status'] = "cancelled"
                break

            self.current_render_time = time.perf_counter() - time_begin
            is_adaptive_active = is_adaptive and self.current_sample >= \
                                 self.rpr_context.get_parameter(pyrpr.CONTEXT_ADAPTIVE_SAMPLING_MIN_SPP)

            # if less than update_samples left, use the remainder
            update_samples = min(render_update_samples,
                                 self.render_samples - self.current_sample)

            # we report time/iterations left as fractions if limit enabled
            time_str = f"{self.current_render_time:.1f}/{self.render_time}" if self.render_time \
                       else f"{self.current_render_time:.1f}"

            # percent done is one of percent iterations or percent time so pick whichever is greater
            progress = max(
                self.current_sample / self.render_samples,
                self.current_render_time / self.render_time if self.render_time else 0
            )
            info_str = f"Render Time: {time_str} sec | "\
                       f"Samples: {self.current_sample}/{self.render_samples}"
            log_str = f"  samples: {self.current_sample} +{update_samples} / {self.render_samples}"\
                      f", progress: {progress * 100:.1f}%, time: {self.current_render_time:.2f}"
            if is_adaptive_active:
                adaptive_progress = max((all_pixels - active_pixels) / all_pixels, 0.0)

                progress = max(progress, adaptive_progress)
                info_str += f" | Adaptive Sampling: {math.floor(adaptive_progress * 100)}%"
                log_str += f", active_pixels: {active_pixels}"

            self.notify_status(progress, info_str)

            log(log_str)

            self.rpr_context.set_parameter(pyrpr.CONTEXT_ITERATIONS, update_samples)
            self.rpr_context.set_parameter(pyrpr.CONTEXT_FRAMECOUNT, self.render_iteration)
            self.rpr_context.render(restart=(self.current_sample == 0))

            self.current_sample += update_samples

            self.rpr_context.resolve()
            if self.background_filter:
                self.update_background_filter_inputs()
                self.background_filter.run()
            self._update_render_result((0, 0), (self.width, self.height),
                                       layer_name=self.render_layer_name)

            # stop at whichever comes first:
            # max samples or max time if enabled or active_pixels == 0
            if is_adaptive_active:
                active_pixels = self.rpr_context.get_info(pyrpr.CONTEXT_ACTIVE_PIXEL_COUNT, int)
                if active_pixels == 0:
                    break

            if self.current_sample == self.render_samples:
                break

            if self.render_time and self.current_render_time >= self.render_time:
                break

            self.render_iteration += 1
            if self.render_iteration > 1 and render_update_samples < MAX_RENDER_ITERATIONS:
                # progressively increase update samples up to 32
                render_update_samples *= 2

        if self.image_filter:
            self.notify_status(1.0, "Denoising final image")
            self.update_image_filter_inputs()
            self.image_filter.run()
            color_source = self.image_filter.get_data()

            # restore alpha channel
            alpha_source = self.rpr_context.get_image()
            color_source[:, :, 3] = alpha_source[:, :, 3]
            if self.background_filter:
                self.update_background_filter_inputs(color_image=color_source)
                self.background_filter.run()
            self._update_render_result((0, 0), (self.width, self.height),
                                       layer_name=self.render_layer_name,
                                       apply_image_filter=True)

        # apply stamp data and metadata to render result
        self.stamp_data_add_field()

        athena_data['Stop Time'] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        athena_data['Samples'] = self.current_sample

        log.info(f"Scene synchronization time:", perfcounter_to_str(self.sync_time))
        log.info(f"Render time:", perfcounter_to_str(self.current_render_time))
        self.athena_send(athena_data)

    def _render_tiles(self):
        athena_data = {}

        tile_iterator = utils.tile_iterator(self.tile_order, self.width, self.height, *self.tile_size)
        tiles_number = tile_iterator.len
        is_adaptive = self.rpr_context.is_aov_enabled(pyrpr.AOV_VARIANCE)

        rpr_camera = self.rpr_context.scene.camera

        time_begin = time.perf_counter()
        athena_data['Start Time'] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        athena_data['End Status'] = "successful"
        progress = 0.0

        render_update_samples = self.render_update_samples

        for tile_index, (tile_pos, tile_size) in enumerate(tile_iterator()):
            if self.rpr_engine.test_break():
                athena_data['End Status'] = "cancelled"
                break

            log(f"Render tile {tile_index} / {tiles_number}: [{tile_pos}, {tile_size}]")

            tile = ((tile_pos[0] / self.width, tile_pos[1] / self.height),
                    (tile_size[0] / self.width, tile_size[1] / self.height))
            # set camera for tile
            self.camera_data.export(rpr_camera, tile=tile)
            self.rpr_context.resize(*tile_size)

            # export backplate section for tile if backplate present
            if self.world_backplate:
                self.world_backplate.export(self.rpr_context, (self.width, self.height), tile)

            sample = 0
            if is_adaptive:
                all_pixels = active_pixels = self.rpr_context.width * self.rpr_context.height

            render_iteration = 0
            while True:
                if self.rpr_engine.test_break():
                    break

                update_samples = min(render_update_samples, self.render_samples - sample)
                self.current_render_time = time.perf_counter() - time_begin
                progress = (tile_index + sample/self.render_samples) / tiles_number
                info_str = f"Render Time: {self.current_render_time:.1f} sec"\
                           f" | Tile: {tile_index}/{tiles_number}"\
                           f" | Samples: {sample}/{self.render_samples}"
                log_str = f"  samples: {sample} +{update_samples} / {self.render_samples}"\
                    f", progress: {progress * 100:.1f}%, time: {self.current_render_time:.2f}"

                is_adaptive_active = is_adaptive and sample >= \
                                     self.rpr_context.get_parameter(pyrpr.CONTEXT_ADAPTIVE_SAMPLING_MIN_SPP)
                if is_adaptive_active:
                    adaptive_progress = max((all_pixels - active_pixels) / all_pixels, 0.0)
                    progress = max(progress, (tile_index + adaptive_progress) / tiles_number)
                    info_str += f" | Adaptive Sampling: {adaptive_progress * 100:.0f}%"
                    log_str += f", active_pixels: {active_pixels}"

                self.notify_status(progress, info_str)
                log(log_str)

                self.rpr_context.set_parameter(pyrpr.CONTEXT_ITERATIONS, update_samples)
                self.rpr_context.set_parameter(pyrpr.CONTEXT_FRAMECOUNT, render_iteration)
                self.rpr_context.render(restart=(sample == 0))

                sample += update_samples

                self.rpr_context.resolve()
                self._update_render_result(tile_pos, tile_size,
                                           layer_name=self.render_layer_name)

                # store maximum actual number of used samples for render stamp info
                self.current_sample = max(self.current_sample, sample)

                if is_adaptive_active:
                    active_pixels = self.rpr_context.get_info(pyrpr.CONTEXT_ACTIVE_PIXEL_COUNT, int)
                    if active_pixels == 0:
                        break

                if sample == self.render_samples:
                    break

                render_iteration += 1
                if render_iteration > 1 and render_update_samples < MAX_RENDER_ITERATIONS:
                    # progressively increase update samples up to 32
                    render_update_samples *= 2

            if not self.rpr_engine.test_break():
                if self.image_filter:
                    self.update_image_filter_inputs(tile_pos=tile_pos)
                if self.background_filter:
                    self.update_background_filter_inputs(tile_pos=tile_pos)

        if (self.image_filter or self.background_filter) and not self.rpr_engine.test_break():
            self.notify_status(1.0, "Applying denoising final image")

            # getting already rendered images for every render pass
            result = self.rpr_engine.get_result()
            render_passes = result.layers[self.render_layer_name].passes
            length = sum((len(p.rect) * p.channels for p in render_passes))
            images = np.empty(length, dtype=np.float32)
            render_passes.foreach_get('rect', images)

            # updating points
            result = self.rpr_engine.begin_result(
                0, 0, self.width, self.height,
                layer=self.render_layer_name)

            render_passes = result.layers[0].passes
            pos = 0
            for p in render_passes:
                length = len(p.rect) * p.channels

                # we will update only Combined pass
                if p.name == "Combined":
                    image = None
                    if self.image_filter:
                        self.image_filter.run()
                        image = self.image_filter.get_data()

                    if self.background_filter:
                        if image is not None:
                            self.background_filter.update_input('color', image)
                        self.background_filter.run()
                        image = self.background_filter.get_data()

                    if image is not None:
                        images[pos: pos + length] = image.flatten()
                    break

                pos += length

            render_passes.foreach_set('rect', images)

            self.rpr_engine.end_result(result)

        if not self.rpr_engine.test_break():
            self.apply_render_stamp_to_image()

        athena_data['Stop Time'] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        athena_data['Samples'] = round(self.render_samples * progress)

        log.info(f"Scene synchronization time:", perfcounter_to_str(self.sync_time))
        log.info(f"Render time:", perfcounter_to_str(self.current_render_time))

        self.athena_send(athena_data)

    def _render_contour(self):
        log(f"Doing Outline Pass")

        # set contour settings
        self.rpr_context.set_parameter(pyrpr.CONTEXT_GPUINTEGRATOR, "gpucontour")

        # enable contour aovs
        self.rpr_context.disable_aovs()
        self.rpr_context.resize(self.width, self.height)

        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.enable_aov(pyrpr.AOV_OBJECT_ID)
        self.rpr_context.enable_aov(pyrpr.AOV_MATERIAL_ID)
        self.rpr_context.enable_aov(pyrpr.AOV_SHADING_NORMAL)
        self.rpr_context.enable_aov(pyrpr.AOV_UV)

        # setting camera
        self.camera_data.export(self.rpr_context.scene.camera)

        athena_data = {}

        time_begin = time.perf_counter()
        athena_data['Start Time'] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        athena_data['End Status'] = "successful"

        self.current_sample = 0

        while True:
            if self.rpr_engine.test_break():
                athena_data['End Status'] = "cancelled"
                break

            self.current_render_time = time.perf_counter() - time_begin

            # if less than update_samples left, use the remainder
            update_samples = 1

            # we report time/iterations left as fractions if limit enabled
            time_str = f"{self.current_render_time:.1f}/{self.render_time}" if self.render_time \
                       else f"{self.current_render_time:.1f}"

            # percent done is one of percent iterations or percent time so pick whichever is greater
            progress = max(
                self.current_sample / self.contour_pass_samples,
                self.current_render_time / self.render_time if self.render_time else 0
            )
            info_str = f"Outline Pass | Render Time: {time_str} sec | "\
                       f"Samples: {self.current_sample}/{self.contour_pass_samples}"
            log_str = f"  samples: {self.current_sample} +{update_samples} / {self.contour_pass_samples}"\
                      f", progress: {progress * 100:.1f}%, time: {self.current_render_time:.2f}"

            self.notify_status(progress, info_str)

            log(log_str)

            self.rpr_context.set_parameter(pyrpr.CONTEXT_ITERATIONS, update_samples)
            self.rpr_context.set_parameter(pyrpr.CONTEXT_FRAMECOUNT, self.render_iteration)
            self.rpr_context.render(restart=(self.current_sample == 0))

            self.current_sample += update_samples

            self.rpr_context.resolve()
            self._update_render_result_contour((0, 0), (self.width, self.height),
                                               layer_name=self.render_layer_name)

            if self.current_sample == self.contour_pass_samples:
                break

            if self.render_time and self.current_render_time >= self.render_time:
                break

            self.render_iteration += 1

        athena_data['Stop Time'] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        athena_data['Samples'] = self.current_sample

        log.info(f"Scene synchronization time:", perfcounter_to_str(self.sync_time))
        log.info(f"Render time:", perfcounter_to_str(self.current_render_time))
        self.athena_send(athena_data)

    def render(self):
        if not self.is_synced:
            return

        self.rpr_context.sync_auto_adapt_subdivision()
        self.rpr_context.sync_portal_lights()

        log(f"Start render [{self.width}, {self.height}]")
        self.notify_status(0, "Start render")

        if self.tile_size:
            self._render_tiles()
        else:
            self._render()

        # contour or "Outline" rendering is done as a separate render pass.  
        if self.needs_contour_pass:
            self._render_contour()

        self.notify_status(1, "Finish render")
        log('Finish render')

    def _init_rpr_context(self, scene):
        scene.rpr.init_rpr_context(self.rpr_context)

        self.rpr_context.scene.set_name(scene.name)

    def sync(self, depsgraph):
        log('Start syncing')

        # Preparations for syncing
        self.is_synced = False

        self.sync_time = time.perf_counter()

        scene = depsgraph.scene
        view_layer = depsgraph.view_layer
        material_override = view_layer.material_override

        self.render_layer_name = view_layer.name
        self.status_title = f"{scene.name}: {self.render_layer_name}"

        self.notify_status(0, "Start syncing")

        self._init_rpr_context(scene)

        border = ((0, 0), (1, 1)) if not scene.render.use_border else \
            ((scene.render.border_min_x, scene.render.border_min_y),
             (scene.render.border_max_x - scene.render.border_min_x, scene.render.border_max_y - scene.render.border_min_y))

        screen_width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
        screen_height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

        self.width = int(screen_width * border[1][0])
        self.height = int(screen_height * border[1][1])

        self.rpr_context.resize(self.width, self.height)

        self.needs_contour_pass = view_layer.rpr.use_contour_render and scene.rpr.final_render_mode == 'FULL2'
        if self.needs_contour_pass:
            view_layer.rpr.contour.export_contour_settings(self.rpr_context)

        self.rpr_context.blender_data['depsgraph'] = depsgraph

        # CACHE BLUR DATA
        self.rpr_context.do_motion_blur = scene.render.use_motion_blur and \
            not math.isclose(scene.camera.data.rpr.motion_blur_exposure, 0.0)

        # with enabled motion blur, cache_blur_data() can change frame,
        # therefore we store current frame and set it back after export process
        cur_frame = (scene.frame_current, 0.0)

        try:
            if self.rpr_context.do_motion_blur:
                self.cache_blur_data(depsgraph)
                self.set_motion_blur_mode(scene)

            # EXPORT OBJECTS
            objects_len = len(depsgraph.objects)
            for i, obj in enumerate(self.depsgraph_objects(depsgraph)):
                self.notify_status(0, "Syncing object (%d/%d): %s" % (i, objects_len, obj.name))

                # the correct collection visibility info is stored in original object
                indirect_only = obj.original.indirect_only_get(view_layer=view_layer)
                object.sync(self.rpr_context, obj,
                            indirect_only=indirect_only, material_override=material_override,
                            frame_current=scene.frame_current)

                if self.rpr_engine.test_break():
                    log.warn("Syncing stopped by user termination")
                    return

            # EXPORT INSTANCES
            instances_len = len(depsgraph.object_instances)
            last_instances_percent = 0
            self.notify_status(0, "Syncing instances 0%")

            for i, inst in enumerate(self.depsgraph_instances(depsgraph)):
                instances_percent = (i * 100) // instances_len
                if instances_percent > last_instances_percent:
                    self.notify_status(0, f"Syncing instances {instances_percent}%")
                    last_instances_percent = instances_percent

                indirect_only = inst.parent.original.indirect_only_get(view_layer=view_layer)
                instance.sync(self.rpr_context, inst,
                              indirect_only=indirect_only, material_override=material_override,
                              frame_current=scene.frame_current)

                if self.rpr_engine.test_break():
                    log.warn("Syncing stopped by user termination")
                    return

            self.notify_status(0, "Syncing instances 100%")

            # EXPORT CAMERA
            camera_key = object.key(scene.camera)   # current camera key
            rpr_camera = self.rpr_context.create_camera(camera_key)
            self.rpr_context.scene.set_camera(rpr_camera)

            # Camera object should be taken from depsgrapgh objects.
            # Use bpy.scene.camera if none found
            camera_obj = depsgraph.objects.get(camera_key, None)
            if not camera_obj:
                camera_obj = scene.camera

            self.camera_data = camera.CameraData.init_from_camera(
                camera_obj.data, camera_obj.matrix_world, screen_width / screen_height, border)

            if self.rpr_context.do_motion_blur:
                rpr_camera.set_exposure(scene.camera.data.rpr.motion_blur_exposure)
                object.export_motion_blur(self.rpr_context, camera_key,
                                          object.get_transform(camera_obj))

            if scene.rpr.is_tile_render_available:
                if scene.camera.data.type == 'PANO':
                    log.warn("Tiles rendering is not supported for Panoramic camera")
                else:
                    # create adaptive subdivision camera to use total render area for calculations
                    subdivision_camera_key = camera_key + ".RPR_ADAPTIVE_SUBDIVISION_CAMERA"
                    subdivision_camera = self.rpr_context.create_camera(subdivision_camera_key)
                    self.camera_data.export(subdivision_camera)
                    self.rpr_context.scene.set_subdivision_camera(subdivision_camera)

                    # apply tiles settings
                    self.tile_size = (min(self.width, scene.rpr.tile_x), min(self.height, scene.rpr.tile_y))
                    self.tile_order = scene.rpr.tile_order
                    self.rpr_context.resize(*self.tile_size)

            else:
                self.camera_data.export(rpr_camera)

            # Environment is synced once per frame
            if scene.world:
                if scene.world.is_evaluated:  # for some reason World data can came in unevaluated
                    world_data = scene.world
                else:
                    world_data = scene.world.evaluated_get(depsgraph)
                world_settings = world.sync(self.rpr_context, world_data)
                self.world_backplate = world_settings.backplate

            # EXPORT PARTICLES
            # Note: particles should be exported after motion blur,
            #       otherwise prev_location of particle will be (0, 0, 0)
            self.notify_status(0, "Syncing particles")
            for obj in self.depsgraph_objects(depsgraph):
                particle.sync(self.rpr_context, obj)
                if self.rpr_engine.test_break():
                    log.warn("Syncing stopped by user termination")
                    return

            # objects linked to scene as a collection are instanced, so walk thru them for particles
            for entry in self.depsgraph_instances(depsgraph):
                particle.sync(self.rpr_context, entry.instance_object)
                if self.rpr_engine.test_break():
                    log.warn("Syncing stopped by user termination")
                    return

        finally:
            if self.rpr_context.do_motion_blur:
                self._set_scene_frame(scene, *cur_frame)

        # EXPORT: AOVS, adaptive sampling, shadow catcher, denoiser
        enable_adaptive = scene.rpr.limits.noise_threshold > 0.0
        view_layer.rpr.export_aovs(view_layer, self.rpr_context, self.rpr_engine, enable_adaptive, self.cryptomatte_allowed)

        if scene.rpr.final_render_mode == 'FULL2':
            scene.rpr.limits.set_random_seed(self.rpr_context)

        if enable_adaptive:
            # if adaptive is enable turn on aov and settings
            self.rpr_context.enable_aov(pyrpr.AOV_VARIANCE)
            scene.rpr.limits.set_adaptive_params(self.rpr_context)

        # Image filter
        image_filter_settings = view_layer.rpr.denoiser.get_settings(scene)
        image_filter_settings['resolution'] = (self.width, self.height)
        self.setup_image_filter(image_filter_settings)

        # Shadow catcher
        if scene.rpr.final_render_mode != 'FULL':
            self.rpr_context.sync_catchers(False)
            bg_filter_enabled = scene.render.film_transparent or self.rpr_context.use_reflection_catcher  # single Shadow Catcher AOV is handled by core
            background_filter_settings = {
                'enable': bg_filter_enabled,
                'use_background': scene.render.film_transparent,
                'use_shadow': self.rpr_context.use_shadow_catcher,
                'use_reflection': self.rpr_context.use_reflection_catcher,
                'resolution': (self.width, self.height),
            }
            self.setup_background_filter(background_filter_settings)
        else:
            self.rpr_context.sync_catchers(scene.render.film_transparent)

        # SET rpr_context parameters
        self.rpr_context.set_parameter(pyrpr.CONTEXT_PREVIEW, False)
        scene.rpr.export_ray_depth(self.rpr_context)
        scene.rpr.export_pixel_filter(self.rpr_context)
        self.rpr_context.texture_compression = scene.rpr.texture_compression

        self.render_samples, self.render_time = (scene.rpr.limits.max_samples, scene.rpr.limits.seconds)
        self.contour_pass_samples = scene.rpr.limits.contour_render_samples

        if self.cryptomatte_allowed:
            self.rpr_context.sync_cryptomatte_hash()

        if scene.rpr.final_render_mode == 'FULL2':
            self.render_update_samples = scene.rpr.limits.update_samples_rpr2
        else:
            self.render_update_samples = scene.rpr.limits.update_samples

        if scene.rpr.use_render_stamp:
            self.render_stamp_text = self.prepare_scene_stamp_text(scene)

        self.sync_time = time.perf_counter() - self.sync_time

        self.is_synced = True
        self.notify_status(0, "Finish syncing")
        log('Finish sync')

    def athena_send(self, data: dict):
        if not (utils.IS_WIN or utils.IS_MAC):
            return

        settings = get_user_settings()
        if not settings.collect_stat:
            return

        from rprblender.utils import athena
        if athena.is_disabled():
            return

        devices = settings.final_devices

        data['CPU Enabled'] = devices.cpu_state
        for i, gpu_state in enumerate(devices.available_gpu_states):
            data[f'GPU{i} Enabled'] = gpu_state

        data['Resolution'] = (self.width, self.height)
        data['Number Lights'] = sum(1 for o in self.rpr_context.scene.objects
                                    if isinstance(o, pyrpr.Light))
        data['AOVs Enabled'] = tuple(
            f'RPR_{v}' for v in dir(pyrpr) if v.startswith('AOV_')
            and getattr(pyrpr, v) in self.rpr_context.frame_buffers_aovs
        )

        data['Ray Depth'] = self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_RECURSION)
        data['Shadow Ray Depth'] = self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_DEPTH_SHADOW)
        data['Reflection Ray Depth'] = \
            self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_DEPTH_DIFFUSE, 0) + \
            self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_DEPTH_GLOSSY, 0)
        data['Refraction Ray Depth'] = \
            self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_DEPTH_REFRACTION, 0) + \
            self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_DEPTH_GLOSSY_REFRACTION, 0)

        data['Num Polygons'] = sum(
            (o.mesh.poly_count if isinstance(o, pyrpr.Instance) else o.poly_count)
            for o in self.rpr_context.objects.values() if isinstance(o, pyrpr.Shape)
        )
        data['Num Textures'] = len(self.rpr_context.images)

        # temporary ignore getting texture sizes with hybrid,
        # until it'll be fixed on hybrid core side
        from . context_hybrid import RPRContext as RPRContextHybrid
        from . context_hybridpro import RPRContext as RPRContextHybridPro
        if not isinstance(self.rpr_context, (RPRContextHybrid, RPRContextHybridPro)):
            data['Textures Size'] = sum(im.size_byte for im in self.rpr_context.images.values()) \
                                    // (1024 * 1024)  # in MB

        data['RIF Type'] = self.image_filter.settings['filter_type'] if self.image_filter else None

        self._update_athena_data(data)

        # sending data
        athena.send_data(data)

    def _update_athena_data(self, data):
        data['Quality'] = "full"

    def prepare_scene_stamp_text(self, scene):
        """ Fill stamp with static scene and render devices info that user can ask for """
        text = str(scene.rpr.render_stamp)
        text = text.replace("%i", socket.gethostname())

        lights_count = len([
            e for e in self.rpr_context.objects.values()
            if isinstance(e, pyrpr.Light)])
        text = text.replace("%sl", str(lights_count))

        objects_count = len([
            e for e in self.rpr_context.objects.values()
            if isinstance(e, (pyrpr.Curve, pyrpr.Shape, pyrpr.HeteroVolume,))
               and hasattr(e, 'is_visible') and e.is_visible
        ])
        text = text.replace("%so", str(objects_count))

        cpu_name = pyrpr.Context.cpu_device['name']
        text = text.replace("%c", cpu_name)

        selected_gpu_names = ''
        settings = get_user_settings()
        devices = settings.final_devices
        for i, gpu_state in enumerate(devices.available_gpu_states):
            if gpu_state:
                name = pyrpr.Context.gpu_devices[i]['name']
                if selected_gpu_names:
                    selected_gpu_names += f" + {name}"
                else:
                    selected_gpu_names += name

        hardware = ''
        render_mode = ''
        if selected_gpu_names:
            hardware = selected_gpu_names
            render_mode = "GPU"
            if devices.cpu_state:
                hardware += " / "
                render_mode += " + "
        if devices.cpu_state:
            hardware += cpu_name
            render_mode = render_mode + "CPU"
        text = text.replace("%g", selected_gpu_names)
        text = text.replace("%r", render_mode)
        text = text.replace("%h", hardware)

        ver = bl_info['version']
        text = text.replace("%b", f"v{ver[0]}.{ver[1]}.{ver[2]}")

        return text

    def apply_render_stamp_to_image(self):
        """
        Apply render stamp if enabled to "Combined" view layer pass.
        """
        if self.render_stamp_text:
            # fill render iteration info
            text = self.render_stamp_text
            text = text.replace("%pt", time.strftime("%H:%M:%S", time.gmtime(self.current_render_time)))
            text = text.replace("%d", time.strftime("%a, %d %b %Y", time.localtime()))
            text = text.replace("%pp", str(self.current_sample))

            try:
                ordered_text_bytes, width, height = \
                    render_stamp.render(text, self.width, self.height)
            except NotImplementedError:
                return

            # Write stamp pixels to the RenderResult
            result = self.rpr_engine.begin_result(self.width - width, 0,
                                                  width, height, layer=self.render_layer_name)

            for p in result.layers[0].passes:
                p.rect = [e[:p.channels] for e in ordered_text_bytes]

            self.rpr_engine.end_result(result)
