#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
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
from rprblender.utils.user_settings import get_user_settings

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

        if scene.camera is None:
            log.error("No camera in scene, skipping export")
            return {'FINISHED'}

        flags = 1 << 5 # RPRLOADSTORE_EXPORTFLAG_EMBED_FILE_IMAGES_USING_OBJECTNAME
        # RPRLOADSTORE_EXPORTFLAG_EXTERNALFILES (1 << 0) - image data will be stored to rprs external file
        # RPRLOADSTORE_EXPORTFLAG_COMPRESS_IMAGE_LEVEL_1 (1 << 1) - lossless image
        # RPRLOADSTORE_EXPORTFLAG_COMPRESS_IMAGE_LEVEL_2 (1 << 2) - lossy image
        # RPRLOADSTORE_EXPORTFLAG_COMPRESS_FLOAT_TO_HALF_NORMALS (1 << 3) 
        # RPRLOADSTORE_EXPORTFLAG_COMPRESS_FLOAT_TO_HALF_UV (1 << 4) 
        if not self.export_as_single_file:
            flags |= 1 << 0
        
        compression = {'NONE': 0,
                        'LOW': 1 << 1,
                        'MEDIUM': 1 << 2,
                        'HIGH': 1 << 2 | 1 << 3 | 1 << 4}
        flags |= compression[self.compression]

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
                exporter.export_to_rpr(filepath_frame, flags)
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
            pyrpr.AOV_DIFFUSE_ALBEDO: 'albedo.diffuse',
            pyrpr.AOV_DIRECT_DIFFUSE: 'direct.diffuse',
            pyrpr.AOV_DIRECT_ILLUMINATION: 'direct.illumination',
            pyrpr.AOV_DIRECT_REFLECT: 'direct.reflect',
            pyrpr.AOV_EMISSION: 'emission',
            pyrpr.AOV_GEOMETRIC_NORMAL: 'normal.geom',
            pyrpr.AOV_INDIRECT_DIFFUSE: 'indirect.diffuse',
            pyrpr.AOV_INDIRECT_ILLUMINATION: 'indirect.illumination',
            pyrpr.AOV_INDIRECT_REFLECT: 'indirect.reflect',
            pyrpr.AOV_LIGHT_GROUP0: 'light.group0',
            pyrpr.AOV_LIGHT_GROUP1: 'light.group1',
            pyrpr.AOV_LIGHT_GROUP2: 'light.group2',
            pyrpr.AOV_LIGHT_GROUP3: 'light.group3',
            pyrpr.AOV_MATERIAL_ID: 'material.id',
            pyrpr.AOV_OBJECT_GROUP_ID: 'group.id',
            pyrpr.AOV_OBJECT_ID: 'object.id',
            pyrpr.AOV_OPACITY: 'opacity',
            pyrpr.AOV_REFRACT: 'refract',
            pyrpr.AOV_SHADING_NORMAL: 'normal',
            pyrpr.AOV_SHADOW_CATCHER: 'shadow.catcher',
            pyrpr.AOV_REFLECTION_CATCHER: 'reflection.catcher',
            pyrpr.AOV_UV: 'uv',
            pyrpr.AOV_VELOCITY: 'velocity',
            pyrpr.AOV_VARIANCE: 'variance',
            pyrpr.AOV_VOLUME: 'volume',
            pyrpr.AOV_WORLD_COORDINATE: 'world.coordinate'
        }

        aovs = {}
        for i, enable_aov in enumerate(view_layer.rpr.enable_aovs):
            if enable_aov:
                aov = view_layer.rpr.aovs_info[i]
                aov_name = aov_map[aov['rpr']]
                aovs[aov_name] = output_base + '.' + aov_name + '.png'
        data['aovs'] = aovs

        # set devices based on final render
        device_settings = {}
        devices = get_user_settings().final_devices
        
        device_settings['cpu'] = int(devices.cpu_state)
        device_settings['threads'] = devices.cpu_threads
        
        for i, gpu_state in enumerate(devices.available_gpu_states):
            device_settings[f'gpu{i}'] = int(gpu_state)

        data['context'] = device_settings

        with open(filepath, 'w') as outfile:
            json.dump(data, outfile)
