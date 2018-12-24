''' Engine is the functionality of the rendering process, 
maintains context, processes, etc.

Other modules in this directory could be viewport, etc.
'''

''' main Render object '''

import weakref
import functools

import bpy

from rprblender import utils
from rprblender.utils import logging
from . import context
from .notifier import Notifier



log = logging.Log(tag='Engine')


def do_update_result(rpr_engine, rpr_context, view_layer, result):
    if not rpr_context.is_rendering():
        return None

    log("Updating render result")
    view_layer.rpr.set_render_result(rpr_context, result.layers[0])
    rpr_engine.update_result(result)
    return 1.0


class Engine:
    def __init__(self, rpr_engine):
        self.rpr_engine = weakref.ref(rpr_engine)
        self.rpr_context = context.RPRContext()

    def render(self, depsgraph):
        ''' handle the rendering process '''
        view_layer = depsgraph.view_layer
        log("Start render")
        notifier = Notifier(self.rpr_engine(), "%s: %s" % (depsgraph.scene.name, view_layer.name))
        notifier.update_info(0, "Start render")

        result = self.rpr_engine().begin_result(0, 0, self.rpr_context.width, self.rpr_context.height)
        self.rpr_context.clear_frame_buffers()

        bpy.app.timers.register(functools.partial(do_update_result, self.rpr_engine(), self.rpr_context, view_layer, result))

        while self.rpr_context.iterations < self.rpr_context.max_iterations:
            notifier.update_info(self.rpr_context.iterations / self.rpr_context.max_iterations,
                                 "Iteration: %d/%d" % (self.rpr_context.iterations, self.rpr_context.max_iterations))
            self.rpr_context.render()

        log("Updating final render result")
        view_layer.rpr.set_render_result(self.rpr_context, result.layers[0])

        self.rpr_engine().end_result(result)
        notifier.update_info(1, "Finish render")
        log('Finish render')

    def get_image(self):
        self.rpr_context.resolve()
        return self.rpr_context.get_image()

    def sync(self, depsgraph):
        ''' sync all data '''
        log('Start syncing')

        notifier = Notifier(self.rpr_engine(), "%s: %s" % (depsgraph.scene.name, depsgraph.view_layer.name))
        notifier.update_info(0, "Start syncing")

        depsgraph.scene.rpr.sync(self.rpr_context)
        self.rpr_context.set_parameter('preview', depsgraph.mode=='VIEWPORT')

        # getting visible objects
        for i, obj in enumerate(depsgraph.objects):
            notifier.update_info(0, "Syncing (%d/%d): %s" % (i, len(depsgraph.objects), obj.name))
            obj.rpr.sync(self.rpr_context)

        self.rpr_context.scene.set_camera(self.rpr_context.objects[utils.key(depsgraph.scene.camera)])

        self.rpr_context.sync_shadow_catcher()

        depsgraph.view_layer.rpr.sync(depsgraph.view_layer, self.rpr_context, self.rpr_engine())

        notifier.update_info(0, "Finish syncing")
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
