"""
Export scene in a specific RPR-compatible file format
"""
import time

from bpy.props import StringProperty, BoolProperty, IntProperty, EnumProperty

import bpy
from bpy_extras.io_utils import ExportHelper
from rprblender.engine.export_engine import ExportEngine

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

    export_as_single_file: BoolProperty(
        default=False,
        name="Export Single File"
    )

    compression: EnumProperty(
        items=(('NONE', 'None', 'None'),
               ('LOW', 'Low', 'Lossless texture compression'),
               ('MEDIUM', 'Medium', 'Lossy texture compression'),
               ('HIGH', 'High', 'Lossy texture and geometry compression')),
        default='LOW',
        name="Compression"
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
        self.layout.prop(self, 'export_as_single_file')
        self.layout.prop(self, 'compression')

    def execute(self, context):
        scene = bpy.context.scene

        flags = 0
        # RPRLOADSTORE_EXPORTFLAG_EXTERNALFILES (1 << 0) - image data will be stored to rprs external file
        # RPRLOADSTORE_EXPORTFLAG_COMPRESS_IMAGE_LEVEL_1 (1 << 1) - lossless image
        # RPRLOADSTORE_EXPORTFLAG_COMPRESS_IMAGE_LEVEL_2 (1 << 2) - lossy image
        # RPRLOADSTORE_EXPORTFLAG_COMPRESS_FLOAT_TO_HALF_NORMALS (1 << 3) 
        # RPRLOADSTORE_EXPORTFLAG_COMPRESS_FLOAT_TO_HALF_UV (1 << 4) 
        if self.export_as_single_file:
            flags += 1 << 0
        
        compression = {'NONE': 0,
                        'LOW': 1 << 1,
                        'MEDIUM': 1 << 2,
                        'HIGH': 1 << 2 + 1 << 3 + 1 << 4}
        flags += compression[self.compression]

        if self.export_animation and self.start_frame <= self.end_frame:
            orig_frame = scene.frame_current
            begin, end = self.filepath.rsplit('.', 1)

            log.info(f"Starting scene '{scene.name}' frames {self.start_frame}:{self.end_frame} RPR export")
            time_started = time.time()

            for i in range(self.start_frame, self.end_frame + 1):
                filepath_frame = "{}.{:04}.{}".format(begin, i, end)
                scene.frame_set(i)

                exporter = ExportEngine()
                exporter.sync(context)
                exporter.export_to_rpr(self.filepath, flags)
                log.info(f"Finished frame {i} export to '{filepath_frame}'")

            scene.frame_set(orig_frame)

        else:
            log.info(f"Starting scene '{scene.name}' RPR export to '{self.filepath}'")
            time_started = time.time()

            exporter = ExportEngine()
            exporter.sync(context)
            exporter.export_to_rpr(self.filepath, flags)

        log.info(f"Finished RPR export in {time.time() - time_started} s")

        return {'FINISHED'}

