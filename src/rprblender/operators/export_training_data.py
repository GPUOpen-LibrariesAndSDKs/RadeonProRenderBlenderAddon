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
Render scene and save predefined AOVs at a specific sample
"""

from pathlib import Path
from bpy.props import BoolProperty, IntProperty, StringProperty

import pyrpr
from rprblender.export import object, camera
from rprblender.engine.export_engine import ExportEngine, ExportEngine2

from . import RPR_Operator

from rprblender.utils.logging import Log

log = Log(tag='operators.export_training_data')


class RPR_EXPORT_OP_export_training_data(RPR_Operator):
    bl_idname = "rpr.export_training_data"
    bl_label = "Export render training data"
    bl_description = "Export training data for an active scene. " \
                     "Render from each camera and save the result aovs to the " \
                     "file formats bin, png, exr, etc." \
                     "Filename example: {camera}.{aov_name}.{sample}.{frame}.{extension}"

    output_path: StringProperty(
        default='',
        name="Output path",
        subtype= "DIR_PATH",
        description="Set directory for output files"
    )
    use_scene_resolution: BoolProperty(
        default=True,
        name="Use Scene Resolution",
        description="If True uses scene render resolution, else uses image_width and image_height"
    )
    extension: StringProperty(
        default='exr',
        name="Extension",
        description="Filename extension for output file: png, bin, jpg, exr, tif, etc"
    )
    width: IntProperty(
        default=800,
        name="Width",
        description="Set render width resolution",
        min=1
    )
    height: IntProperty(
        default=600,
        name="Height",
        description="Set render height resolution",
        min=1
    )
    use_scene_frames: BoolProperty(
        default=True,
        name="Use Scene Resolution",
        description="If True uses scene frame range, else uses frame_start, frame_end",
    )
    frame_start: IntProperty(
        default=1,
        name="FrameSrart",
        description="First render frame",
        min=0
    )
    frame_end: IntProperty(
        default=60,
        name="FrameEnd",
        description="Last render frame",
        min=0
    )
    samples: StringProperty(
        default="1, 2, 4, 8, 4096",
        name="Samples",
        description="Samples to export data",
    )

    def execute(self, context):
        # place more AOV types here by appending aov with tuple of (aov_type, name, channels for bin file format)
        AOVS = (
            (pyrpr.AOV_COLOR, 'Color', 3),
            (pyrpr.AOV_DIFFUSE_ALBEDO, 'DiffuseAlbedo', 3),
            (pyrpr.AOV_DEPTH, 'Depth', 1),
            (pyrpr.AOV_SHADING_NORMAL, 'ColorVariance', 3),
            (pyrpr.AOV_VARIANCE, 'color_variance', 3),
            (pyrpr.AOV_DIRECT_DIFFUSE, 'DirectDiffuse', 3),
            (pyrpr.AOV_DIRECT_ILLUMINATION, 'DirectIllumination', 3),
            (pyrpr.AOV_DIRECT_REFLECT, 'DirectReflect', 3),
            (pyrpr.AOV_INDIRECT_DIFFUSE, 'IndirectDiffuse', 3),
            (pyrpr.AOV_INDIRECT_ILLUMINATION, 'IndirectIllumination', 3),
            (pyrpr.AOV_INDIRECT_REFLECT, 'IndirectReflect', 3),
            (pyrpr.AOV_UV, 'UV', 3),
            (pyrpr.AOV_VELOCITY, 'Velocity', 3),
            (pyrpr.AOV_WORLD_COORDINATE, 'WorldCoordinate', 3)
        )

        output_path = Path(self.output_path)
        if not output_path.is_dir():
            log.error('No such directory')
            return {'CANCELLED'}

        cameras = tuple(obj for obj in context.scene.objects if obj.type == 'CAMERA')

        if not cameras:
            log.error("No camera in scene")
            return {'CANCELLED'}

        frame_start = context.scene.frame_start
        frame_end = context.scene.frame_end

        if not self.use_scene_frames:
            frame_start = self.frame_start
            frame_end = self.frame_end

        if frame_end < frame_start:
            frame_end = frame_start

        log(f"Directory path: {self.output_path}")

        for frame in range(frame_start, frame_end + 1):
            context.scene.frame_set(frame, subframe=0.0)
            depsgraph = context.evaluated_depsgraph_get()
            scene = depsgraph.scene

            if scene.rpr.final_render_mode == 'FULL':  # Export Legacy mode using RPR1
                exporter = ExportEngine()
            else:  # Other quality modes export using RPR2
                exporter = ExportEngine2()

            exporter.sync(context)
            rpr_context = exporter.rpr_context

            if self.use_scene_resolution:
                rpr_context.width = int(context.scene.render.resolution_x *
                                        context.scene.render.resolution_percentage / 100)
                rpr_context.height = int(context.scene.render.resolution_y *
                                         context.scene.render.resolution_percentage / 100)
            else:
                rpr_context.width = self.width
                rpr_context.height = self.height

            # clear exported and enable predefined AOVs
            rpr_context.disable_aovs()
            for aov in AOVS:
                rpr_context.enable_aov(aov_type=aov[0])

            if rpr_context.do_motion_blur and scene.rpr.final_render_mode == 'FULL2':
                flag = not bool(scene.rpr.motion_blur_in_velocity_aov)
                rpr_context.set_parameter(pyrpr.CONTEXT_BEAUTY_MOTION_BLUR, flag)

            for cam in cameras:
                # EXPORT CAMERA
                camera_key = object.key(cam)  # current camera key
                rpr_camera = rpr_context.create_camera(camera_key)
                rpr_context.scene.set_camera(rpr_camera)
                camera_obj = depsgraph.objects.get(camera_key, None)
                camera_data = camera.CameraData.init_from_camera(camera_obj.data, camera_obj.matrix_world,
                                                                 rpr_context.width / rpr_context.height)
                camera_data.export(rpr_camera)

                if rpr_context.do_motion_blur:
                    rpr_camera.set_exposure(scene.camera.data.rpr.motion_blur_exposure)
                    object.export_motion_blur(rpr_context, camera_key,
                                              object.get_transform(camera_obj))

                # adaptive subdivision will be limited to the current scene render size
                rpr_context.sync_auto_adapt_subdivision()

                # render part
                log.info(f"Start render, camera: {cam.name}, "
                         f"resolution: [{rpr_context.width}, {rpr_context.height}], frame: {frame}")

                samples = sorted(tuple(int(s) for s in self.samples.split(',')))

                for i, sample in enumerate(samples):
                    update_samples = (sample - samples[i - 1]) if i > 0 else sample
                    rpr_context.set_parameter(pyrpr.CONTEXT_ITERATIONS, update_samples)
                    rpr_context.render(restart=(i == 0))
                    rpr_context.resolve()
                    log(f"Render sample {sample}, frame {frame}")

                    for aov in AOVS:
                        aov_type, aov_name, aov_channels = aov
                        filepath = str(output_path /
                                       f"{cam.name}.{aov_name}.{sample:04d}.{frame:04d}.{self.extension}")
                        fb = rpr_context.get_frame_buffer(aov_type)

                        if self.extension == 'bin':
                            data = fb.get_data()
                            data = data[:, :, :aov_channels]
                            data.tofile(filepath)
                        else:
                            fb.save_to_file(file_path=filepath)

                        log.info(f"File saved at {sample} samples, {filepath}")

                    # clearing scene after finishing render
                    log(f"Finish render, camera: {cam.name}")
            rpr_context.clear_scene()

        log.info(f"Finish render for all cameras")

        return {'FINISHED'}
