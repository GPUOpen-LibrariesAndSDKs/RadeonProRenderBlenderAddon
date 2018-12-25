''' Engine is the functionality of the rendering process, 
maintains context, processes, etc.

Other modules in this directory could be viewport, etc.
'''

''' main Render object '''

import weakref
import threading
import time
import numpy as np

import bpy

from rprblender import utils
from rprblender.utils import logging
from . import context
from .notifier import Notifier
from rprblender.properties.view_layer import RPR_ViewLayerProperites
from rprblender import config


log = logging.Log(tag='Engine')


class Engine:
    def __init__(self, rpr_engine):
        self.rpr_engine = weakref.proxy(rpr_engine)
        self.rpr_context = context.RPRContext()

        self.render_lock = threading.Lock()
        self.is_synced = False

    def set_render_result(self, render_layer: bpy.types.RenderLayer):
        def zeros_image(channels):
            return np.zeros((self.rpr_context.height, self.rpr_context.width, channels), dtype=np.float32)

        images = []

        for p in render_layer.passes:
            try:
                aov = next(aov for aov in RPR_ViewLayerProperites.aovs_info if aov['name'] == p.name)  # finding corresponded aov
                image = self.rpr_context.get_image(aov['rpr'])

            except StopIteration:
                log.warn("AOV '{}' is not found".format(p.name))
                image = zeros_image(p.channels)

            except KeyError:
                # This could happen when Depth or Combined was not selected, but they still are in view_layer.use_pass_*
                log.warn("AOV '{}' is not enabled in rpr_context".format(aov['name']))
                image = zeros_image(p.channels)

            if p.channels != image.shape[2]:
                image = image[:, :, 0:p.channels]

            images.append(image.flatten())

        # efficient way to copy all AOV images
        render_layer.passes.foreach_set('rect', np.concatenate(images))

    def do_update_result(self, view_layer, result):
        while not self.rpr_engine.test_break():
            time.sleep(config.render_update_result_interval)

            resolved = False
            with self.render_lock:
                if self.rpr_context.iterations > self.rpr_context.resolved_iterations:
                    self.rpr_context.resolve()
                    resolved = True

            if not resolved:
                continue

            log("Updating render result")
            self.rpr_context.resolve_extras()
            self.set_render_result(result.layers[0])
            self.rpr_engine.update_result(result)

            if self.rpr_context.iterations >= self.rpr_context.max_iterations:
                break

    def do_render(self, notifier):
        while not self.rpr_engine.test_break():
            if self.rpr_context.iterations >= self.rpr_context.max_iterations:
                break

            notifier.update_info(self.rpr_context.iterations / self.rpr_context.max_iterations,
                                 "Iteration: %d/%d" % (self.rpr_context.iterations, self.rpr_context.max_iterations))

            with self.render_lock:
                self.rpr_context.render()

    def render(self, depsgraph):
        ''' handle the rendering process '''

        if not self.is_synced:
            return

        log("Start render")

        view_layer = depsgraph.view_layer
        notifier = Notifier(self.rpr_engine, "%s: %s" % (depsgraph.scene.name, view_layer.name))
        notifier.update_info(0, "Start render")

        result = self.rpr_engine.begin_result(0, 0, self.rpr_context.width, self.rpr_context.height)
        self.rpr_context.clear_frame_buffers()

        if self.rpr_engine.is_preview:
            self.do_render(notifier)

        else:
            update_result_thread = threading.Thread(target=Engine.do_update_result, args=(self, view_layer, result))
            update_result_thread.start()

            self.do_render(notifier)

            update_result_thread.join()

        log('Getting final render result')
        if self.rpr_context.iterations > self.rpr_context.resolved_iterations:
            self.rpr_context.resolve()
            self.rpr_context.resolve_extras()
            self.set_render_result(result.layers[0])

        self.rpr_engine.end_result(result)
        notifier.update_info(1, "Finish render")
        log('Finish render')

    def sync(self, depsgraph):
        ''' sync all data '''
        log('Start syncing')
        self.is_synced = False

        notifier = Notifier(self.rpr_engine, "%s: %s" % (depsgraph.scene.name, depsgraph.view_layer.name))
        notifier.update_info(0, "Start syncing")

        depsgraph.scene.rpr.sync(self.rpr_context)
        self.rpr_context.set_parameter('preview', depsgraph.mode=='VIEWPORT')

        # getting visible objects
        for i, obj in enumerate(depsgraph.objects):
            notifier.update_info(0, "Syncing (%d/%d): %s" % (i, len(depsgraph.objects), obj.name))
            obj.rpr.sync(self.rpr_context)

            if self.rpr_engine.test_break():
                log.warn("Syncing stopped by user termination")
                return

        self.rpr_context.scene.set_camera(self.rpr_context.objects[utils.key(depsgraph.scene.camera)])

        self.rpr_context.sync_shadow_catcher()

        depsgraph.view_layer.rpr.sync(depsgraph.view_layer, self.rpr_context, self.rpr_engine)

        if self.rpr_engine.is_preview:
            self.rpr_context.set_parameter('iterations', config.render_preview_iterations)
            self.rpr_context.set_max_iterations(1)

        notifier.update_info(0, "Finish syncing")

        self.is_synced = True
        log('Finish sync')

    def sync_updated(self, depsgraph):
        ''' sync just the updated things ''' 
        log('Start sync_updated')

        for updated_obj in depsgraph.updates:
            log("updated {}; geometry updated {}; transform updated {}".format(
                updated_obj.id.name, updated_obj.is_updated_geometry, updated_obj.is_updated_transform))

        log('Finish sync_updated')

    def draw(self, depsgraph, region, space_data, region_data):
        ''' viewport draw ''' 
#        log('draw')
        pass
