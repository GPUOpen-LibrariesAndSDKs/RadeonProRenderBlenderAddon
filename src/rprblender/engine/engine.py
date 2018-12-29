''' Engine is the functionality of the rendering process, 
maintains context, processes, etc.

Other modules in this directory could be viewport, etc.
'''

''' main Render object '''

import weakref
import threading
import time
import numpy as np
from abc import ABCMeta, abstractmethod

import bpy

from rprblender import utils
from rprblender.utils import logging
from . import context
from rprblender.properties.view_layer import RPR_ViewLayerProperites
from rprblender import config
import pyrpr


log = logging.Log(tag='Engine')


class Engine(metaclass=ABCMeta):
    def __init__(self, rpr_engine):
        self.rpr_engine = weakref.proxy(rpr_engine)
        self.rpr_context: context.RPRContext = None

    @abstractmethod
    def render(self, depsgraph):
        pass

    @abstractmethod
    def sync(self, depsgraph):
        ''' sync all data '''
        pass

    @staticmethod
    def set_render_result(rpr_context, render_passes: bpy.types.RenderPasses):
        def zeros_image(channels):
            return np.zeros((rpr_context.height, rpr_context.width, channels), dtype=np.float32)

        images = []

        for p in render_passes:
            try:
                aov = next(aov for aov in RPR_ViewLayerProperites.aovs_info if aov['name'] == p.name)  # finding corresponded aov
                image = rpr_context.get_image(aov['rpr'])

            except StopIteration:
                log.warn("AOV '{}' is not found in aovs_info".format(p.name))
                image = zeros_image(p.channels)

            except KeyError:
                # This could happen when Depth or Combined was not selected, but they still are in view_layer.use_pass_*
                log.warn("AOV '{}' is not enabled in rpr_context".format(aov['name']))
                image = zeros_image(p.channels)

            if p.channels != image.shape[2]:
                image = image[:, :, 0:p.channels]

            images.append(image.flatten())

        # efficient way to copy all AOV images
        render_passes.foreach_set('rect', np.concatenate(images))


