"""
Export scene in a specific RPR-compatible file format
"""
import time

from bpy.props import StringProperty, BoolProperty, IntProperty

import bpy
from rprblender.export import (
    camera,
    instance,
    object,
    particle,
    world,
    mesh,
    light,
    to_mesh,
    volume,
)
from bpy_extras.io_utils import ExportHelper
from rprblender.engine.engine import Engine
from rprblender.engine.context import RPRContext

import pyrpr_load_store
from . import RPR_Operator

from rprblender.utils.logging import Log
log = Log(tag='operators.export_scene')


class RPR_EXPORT_OP_export_rpr_scene(RPR_Operator, ExportHelper):
    bl_idname = "rpr.export_scene_rpr"
    bl_label = "RPR (.rpr)"
    bl_description = "Export current scene to RPR file"

    filename_ext: str = ".rpr"

    filter_glob: StringProperty(
        default="*.rpr",
        options={'HIDDEN'},
        maxlen=255,
    )

    export_animation: BoolProperty(
        default=False,
        name="Export Animation"
    )

    start_frame: IntProperty(
        default=0,
        name="Start Frame"
    )

    end_frame: IntProperty(
        default=0,
        name="End Frame"
    )

    def draw(self, context):
        self.layout.prop(self, 'export_animation')
        row = self.layout.row(align=True)
        row.prop(self, 'start_frame')
        row.prop(self, 'end_frame')

    def execute(self, context):
        scene = bpy.context.scene

        if self.export_animation and self.start_frame <= self.end_frame:
            orig_frame = scene.frame_current
            begin, end = self.filepath.rsplit('.', 1)

            log.info(f"Starting scene '{scene.name}' frames {self.start_frame}:{self.end_frame} RPR export")
            time_started = time.time()

            for i in range(self.start_frame, self.end_frame + 1):
                filepath_frame = "{}.{:04}.{}".format(begin, i, end)
                scene.frame_set(i)
                export_rpr_scene(context, filepath_frame)
                log.info(f"Finished frame {i} export to '{filepath_frame}'")

            scene.frame_set(orig_frame)

        else:
            log.info(f"Starting scene '{scene.name}' RPR export to '{self.filepath}'")
            time_started = time.time()

            export_rpr_scene(context, self.filepath)

        log.info(f"Finished RPR export in {time.time() - time_started} s")

        return {'FINISHED'}


def export_rpr_scene(context, filepath):
    volumes_data = []  # to keep volumes data references until export is finished
    depsgraph = context.evaluated_depsgraph_get()
    scene = depsgraph.scene

    rpr_context = RPRContext()

    scene.rpr.init_rpr_context(rpr_context)

    rpr_context.scene.set_name(scene.name)
    rpr_context.width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
    rpr_context.height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

    world.sync(rpr_context, scene.world)

    # camera, objects, particles
    for obj in Engine.depsgraph_objects(depsgraph, with_camera=True):
        object.sync(rpr_context, obj)

        for particle_system in obj.particle_systems:
            particle.sync(rpr_context, particle_system, obj)

    # instances
    for inst in Engine.depsgraph_instances(depsgraph):
        instance.sync(rpr_context, inst)

    # rpr_context parameters
    rpr_context.set_parameter('preview', False)
    scene.rpr.export_ray_depth(rpr_context)
    scene.rpr.export_pixel_filter(rpr_context)

    rpr_context.sync_portal_lights()

    # Exported scene will be rendered vertically flipped, flip it back
    rpr_context.set_parameter('yflip', True)

    pyrpr_load_store.export(filepath, rpr_context.context, rpr_context.scene)

    return {'FINISHED'}
