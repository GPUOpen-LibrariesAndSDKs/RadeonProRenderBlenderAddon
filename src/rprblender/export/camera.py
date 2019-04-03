from dataclasses import dataclass
import numpy as np
import copy

import bpy
import pyrpr
import sys

from rprblender.engine.context import RPRContext
from . import object

from rprblender.utils import logging
log = logging.Log(tag='export.camera')


@dataclass(init=False, eq=True)
class CameraData:
    """ Comparable dataclass which holds all camera settings """

    mode: int = None
    clip_plane: (float, float) = None
    focal_length: float = None
    sensor_size: (float, float) = None
    transform: tuple = None
    lens_shift: (float, float) = None
    ortho_size: (float, float) = None
    dof_enable: bool = False
    dof_fstop: float = None
    dof_blades: int = None
    dof_focus_distance: float = None

    @staticmethod
    def init_from_camera(camera: bpy.types.Camera, transform, ratio, border=((0, 0), (1, 1))):
        """ Returns CameraData from bpy.types.Camera """

        def get_focus_distance(camera_data):
            ''' get focus distance from obj if set else the actual distance '''
            if not camera_data.dof_object:
                return camera_data.dof_distance

            obj_pos = camera_data.dof_object.matrix_world.to_translation()
            camera_pos = transform.to_translation()
            direction = obj_pos - camera_pos
            return direction.length

        pos, size = border

        data = CameraData()
        data.clip_plane = (camera.clip_start, camera.clip_end)
        data.transform = tuple(transform)

        
        focus_distance = get_focus_distance(camera)
        # enable dof is distance is set
        data.dof_enable = (focus_distance != 0.0)
        if data.dof_enable:
            data.dof_fstop = camera.gpu_dof.fstop
            data.dof_blades = max(camera.gpu_dof.blades, 4)
            data.dof_focus_distance = max(focus_distance, 0.001)
        else:
            data.dof_fstop = sys.float_info.max

        if camera.sensor_fit == 'VERTICAL':
            data.lens_shift = (camera.shift_x / ratio, camera.shift_y)
        elif camera.sensor_fit == 'HORIZONTAL':
            data.lens_shift = (camera.shift_x, camera.shift_y * ratio)
        elif camera.sensor_fit == 'AUTO':
            data.lens_shift = (camera.shift_x, camera.shift_y * ratio) if ratio > 1.0 else \
                (camera.shift_x / ratio, camera.shift_y)
        else:
            raise ValueError("Incorrect camera.sensor_fit value", camera, camera.sensor_fit)

        data.lens_shift = tuple(data.lens_shift[i] / size[i] + (pos[i] + size[i] * 0.5 - 0.5) / size[i] for i in (0, 1))

        if camera.type == 'PERSP':
            data.mode = pyrpr.CAMERA_MODE_PERSPECTIVE
            data.focal_length = camera.lens
            if camera.sensor_fit == 'VERTICAL':
                data.sensor_size = (camera.sensor_height * ratio, camera.sensor_height)
            elif camera.sensor_fit == 'HORIZONTAL':
                data.sensor_size = (camera.sensor_width, camera.sensor_width / ratio)
            else:
                data.sensor_size = (camera.sensor_width, camera.sensor_width / ratio) if ratio > 1.0 else \
                                   (camera.sensor_width * ratio, camera.sensor_width)

            data.sensor_size = tuple(data.sensor_size[i] * size[i] for i in (0, 1))


        elif camera.type == 'ORTHO':
            data.mode = pyrpr.CAMERA_MODE_ORTHOGRAPHIC
            if camera.sensor_fit == 'VERTICAL':
                data.ortho_size = (camera.ortho_scale * ratio, camera.ortho_scale)
            elif camera.sensor_fit == 'HORIZONTAL':
                data.ortho_size = (camera.ortho_scale, camera.ortho_scale / ratio)
            else:
                data.ortho_size = (camera.ortho_scale, camera.ortho_scale / ratio) if ratio > 1.0 else \
                                  (camera.ortho_scale * ratio, camera.ortho_scale)

            data.ortho_size = tuple(data.ortho_size[i] * size[i] for i in (0, 1))

        elif camera.type == 'PANO':
            # TODO: Recheck parameters for PANO camera
            data.mode = pyrpr.CAMERA_MODE_LATITUDE_LONGITUDE_360
            data.focal_length = camera.lens
            if camera.sensor_fit == 'VERTICAL':
                data.sensor_size = (camera.sensor_height * ratio, camera.sensor_height)
            elif camera.sensor_fit == 'HORIZONTAL':
                data.sensor_size = (camera.sensor_width, camera.sensor_width / ratio)
            else:
                data.sensor_size = (camera.sensor_width, camera.sensor_width / ratio) if ratio > 1.0 else \
                                   (camera.sensor_width * ratio, camera.sensor_width)

            data.sensor_size = tuple(data.sensor_size[i] * size[i] for i in (0, 1))

        else:
            raise ValueError("Incorrect camera.type value",camera, camera.type)

        return data

    @staticmethod
    def init_from_context(context: bpy.types.Context):
        """ Returns CameraData from bpy.types.Context """

        VIEWPORT_SENSOR_SIZE = 72.0     # this constant was found experimentally, didn't find such option in
                                        # context.space_data or context.region_data

        ratio = context.region.width / context.region.height
        if context.region_data.view_perspective == 'PERSP':
            data = CameraData()
            data.mode = pyrpr.CAMERA_MODE_PERSPECTIVE
            data.clip_plane = (context.space_data.clip_start, context.space_data.clip_end)
            data.lens_shift = (0.0, 0.0)
            data.focal_length = context.space_data.lens
            data.sensor_size = (VIEWPORT_SENSOR_SIZE, VIEWPORT_SENSOR_SIZE / ratio) if ratio > 1.0 else \
                               (VIEWPORT_SENSOR_SIZE * ratio, VIEWPORT_SENSOR_SIZE)
            data.transform = tuple(context.region_data.view_matrix.inverted())

        elif context.region_data.view_perspective == 'ORTHO':
            data = CameraData()
            data.mode = pyrpr.CAMERA_MODE_ORTHOGRAPHIC
            ortho_size = context.region_data.view_distance * VIEWPORT_SENSOR_SIZE / context.space_data.lens
            data.lens_shift = (0.0, 0.0)
            data.clip_plane = (-context.space_data.clip_end * 0.5, context.space_data.clip_end * 0.5)
            data.ortho_size = (ortho_size, ortho_size / ratio) if ratio > 1.0 else \
                              (ortho_size * ratio, ortho_size)

            data.transform = tuple(context.region_data.view_matrix.inverted())

        elif context.region_data.view_perspective == 'CAMERA':
            camera_obj = context.space_data.camera
            data = CameraData.init_from_camera(camera_obj.data, context.region_data.view_matrix.inverted(), ratio)

            # This formula was taken from previous plugin with corresponded comment
            # See blender/intern/cycles/blender/blender_camera.cpp:blender_camera_from_view (look for 1.41421f)
            zoom = 4.0 / (2.0 ** 0.5 + context.region_data.view_camera_zoom / 50.0) ** 2

            # Updating lens_shift due to viewport zoom and view_camera_offset
            # view_camera_offset should be multiplied by 2
            data.lens_shift = ((data.lens_shift[0] + context.region_data.view_camera_offset[0] * 2) / zoom,
                               (data.lens_shift[1] + context.region_data.view_camera_offset[1] * 2) / zoom)

            if data.mode == pyrpr.CAMERA_MODE_ORTHOGRAPHIC:
                data.ortho_size = (data.ortho_size[0] * zoom, data.ortho_size[1] * zoom)
            else:
                data.sensor_size = (data.sensor_size[0] * zoom, data.sensor_size[1] * zoom)

        else:
            raise ValueError("Incorrect view_perspective value", context.region_data.view_perspective)

        return data

    def export(self, rpr_camera: pyrpr.Camera, tile=((0.0, 0.0), (1.0, 1.0))):
        """
        Set CameraData to pyrpr.Camera
        :param rpr_camera: pyrpr.Camera
        :param tile: tuple of tile position <tuple> and tile size <tuple> normalized to 1
        """

        pos, size = tile

        rpr_camera.set_mode(self.mode)
        rpr_camera.set_clip_plane(*self.clip_plane)

        # following formula is used:
        #   lens_shift = lens_shift * resolution / tile_size + (center - resolution/2) / tile_size
        # where: center = tile_pos + tile_size/2
        lens_shift = tuple(self.lens_shift[i] / size[i] + (pos[i] + size[i] * 0.5 - 0.5) / size[i] for i in (0, 1))
        rpr_camera.set_lens_shift(*lens_shift)

        if self.mode == pyrpr.CAMERA_MODE_PERSPECTIVE:
            sensor_size = tuple(self.sensor_size[i] * size[i] for i in (0, 1))
            rpr_camera.set_sensor_size(*sensor_size)
            rpr_camera.set_focal_length(self.focal_length)

        elif self.mode == pyrpr.CAMERA_MODE_ORTHOGRAPHIC:
            ortho_size = tuple(self.ortho_size[i] * size[i] for i in (0, 1))
            rpr_camera.set_ortho(*ortho_size)

        elif self.mode == pyrpr.CAMERA_MODE_LATITUDE_LONGITUDE_360:
            # TODO: Fix panoramic camera with tile render
            rpr_camera.set_sensor_size(*self.sensor_size)
            rpr_camera.set_focal_length(self.focal_length)

        if self.dof_enable:
            rpr_camera.set_focus_distance(self.dof_focus_distance)
            rpr_camera.set_f_stop(self.dof_fstop)
            rpr_camera.set_aperture_blades(self.dof_blades)
        else:
            # if disabled f_stop will be max float
            rpr_camera.set_f_stop(self.dof_fstop)

        rpr_camera.set_transform(np.array(self.transform, dtype=np.float32))




def sync(rpr_context: RPRContext, obj: bpy.types.Object):
    """ Creates pyrpr.Camera from obj.data: bpy.types.Camera """

    camera = obj.data
    log("sync", camera)

    rpr_camera = rpr_context.create_camera(object.key(obj))
    rpr_camera.set_name(camera.name)

    settings = CameraData.init_from_camera(camera, obj.matrix_world, rpr_context.width / rpr_context.height)
    settings.export(rpr_camera)
