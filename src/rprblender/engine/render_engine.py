import threading
import time
import math

import bpy
import pyrpr

from rprblender import config
from rprblender import utils
from .engine import Engine
from rprblender.export import world, camera, object, instance, particle
from rprblender.utils import render_stamp

from rprblender.utils import logging
log = logging.Log(tag='RenderEngine')


class RenderEngine(Engine):
    """ Final render engine """

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

    def notify_status(self, progress, info):
        self.rpr_engine.update_progress(progress)
        self.rpr_engine.update_stats(self.status_title, info)

        if config.notifier_log_calls:
            log("%d - %s" % (int(progress*100), info))

    def _render(self):
        time_begin = time.perf_counter()

        self.current_sample = 0
        while True:
            if self.rpr_engine.test_break():
                break

            self.current_render_time = time.perf_counter() - time_begin

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
            self.notify_status(progress,
                               f"Render Time: {time_str} sec | "
                               f"Samples: {self.current_sample}/{self.render_samples}")

            log(f"  samples: {self.current_sample} +{update_samples} / {self.render_samples}, "
                f"progress: {progress * 100:.1f}%, time: {self.current_render_time:.2f}")

            self.rpr_context.set_parameter('iterations', update_samples)
            self.rpr_context.render(restart=(self.current_sample == 0))
            self.resolve_update_render_result((0, 0), (self.width, self.height),
                                              self.render_layer_name)

            self.current_sample += update_samples

            # stop at whichever comes first, max samples or max time if enabled
            if self.current_sample >= self.render_samples:
                break

            if self.render_time:
                if self.current_render_time >= self.render_time:
                    break

    def _render_tiles(self):
        tile_iterator = utils.tile_iterator(self.tile_order, self.width, self.height, *self.tile_size)
        tiles_number = tile_iterator.len

        rpr_camera = self.rpr_context.scene.camera

        time_begin = time.perf_counter()

        for tile_index, (tile_pos, tile_size) in enumerate(tile_iterator()):
            if self.rpr_engine.test_break():
                break

            log(f"Render tile {tile_index} / {tiles_number}: [{tile_pos}, {tile_size}]")

            self.camera_data.export(rpr_camera,
                                    tile=((tile_pos[0]/self.width, tile_pos[1]/self.height),
                                          (tile_size[0]/self.width, tile_size[1]/self.height)))
            self.rpr_context.resize(*tile_size)

            sample = 0
            while sample < self.render_samples:
                if self.rpr_engine.test_break():
                    break

                update_samples = min(self.render_update_samples, self.render_samples - sample)
                self.current_render_time = time.perf_counter() - time_begin
                progress = (tile_index + sample/self.render_samples) / tiles_number

                self.notify_status(progress,
                                   f"Render Time: {self.current_render_time:.1f} sec | "
                                   f"Tile: {tile_index}/{tiles_number} | "
                                   f"Samples: {sample}/{self.render_samples}")

                log(f"  samples: {sample} +{update_samples} / {self.render_samples}, "
                    f"progress: {progress * 100:.1f}%, time: {self.current_render_time:.2f}")
                self.rpr_context.set_parameter('iterations', update_samples)
                self.rpr_context.render(restart=(sample == 0))
                self.resolve_update_render_result(tile_pos, tile_size, self.render_layer_name)

                sample += update_samples

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
                and not bpy.context.scene.rpr.use_tile_render:

            # TODO: Apply render stamp after tile rendering
            image = render_stamp.render_stamp(bpy.context.scene.rpr.render_stamp, image,
                                              self.rpr_context.width, self.rpr_context.height, channels,
                                              self.current_sample, self.current_render_time)
        return image

    def sync(self, depsgraph):
        log('Start syncing')

        # Preparations for syncing
        self.is_synced = False

        scene = depsgraph.scene
        view_layer = depsgraph.view_layer

        self.render_layer_name = view_layer.name
        self.status_title = f"{scene.name}: {self.render_layer_name}"

        self.notify_status(0, "Start syncing")

        # Initializing rpr_context
        scene.rpr.init_rpr_context(self.rpr_context)
        self.rpr_context.scene.set_name(scene.name)

        border = ((0, 0), (1, 1)) if not scene.render.use_border else \
            ((scene.render.border_min_x, scene.render.border_min_y),
             (scene.render.border_max_x - scene.render.border_min_x, scene.render.border_max_y - scene.render.border_min_y))

        screen_width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
        screen_height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

        self.width = int(screen_width * border[1][0])
        self.height = int(screen_height * border[1][1])

        self.rpr_context.resize(self.width, self.height)

        world.sync(self.rpr_context, scene.world)

        # EXPORT OBJECTS
        objects_len = len(depsgraph.objects)
        for i, obj in enumerate(self.depsgraph_objects(depsgraph)):
            self.notify_status(0, "Syncing object (%d/%d): %s" % (i, objects_len, obj.name))

            object.sync(self.rpr_context, obj, depsgraph)

            if self.rpr_engine.test_break():
                log.warn("Syncing stopped by user termination")
                return

        # EXPORT INSTANCES
        instances_len = len(depsgraph.object_instances)
        for i, inst in enumerate(self.depsgraph_instances(depsgraph)):
            obj = inst.object
            self.notify_status(0, "Syncing instance (%d/%d): %s" % (i, instances_len - objects_len, obj.name))

            instance.sync(self.rpr_context, inst, depsgraph)

            if self.rpr_engine.test_break():
                log.warn("Syncing stopped by user termination")
                return

        # EXPORT CAMERA
        camera_key = object.key(scene.camera)
        rpr_camera = self.rpr_context.create_camera(camera_key)
        self.rpr_context.scene.set_camera(rpr_camera)

        camera_obj = scene.camera
        self.camera_data = camera.CameraData.init_from_camera(camera_obj.data, camera_obj.matrix_world,
                                                              screen_width / screen_height, border)

        if scene.rpr.use_tile_render:
            if scene.camera.data.type == 'PANO':
                log.warn("Tiles rendering is not supported for Panoramic camera")
            elif view_layer.rpr.denoiser.filter_type == 'ML':
                log.warn("Tiles rendering is not supported with enabled ML (Machine Learning) denoiser")
            else:
                self.tile_size = (min(self.width, scene.rpr.tile_x), min(self.height, scene.rpr.tile_y))
                self.tile_order = scene.rpr.tile_order
                self.rpr_context.resize(*self.tile_size)

        else:
            self.camera_data.export(rpr_camera)

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
        view_layer.rpr.export_aovs(view_layer, self.rpr_context, self.rpr_engine)

        if scene.rpr.limits.noise_threshold > 0.0:
            # if adaptive is enable turn on aov and settings
            self.rpr_context.enable_aov(pyrpr.AOV_VARIANCE)
            scene.rpr.limits.set_adaptive_params(self.rpr_context)

        self.rpr_context.sync_shadow_catcher()
        view_layer.rpr.denoiser.export_denoiser(self.rpr_context)

        # SET rpr_context parameters
        self.rpr_context.set_parameter('preview', False)
        scene.rpr.export_ray_depth(self.rpr_context)

        self.render_samples, self.render_time = (scene.rpr.limits.max_samples, scene.rpr.limits.seconds)
        self.render_update_samples = scene.rpr.limits.update_samples
        
        self.is_synced = True
        self.notify_status(0, "Finish syncing")
        log('Finish sync')
