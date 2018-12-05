''' Engine is the functionality of the rendering process, 
maintains context, processes, etc.

Other modules in this directory could be viewport, etc.
'''

''' main Render object '''


class Engine:

    def __init__(self, rpr_engine, data):
        self.rpr_engine = rpr_engine
        self.data = data

    def render(self, depsgraph):
        ''' handle the rendering process ''' 
        print('Engine.render')


    def sync(self, depsgraph):
        ''' sync all data ''' 
        print('Engine.sync')

        # export scene data, set denoisers, etc
        # scene = self.data.scene
        # scene.rpr.sync(context)

        # walk depsgraph
        for instance in depsgraph.object_instances:
            if instance.is_instance:  # Real dupli instance
                obj = dup.instance_object.original
            else:  # Usual object
                obj = instance.object.original
            
            # these ids are weird.  Needs more investigation
            print("instance of %s" % obj.name, instance.random_id, instance.persistent_id)

            # run the "sync" method of the obj
            context = None # dummy rpr context
            if hasattr(obj, 'rpr'):
                obj.rpr.sync(context)
            else:
                print('not exporting', obj.name)

    def sync_updated(self, depsgraph):
        ''' sync just the updated things ''' 
        print('Engine.sync_updated')
        for updated_obj in depsgraph.updates:
            print(updated_obj.id.name, updated_obj.is_dirty_geometry, updated_obj.is_dirty_transform)

    def draw(self, depsgraph, region, space_data, region_data):
        ''' viewport draw ''' 
        print('Engine.draw')