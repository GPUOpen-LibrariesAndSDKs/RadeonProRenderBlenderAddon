''' Engine is the functionality of the rendering process, 
maintains context, processes, etc.

Other modules in this directory could be viewport, etc.
'''

''' main Render object '''

import weakref
import pyrpr
from . import context
from rprblender import logging


def log(*args):
    logging.info(*args, tag='Engine')


class Engine:
    def __init__(self, rpr_engine):
        self.rpr_engine = weakref.ref(rpr_engine)
        self.context = context.RPRContext()

    def render(self):
        ''' handle the rendering process '''
        log('Start render')

        try:
            while True:
                log("Render iterations: %d/%d" % (self.context.iterations, self.context.max_iterations))
                self.context.render()

        except IndexError as err:
            log('Finish render')

    def get_image(self):
        self.context.resolve()
        return self.context.get_image()

    def sync(self, depsgraph):
        ''' sync all data '''
        log('Start sync')

        # export scene data, set denoisers, etc
        scene = depsgraph.scene
        scene.rpr.sync(self.context, depsgraph)

        ## walk depsgraph
        #for instance in depsgraph.object_instances:
        #    if instance.is_instance:  # Real dupli instance
        #        obj = dup.instance_object.original
        #    else:  # Usual object
        #        obj = instance.object.original

        #    # these ids are weird.  Needs more investigation
        #    print("instance of %s" % obj.name, instance.random_id, instance.persistent_id)

        #    # run the "sync" method of the obj
        #    context = None # dummy rpr context
        #    if hasattr(obj, 'rpr'):
        #        obj.rpr.sync(context)
        #    else:
        #        print('not exporting', obj.name)

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