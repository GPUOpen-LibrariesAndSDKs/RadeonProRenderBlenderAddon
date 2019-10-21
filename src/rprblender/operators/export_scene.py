"""
Export scene in a specific RPR-compatible file format
"""
import time

from bpy.props import StringProperty, BoolProperty, IntProperty, EnumProperty

import bpy
from bpy_extras.io_utils import ExportHelper
from rprblender.engine.export_engine import ExportEngine
import os.path
import json

from . import RPR_Operator

from rprblender.utils.logging import Log
import pyrpr

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
                filepath_json = os.path.splitext(filepath_frame)[0] + '.json'
                scene.frame_set(i)

                exporter = ExportEngine()
                exporter.sync(context)
                exporter.export_to_rpr(self.filepath, flags)
                self.save_json(filepath_json, scene, context.view_layer)
                log.info(f"Finished frame {i} export to '{filepath_frame}'")

            scene.frame_set(orig_frame)

        else:
            log.info(f"Starting scene '{scene.name}' RPR export to '{self.filepath}'")
            time_started = time.time()

            filepath_json = os.path.splitext(self.filepath)[0] + '.json'
            exporter = ExportEngine()
            exporter.sync(context)
            exporter.export_to_rpr(self.filepath, flags)
            self.save_json(filepath_json, scene, context.view_layer)

        log.info(f"Finished RPR export in {time.time() - time_started} s")

        return {'FINISHED'}

    def save_json(self, filepath, scene, view_layer):
        ''' save scene settings to json at filepath '''
        output_base = os.path.splitext(filepath)[0]

        data = {
            'width': int(scene.render.resolution_x * scene.render.resolution_percentage / 100),
            'height': int(scene.render.resolution_y * scene.render.resolution_percentage / 100),
            'iterations': scene.rpr.limits.max_samples,
            'batchsize': scene.rpr.limits.update_samples,
            'output': output_base + '.png',
            'output.json': output_base + 'output.json'
        }

        # map of aov key to string
        aov_map = {
            pyrpr.AOV_AO: 'ao',
            pyrpr.AOV_BACKGROUND: 'background',
            pyrpr.AOV_COLOR: 'color',
            pyrpr.AOV_DEPTH: 'depth',
            pyrpr.AOV_DIFFUSE_ALBEDO: 'diffuse_albedo',
            pyrpr.AOV_DIRECT_DIFFUSE: 'direct_diffuse',
            pyrpr.AOV_DIRECT_ILLUMINATION: 'direct_illumination',
            pyrpr.AOV_DIRECT_REFLECT: 'direct_reflect',
            pyrpr.AOV_EMISSION: 'emission',
            pyrpr.AOV_GEOMETRIC_NORMAL: 'geometric_normal',
            pyrpr.AOV_INDIRECT_DIFFUSE: 'indirect_diffuse',
            pyrpr.AOV_INDIRECT_ILLUMINATION: 'indirect_illumination',
            pyrpr.AOV_INDIRECT_REFLECT: 'indirect_reflect',
            pyrpr.AOV_LIGHT_GROUP0: 'light_group0',
            pyrpr.AOV_LIGHT_GROUP1: 'light_group1',
            pyrpr.AOV_LIGHT_GROUP2: 'light_group2',
            pyrpr.AOV_LIGHT_GROUP3: 'light_group3',
            pyrpr.AOV_MATERIAL_IDX: 'material_idx',
            pyrpr.AOV_OBJECT_GROUP_ID: 'object_group_id',
            pyrpr.AOV_OBJECT_ID: 'object_id',
            pyrpr.AOV_OPACITY: 'opacity',
            pyrpr.AOV_REFRACT: 'refract',
            pyrpr.AOV_SHADING_NORMAL: 'shading_normal',
            pyrpr.AOV_SHADOW_CATCHER: 'shadow_catcher',
            pyrpr.AOV_UV: 'uv',
            pyrpr.AOV_VELOCITY: 'velocity',
            pyrpr.AOV_VOLUME: 'volume',
            pyrpr.AOV_WORLD_COORDINATE: 'world_coordinate'
        }

        aovs = {}
        for i, enable_aov in enumerate(view_layer.rpr.enable_aovs):
            if enable_aov:
                aov = view_layer.rpr.aovs_info[i]
                aov_name = aov_map[aov['rpr']]
                aovs[aov_name] = output_base + '.' + aov_name + '.png'
        data['aovs'] = aovs

        with open(filepath, 'w') as outfile:
            json.dump(data, outfile)

        





