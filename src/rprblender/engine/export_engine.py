"""
Scene export to file
"""


import pyrpr_load_store

from rprblender.export import (
    instance,
    object,
    particle,
    world,
    volume,
)
from .context import RPRContext
from .engine import Engine


from rprblender.utils.logging import Log
log = Log(tag='engine.export_engine')


class ExportEngine(Engine):
    TYPE = 'EXPORT_TO_FILE'

    def __init__(self):
        self.rpr_context = RPRContext()
        self.rpr_context.engine_type = self.TYPE

    def render(self):
        pass

    def sync(self, context):
        """ Prepare scene for export """
        depsgraph = context.evaluated_depsgraph_get()
        scene = depsgraph.scene

        scene.rpr.init_rpr_context(self.rpr_context)

        self.rpr_context.scene.set_name(scene.name)
        self.rpr_context.width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
        self.rpr_context.height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

        world.sync(self.rpr_context, scene.world)

        # camera, objects, particles
        for obj in self.depsgraph_objects(depsgraph,with_camera=True):
            object.sync(self.rpr_context, obj)

            for particle_system in obj.particle_systems:
                particle.sync(self.rpr_context, particle_system, obj)

        # instances
        for inst in self.depsgraph_instances(depsgraph):
            instance.sync(self.rpr_context, inst)

        # rpr_context parameters
        self.rpr_context.set_parameter('preview', False)
        scene.rpr.export_ray_depth(self.rpr_context)

        self.rpr_context.sync_portal_lights()

        # Exported scene will be rendered vertically flipped, flip it back
        self.rpr_context.set_parameter('yflip', True)

    def export_to_rpr(self, filepath: str):
        """
        Export scene to RPR file
        :param filepath: full output file path, including filename extension
        """
        pyrpr_load_store.export(filepath, self.rpr_context.context, self.rpr_context.scene)

        return {'FINISHED'}