class RenderEngine(Engine):
    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)
        self.rpr_context = context.RPRContext()

        self.render_lock = threading.Lock()
        self.is_synced = False
        self.render_event = threading.Event()
        self.finish_render = False

        self.status_title = ""

    def notify_status(self, progress, info):
        self.rpr_engine.update_progress(progress)
        self.rpr_engine.update_stats(self.status_title, info)

        if config.notifier_log_calls:
            log("%d - %s" % (int(progress*100), info))

    def _do_update_result(self, result):
        while not self.finish_render:
            self.render_event.wait()
            self.render_event.clear()

            with self.render_lock:
                self.rpr_context.resolve()

            log("Updating render result")
            self.rpr_context.resolve_extras()
            Engine.set_render_result(self.rpr_context, result.layers[0].passes)
            self.rpr_engine.update_result(result)

            time.sleep(config.render_update_result_interval)

    def _do_render(self, iterations, samples):
        self.finish_render = False
        try:
            self.rpr_context.set_parameter('iterations', samples)

            for it in range(iterations):
                if self.rpr_engine.test_break():
                    break

                self.notify_status(it / iterations, "Iteration: %d/%d" % (it + 1, iterations))

                with self.render_lock:
                    self.rpr_context.render()

                self.render_event.set()
        finally:
            self.finish_render = True

    def _do_render_tile(self, n, m, samples):
        # TODO: This is a prototype of tile render
        #  currently it produces core error, needs to be checked

        self.finish_render = False
        try:
            self.rpr_context.set_parameter('iterations', samples)

            for i, tile in enumerate(utils.get_tiles(self.rpr_context.width, self.rpr_context.height, n, m)):
                if self.rpr_engine.test_break():
                    break

                self.notify_status(i / (n * m), "Tile: %d/%d" % (i, n * m))

                with self.render_lock:
                    self.rpr_context.render(tile)

                self.render_event.set()
        finally:
            self.finish_render = True


    def render(self, depsgraph):
        if not self.is_synced:
            return

        log("Start render")

        scene = depsgraph.scene
        rpr_scene = scene.rpr

        self.notify_status(0, "Start render")

        result = self.rpr_engine.begin_result(0, 0, self.rpr_context.width, self.rpr_context.height)
        self.rpr_context.clear_frame_buffers()
        self.render_event.clear()

        update_result_thread = threading.Thread(target=RenderEngine._do_update_result, args=(self, result))
        update_result_thread.start()

        self._do_render(rpr_scene.limits.iterations, rpr_scene.limits.iteration_samples)
        #self._do_render_tile(20, 20)

        update_result_thread.join()

        if self.render_event.is_set():
            log('Getting final render result')
            self.rpr_context.resolve()
            self.rpr_context.resolve_extras()
            Engine.set_render_result(self.rpr_context, result.layers[0].passes)

        self.rpr_engine.end_result(result)
        self.notify_status(1, "Finish render")
        log('Finish render')

    def sync(self, depsgraph):
        log('Start syncing')
        self.is_synced = False

        scene = depsgraph.scene
        view_layer = depsgraph.view_layer
        rpr_scene = scene.rpr
        self.status_title = "%s: %s" % (scene.name, view_layer.name)

        self.notify_status(0, "Start syncing")

        rpr_scene.sync(self.rpr_context)

        scene.world.rpr.sync(self.rpr_context)

        # getting visible objects
        for i, obj_instance in enumerate(depsgraph.object_instances):
            obj = obj_instance.object
            self.notify_status(0, "Syncing (%d/%d): %s" % (i, len(depsgraph.object_instances), obj.name))
            obj.rpr.sync(self.rpr_context, obj_instance)

            if self.rpr_engine.test_break():
                log.warn("Syncing stopped by user termination")
                return

        self.rpr_context.scene.set_camera(self.rpr_context.objects[utils.key(scene.camera)])

        self.rpr_context.sync_shadow_catcher()

        view_layer.rpr.sync(view_layer, self.rpr_context, self.rpr_engine)

        self.rpr_context.set_parameter('preview', False)

        self.is_synced = True
        self.notify_status(0, "Finish syncing")
        log('Finish sync')


class PreviewEngine(Engine):
    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)
        self.rpr_context = context.RPRContext()
        self.is_synced = False

    def render(self, depsgraph):
        if not self.is_synced:
            return

        log("Start preview render")

        result = self.rpr_engine.begin_result(0, 0, self.rpr_context.width, self.rpr_context.height)

        self.rpr_context.clear_frame_buffers()
        self.rpr_context.set_parameter('iterations', config.render_preview_iterations)
        self.rpr_context.render()

        self.rpr_context.resolve()
        Engine.set_render_result(self.rpr_context, result.layers[0].passes)
        self.rpr_engine.end_result(result)

        log('Finish preview render')

    def sync(self, depsgraph):
        log('Start preview syncing')
        self.is_synced = False

        rpr_scene = depsgraph.scene.rpr
        rpr_scene.sync(self.rpr_context)

        # getting visible objects
        for i, obj_instance in enumerate(depsgraph.object_instances):
            obj = obj_instance.object

            obj.rpr.sync(self.rpr_context, obj_instance)

        self.rpr_context.scene.set_camera(self.rpr_context.objects[utils.key(depsgraph.scene.camera)])
        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)

        self.rpr_context.set_parameter('preview', False)

        self.is_synced = True
        log('Finish preview sync')


class ViewportEngine(Engine):
    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)

    def render(self, depsgraph):
        log('ViewportEngine.render')

    def sync(self, depsgraph):
        log('ViewportEngine.sync')

    def sync_updated(self, depsgraph):
        ''' sync just the updated things '''
        log("Start ViewportEngine.sync_updated")

        for updated_obj in depsgraph.updates:
            log("updated {}; geometry updated {}; transform updated {}".format(
                updated_obj.id.name, updated_obj.is_updated_geometry, updated_obj.is_updated_transform))

        log("Finish ViewportEngine.sync_updated")

    def draw(self, depsgraph, region, space_data, region_data):
        ''' viewport draw '''
        log("'ViewportEngine.draw")
