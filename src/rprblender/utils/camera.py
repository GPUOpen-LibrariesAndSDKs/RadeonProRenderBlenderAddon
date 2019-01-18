from dataclasses import dataclass
import numpy as np

import bpy
import pyrpr


@dataclass(init=False, eq=True)
class CameraData:
    mode: int = None
    clip_plane: (float, float) = None
    focal_length: float = None
    sensor_size: (float, float) = None
    transform: tuple = None
    lens_shift: (float, float) = None


def get_camera_data(camera: bpy.types.Camera, transform, ratio):
    data = CameraData()
    data.clip_plane = (camera.clip_start, camera.clip_end)
    data.lens_shift = (camera.shift_x, camera.shift_y)   # TODO: Shift has to be fixed
    data.focal_length = camera.lens
    data.sensor_size = (
        camera.sensor_width,
        camera.sensor_width if ratio < 1 else (camera.sensor_width / ratio)
    )
    data.transform = tuple(transform)

    if camera.type == 'PERSP':
        data.mode = pyrpr.CAMERA_MODE_PERSPECTIVE
        # TODO: check for more perspective parameters

    elif camera.type == 'ORTHO':
        data.mode = pyrpr.CAMERA_MODE_ORTHOGRAPHIC
        # TODO: set orthographic parameters

    elif camera.type == 'PANO':
        data.mode = pyrpr.CAMERA_MODE_LATITUDE_LONGITUDE_360
        #TODO: set panoramic parameters

    else:
        raise TypeError("Not supported camera type", camera.type)

    return data


def get_viewport_camera_data(context: bpy.types.Context):
    data = CameraData()

    ratio = context.region.width / context.region.height
    if context.region_data.view_perspective == 'PERSP':
        data.mode = pyrpr.CAMERA_MODE_PERSPECTIVE
        data.clip_plane = (context.space_data.clip_start, context.space_data.clip_end)
        data.sensor_size = (
            context.space_data.lens, 
            context.space_data.lens if ratio < 1 else (context.space_data.lens / ratio)
        )
        # TODO: settings.focal_length

    elif context.region_data.view_perspective == 'CAMERA':
        # TODO: set camera parameters
        pass

    elif context.region_data.view_perspective == 'ORTHO':
        data.mode = pyrpr.CAMERA_MODE_ORTHOGRAPHIC
        # TODO: set ORTHO parameters

    else:
        raise KeyError("Not supported view_perspective type", context.region_data.view_perspective)

    data.transform = tuple(context.region_data.view_matrix.inverted())
    return data


def set_camera_data(rpr_camera: pyrpr.Camera, data: CameraData):
    rpr_camera.set_mode(data.mode)
    rpr_camera.set_clip_plane(*data.clip_plane)
    rpr_camera.set_sensor_size(*data.sensor_size)
    rpr_camera.set_transform(np.array(data.transform, dtype=np.float32))

    if data.focal_length is not None:
        rpr_camera.set_focal_length(data.focal_length)
