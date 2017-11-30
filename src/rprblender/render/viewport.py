import time
import gc

import bpy

import rprblender.render.scene
from rprblender import config
from rprblender import logging
from rprblender import sync, export
import rprblender.render.render_layers
from rprblender.helpers import CallLogger

import pyrpr

call_logger = CallLogger(tag='render.viewport')


class ViewportRenderer:

    thread = None
    scene_renderer_threaded = None

    def __init__(self):
        logging.debug(self, "init")

        self.time_start = time.clock()

        self.render_camera = None

        self.render_resolution = None
        self.render_region = None

        self.render_aov = None

    @call_logger.logged
    def __del__(self):
        self.scene_exporter = None
        self.scene_renderer_threaded = None

        self.scene_synced.destroy()
        if config.debug:
            referrers = gc.get_referrers(self.scene_synced)
            assert 1 == len(referrers), referrers
        self.scene_synced = None

        self.scene_renderer = None

    def get_image(self, pass_name='default'):
        with self.scene_renderer_threaded.image_lock:
            return self.scene_renderer.get_image(pass_name)

    @call_logger.logged
    def start(self, scene, threaded=True, is_production=False):

        if self.scene_renderer_threaded and self.threaded:
            self.scene_renderer_threaded.stop()
            self.scene_renderer_threaded = None

        self.threaded = threaded

        self.scene_renderer = rprblender.render.scene.SceneRenderer(
            rprblender.render.get_render_device(is_production=is_production),
            scene.rpr.render, is_production=is_production)
        if self.threaded:
            self.scene_renderer_threaded = rprblender.render.scene.SceneRendererThreaded(self.scene_renderer)
        # pyrpr.ContextSetParameter1f(self.scene_renderer.get_core_context(), b'displaygamma', 2.2)

        # searching for shadow catcher in scene
        for obj in scene.objects:
            is_shadowcatcher = obj.rpr_object.shadowcatcher
            if is_shadowcatcher:
                self.scene_renderer.has_shadowcatcher = True
                break

        self.scene_renderer.denoiser = bpy.context.scene.rpr.render.denoiser.enable
        if self.scene_renderer.denoiser:
            filter_type_value = bpy.context.scene.rpr.render.denoiser.filter_type
            self.scene_renderer.filter_type = bpy.context.scene.rpr.render.denoiser.filter_type_values[filter_type_value]

        self.scene_renderer_threaded.set_aov(self.render_aov)
        self.scene_renderer_threaded.set_render_resolution(self.render_resolution)
        self.scene_renderer_threaded.set_render_region(self.render_region)
        if self.threaded:
            self.scene_renderer_threaded.start()

        self.set_scene(scene)

    def set_scene(self, scene):
        with self.scene_renderer_threaded.update_lock:
            self.scene_renderer_threaded.need_scene_redraw = True

            self.scene_synced = sync.SceneSynced(self.scene_renderer.render_device, scene.rpr.render)
            self.scene_synced.set_render_camera(self.render_camera)

            self.scene_synced.make_core_scene()

            if self.threaded:
                self.scene_renderer_threaded.set_scene_synced(self.scene_synced)

            self.export_scene(scene)

    def stop(self):
        if self.threaded:
            self.scene_renderer_threaded.stop()

    def update_iter(self, scene):
        logging.debug('ViewportRenderer.update ...')
        yield 'update'

        with self.scene_renderer_threaded.update_lock:
            self.scene_renderer_threaded.need_scene_redraw = True

            yield from self.scene_update(scene)

        logging.debug('ViewportRenderer.update done')

    def export_scene(self, scene):
        # texture compression context param needs to be set before exporting textures
        pyrpr.ContextSetParameter1u(self.scene_renderer.get_core_context(), b"texturecompression",
                                      self.scene_synced.settings.texturecompression)
        self.scene_exporter = export.SceneExport(scene, self.scene_synced, preview=True)

        self.scene_exporter.sync_environment_settings(scene.world.rpr_data.environment if scene.world else None)

        self.visible_objects = self.scene_exporter.export()

    def clear_scene(self):
        self.scene_synced.reset_scene()

    def scene_update(self, scene):
        logging.debug('ViewportRenderer.scene_update')
        yield 'scene'

        self.scene_exporter.sync_environment_settings(scene.world.rpr_data.environment if scene.world else None)
        self.scene_exporter.sync()
        need_scene_reset = self.scene_exporter.need_scene_reset

        if need_scene_reset:
            yield 'clear scene'
            self.clear_scene()
            yield 'reset scene'
            self.export_scene(scene)

    def scene_reset(self, scene):
        """used to force-reexport scene in tests"""
        with self.scene_renderer_threaded.update_lock:
            self.scene_renderer_threaded.need_scene_redraw = True

            self.scene_synced.settings = scene.rpr.render
            self.clear_scene()
            self.scene_synced.set_render_camera(self.render_camera)
            self.export_scene(scene)

    def set_render_camera(self, render_camera):
        self.render_camera = render_camera

    @call_logger.logged
    def update_render_camera(self, render_camera):
        self.render_camera = render_camera
        self.scene_renderer_threaded.update_render_camera(render_camera)

    def set_render_aov(self, aov):
        self.render_aov = rprblender.render.render_layers.extract_settings(aov)

    def update_render_aov(self, aov):
        self.render_aov = rprblender.render.render_layers.extract_settings(aov)
        self.scene_renderer_threaded.update_aov(self.render_aov)

    @call_logger.logged
    def set_render_resolution(self, render_resolution):
        self.render_resolution = render_resolution

    @call_logger.logged
    def set_render_region(self, render_region):
        self.render_region = render_region

    @call_logger.logged
    def update_render_resolution(self, render_resolution):
        self.render_resolution = render_resolution
        self.scene_renderer_threaded.update_render_resolution(render_resolution)

    @call_logger.logged
    def update_render_region(self, render_region):
        self.render_region = render_region
        self.scene_renderer_threaded.update_render_region(render_region)

