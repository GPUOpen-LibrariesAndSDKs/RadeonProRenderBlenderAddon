import time
import datetime
import math
import numpy as np

import bpy
import pyrpr

from rprblender import utils
from .engine import Engine
from rprblender.export import world, camera, object, instance, particle
from rprblender.utils import render_stamp
from rprblender.utils.user_settings import get_user_settings

from rprblender.utils import logging
log = logging.Log(tag='RenderEngine')


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

        self.status_title = ""

        self.tile_size = None
        self.camera_data: camera.CameraData = None
        self.tile_order = None

        self.world_backplate = None

    def notify_status(self, progress, info):
        self.rpr_engine.update_progress(progress)
        self.rpr_engine.update_stats(self.status_title, info)

    def _render(self):
        athena_data = {}

        time_begin = time.perf_counter()
        athena_data['Start Time'] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        athena_data['End Status'] = "successful"

        self.current_sample = 0
        is_adaptive = self.rpr_context.is_aov_enabled(pyrpr.AOV_VARIANCE)
        if is_adaptive:
            all_pixels = active_pixels = self.rpr_context.width * self.rpr_context.height

        while True:
            if self.rpr_engine.test_break():
                athena_data['End Status'] = "cancelled"
                break

            self.current_render_time = time.perf_counter() - time_begin
            is_adaptive_active = is_adaptive and self.current_sample >= \
                                 self.rpr_context.get_parameter(pyrpr.CONTEXT_ADAPTIVE_SAMPLING_MIN_SPP)

            # if less that update_samples left, use the remainder
            update_samples = min(self.render_update_samples,
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
            self.rpr_context.render(restart=(self.current_sample == 0))

            self.current_sample += update_samples

            self.rpr_context.resolve()
            self.update_render_result((0, 0), (self.width, self.height),
                                      layer_name=self.render_layer_name)

            # stop at whichever comes first:
            # max samples or max time if enabled or active_pixels == 0
            if is_adaptive_active:
                active_pixels = self.rpr_context.get_info(pyrpr.CONTEXT_ACTIVE_PIXEL_COUNT, int)
                if active_pixels == 0:
                    break

            if self.current_sample == self.render_samples:
                break

            if self.render_time:
                if self.current_render_time >= self.render_time:
                    break

        if self.image_filter:
            self.notify_status(1.0, "Applying denoising final image")
            self.update_image_filter_inputs()
            self.image_filter.run()
            self.update_render_result((0, 0), (self.width, self.height),
                                      layer_name=self.render_layer_name,
                                      apply_image_filter=True)

        athena_data['Stop Time'] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        athena_data['Samples'] = self.current_sample

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
                self.world_backplate.export_tile(self.rpr_context,
                                                 tile[0][0], tile[0][1],
                                                 tile[0][0] + tile[1][0], tile[0][1] + tile[1][1])

            sample = 0
            if is_adaptive:
                all_pixels = active_pixels = self.rpr_context.width * self.rpr_context.height

            while True:
                if self.rpr_engine.test_break():
                    break

                update_samples = min(self.render_update_samples, self.render_samples - sample)
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
                self.rpr_context.render(restart=(sample == 0))

                sample += update_samples

                self.rpr_context.resolve()
                self.update_render_result(tile_pos, tile_size,
                                          layer_name=self.render_layer_name)

                if is_adaptive_active:
                    active_pixels = self.rpr_context.get_info(pyrpr.CONTEXT_ACTIVE_PIXEL_COUNT, int)
                    if active_pixels == 0:
                        break

                if sample == self.render_samples:
                    break

            if self.image_filter and sample == self.render_samples:
                self.update_image_filter_inputs(tile_pos)

        if self.image_filter and not self.rpr_engine.test_break():
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
                    self.image_filter.run()
                    image = self.image_filter.get_data()
                    images[pos: pos + length] = image.flatten()
                    break

                pos += length

            render_passes.foreach_set('rect', images)

            self.rpr_engine.end_result(result)

        athena_data['Stop Time'] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        athena_data['Samples'] = round(self.render_samples * progress)
        self.athena_send(athena_data)

    def render(self):
        if not self.is_synced:
            return

        self.rpr_context.sync_auto_adapt_subdivision(self.width, self.height)
        self.rpr_context.sync_portal_lights()

        log(f"Start render [{self.width}, {self.height}]")
        self.notify_status(0, "Start render")

        if self.tile_size:
            self._render_tiles()
        else:
            self._render()

        self.notify_status(1, "Finish render")
        log('Finish render')

    def apply_render_stamp(self, image, channels):
        """
        Apply render stamp to image if enabled.
        :param image: source image
        :type image: np.Array
        :param channels: image depth in bytes per pixel
        :type channels: int
        :return: image with applied render stamp text if text allowed, unchanged source image otherwise
        :rtype: np.Array
        """
        if bpy.context.scene.rpr.use_render_stamp \
                and render_stamp.render_stamp_supported \
                and not bpy.context.scene.rpr.is_tile_render_available:

            # TODO: Apply render stamp after tile rendering
            image = render_stamp.render_stamp(bpy.context.scene.rpr.render_stamp, image,
                                              self.rpr_context, channels,
                                              self.current_sample, self.current_render_time)
        return image

    def _init_rpr_context(self, scene):
        scene.rpr.init_rpr_context(self.rpr_context)
        self.rpr_context.scene.set_name(scene.name)

    def sync(self, depsgraph):
        log('Start syncing')

        # Preparations for syncing
        self.is_synced = False

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

        self.rpr_context.set_transparent_background(scene.render.film_transparent)

        # EXPORT OBJECTS
        objects_len = len(depsgraph.objects)
        for i, obj in enumerate(self.depsgraph_objects(depsgraph)):
            self.notify_status(0, "Syncing object (%d/%d): %s" % (i, objects_len, obj.name))

            # the correct collection visibility info is stored in original object
            indirect_only = obj.original.indirect_only_get(view_layer=view_layer)
            object.sync(self.rpr_context, obj,
                        indirect_only=indirect_only, material_override=material_override)

            if self.rpr_engine.test_break():
                log.warn("Syncing stopped by user termination")
                return

        # EXPORT INSTANCES
        instances_len = len(depsgraph.object_instances)
        last_instances_percent = 0
        self.notify_status(0, "Syncing instances 0%%")

        for i, inst in enumerate(self.depsgraph_instances(depsgraph)):
            instances_percent = (i * 100) // instances_len
            if instances_percent > last_instances_percent:
                self.notify_status(0, "Syncing instances %d%%" % instances_percent)
                last_instances_percent = instances_percent

            indirect_only = inst.parent.original.indirect_only_get(view_layer=view_layer)
            instance.sync(self.rpr_context, inst,
                          indirect_only=indirect_only, material_override=material_override)

            if self.rpr_engine.test_break():
                log.warn("Syncing stopped by user termination")
                return
        self.notify_status(0, "Syncing instances 100%%")

        # EXPORT CAMERA
        camera_key = object.key(scene.camera)   # current camera key
        rpr_camera = self.rpr_context.create_camera(camera_key)
        self.rpr_context.scene.set_camera(rpr_camera)

        # Camera object should be taken from depsgrapgh objects.
        # If it is not available then taking it from scene.camera
        camera_obj = depsgraph.objects.get(camera_key, None)
        if not camera_obj:
            camera_obj = scene.camera

        self.camera_data = camera.CameraData.init_from_camera(camera_obj.data, camera_obj.matrix_world,
                                                              screen_width / screen_height, border)

        if scene.rpr.is_tile_render_available:
            if scene.camera.data.type == 'PANO':
                log.warn("Tiles rendering is not supported for Panoramic camera")
            else:
                self.tile_size = (min(self.width, scene.rpr.tile_x), min(self.height, scene.rpr.tile_y))
                self.tile_order = scene.rpr.tile_order
                self.rpr_context.resize(*self.tile_size)

        else:
            self.camera_data.export(rpr_camera)

        # Environment is synced once per frame
        world.sync(self.rpr_context, scene.world)
        if scene.world.rpr.background_image_type == "BACKPLATE":
            # Different Backplate regions should be exported for each render tile
            self.world_backplate = world.Backplate(scene.world.rpr, (self.width, self.height))
            self.world_backplate.export_full(self.rpr_context)

        # SYNC MOTION BLUR
        self.rpr_context.do_motion_blur = scene.render.use_motion_blur and \
                                          not math.isclose(scene.camera.data.rpr.motion_blur_exposure, 0.0)

        if self.rpr_context.do_motion_blur:
            self.sync_motion_blur(depsgraph)
            rpr_camera.set_exposure(scene.camera.data.rpr.motion_blur_exposure)

        # EXPORT PARTICLES
        # Note: particles should be exported after motion blur,
        #       otherwise prev_location of particle will be (0, 0, 0)
        for obj in self.depsgraph_objects(depsgraph):
            if len(obj.particle_systems) == 0:
                continue

            for particle_system in obj.particle_systems:
                self.notify_status(0, f"Syncing particles: {particle_system.name} on {obj.name}")

                particle.sync(self.rpr_context, particle_system, obj)

                if self.rpr_engine.test_break():
                    log.warn("Syncing stopped by user termination")
                    return

        # EXPORT: AOVS, adaptive sampling, shadow catcher, denoiser
        enable_adaptive = scene.rpr.get_devices(True).count() == 1
        view_layer.rpr.export_aovs(view_layer, self.rpr_context, self.rpr_engine, enable_adaptive)

        if scene.rpr.limits.noise_threshold > 0.0 and enable_adaptive:
            # if adaptive is enable turn on aov and settings
            self.rpr_context.enable_aov(pyrpr.AOV_VARIANCE)
            scene.rpr.limits.set_adaptive_params(self.rpr_context)

        # Shadow catcher
        self.rpr_context.sync_catchers()

        # Image filter
        image_filter_settings = view_layer.rpr.denoiser.get_settings(scene)
        image_filter_settings['resolution'] = (self.width, self.height)
        self.setup_image_filter(image_filter_settings)

        if self.image_filter and self.rpr_context.is_aov_enabled(pyrpr.AOV_COLOR):
            self.rpr_engine.add_pass('Color', 4, 'RGBA', layer=view_layer.name)

        # SET rpr_context parameters
        self.rpr_context.set_parameter(pyrpr.CONTEXT_PREVIEW, False)
        scene.rpr.export_ray_depth(self.rpr_context)
        scene.rpr.export_pixel_filter(self.rpr_context)

        self.render_samples, self.render_time = (scene.rpr.limits.max_samples, scene.rpr.limits.seconds)
        self.render_update_samples = scene.rpr.limits.update_samples
        
        self.is_synced = True
        self.notify_status(0, "Finish syncing")
        log('Finish sync')

    def athena_send(self, data: dict):
        if not (utils.IS_WIN or utils.IS_MAC):
            return

        settings = get_user_settings()
        if not settings.collect_stat:
            return

        devices = settings.final_devices

        data['CPU Enabled'] = devices.cpu_state
        if hasattr(devices, 'gpu_states'):
            for i, gpu_state in enumerate(devices.gpu_states):
                data[f'GPU{i} Enabled'] = gpu_state

        data['Resolution'] = (self.width, self.height)
        quality = -1 if utils.IS_MAC else self.rpr_context.get_parameter(pyrpr.CONTEXT_RENDER_QUALITY, -1)
        data['Quality'] = "full" if utils.IS_MAC else {-1: "full",
                           pyrpr.RENDER_QUALITY_HIGH: "high",
                           pyrpr.RENDER_QUALITY_MEDIUM: "medium",
                           pyrpr.RENDER_QUALITY_LOW: "low"}[quality]
        data['Number Lights'] = sum(1 for o in self.rpr_context.scene.objects
                                 if isinstance(o, pyrpr.Light))
        data['AOVs Enabled'] = tuple(
            f'RPR_{v}' for v in dir(pyrpr) if v.startswith('AOV_')
            and getattr(pyrpr, v) in self.rpr_context.frame_buffers_aovs
        )

        data['Ray Depth'] = self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_RECURSION)
        data['Shadow Ray Depth'] = self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_DEPTH_SHADOW)
        data['Reflection Ray Depth'] = \
            self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_DEPTH_DIFFUSE) + \
            self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_DEPTH_GLOSSY)
        data['Refraction Ray Depth'] = \
            self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_DEPTH_REFRACTION) + \
            self.rpr_context.get_parameter(pyrpr.CONTEXT_MAX_DEPTH_GLOSSY_REFRACTION)

        data['Num Polygons'] = sum(
            (o.mesh.poly_count if isinstance(o, pyrpr.Instance) else o.poly_count)
            for o in self.rpr_context.objects.values() if isinstance(o, pyrpr.Shape)
        )
        data['Num Textures'] = len(self.rpr_context.images)
        data['Textures Size'] = sum(im.size_byte for im in self.rpr_context.images.values()) \
                                // (1024 * 1024)  # in MB

        data['RIF Type'] = self.image_filter.settings['filter_type'] if self.image_filter else None

        # sending data
        from rprblender.utils import athena
        athena.send_data(data)
