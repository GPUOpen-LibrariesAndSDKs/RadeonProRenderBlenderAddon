''' Engine is the functionality of the rendering process, 
maintains context, processes, etc.

Other modules in this directory could be viewport, etc.
'''

''' main Render object '''

import weakref

from . import context
from rprblender import logging
from rprblender import utils
from .notifier import Notifier


def log(*args):
    logging.info(*args, tag='Engine')


class Engine:
    def __init__(self, rpr_engine):
        self.rpr_engine = weakref.ref(rpr_engine)
        self.rpr_context = context.RPRContext()

    def render(self, depsgraph):
        ''' handle the rendering process '''
        log('Start render')
        notifier = Notifier(self.rpr_engine(), "%s: %s" % (depsgraph.scene.name, depsgraph.view_layer.name))
        notifier.update_info(0, "Start render")
        try:
            while True:
                notifier.update_info(self.rpr_context.iterations / self.rpr_context.max_iterations,
                                     "Iteration: %d/%d" % (self.rpr_context.iterations, self.rpr_context.max_iterations))
                self.rpr_context.render()

        except IndexError as err:
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

        notifier.update_info(0, "Finish syncing")
        log('Finish sync')

    def sync_updated(self, depsgraph):
        ''' sync just the updated things ''' 
        log('Start sync_updated')

        for updated_obj in depsgraph.updates:
            print(updated_obj.id.name, updated_obj.is_dirty_geometry, updated_obj.is_dirty_transform)

        log('Finish sync_updated')

    def draw(self, depsgraph, region, space_data, region_data):
        ''' viewport draw ''' 
        log('draw')