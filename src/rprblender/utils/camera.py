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
    ortho_size: (float, float) = None


def get_camera_data(camera: bpy.types.Camera, transform, ratio):
    data = CameraData()
    data.clip_plane = (camera.clip_start, camera.clip_end)
    data.transform = tuple(transform)

    if camera.sensor_fit == 'VERTICAL':
        data.lens_shift = (camera.shift_x / ratio, camera.shift_y)
    elif camera.sensor_fit == 'HORIZONTAL':
        data.lens_shift = (camera.shift_x, camera.shift_y * ratio)
    elif camera.sensor_fit == 'AUTO':
        data.lens_shift = (camera.shift_x, camera.shift_y * ratio) if ratio > 1.0 else \
            (camera.shift_x / ratio, camera.shift_y)

    if camera.type == 'PERSP':
        data.mode = pyrpr.CAMERA_MODE_PERSPECTIVE
        data.focal_length = camera.lens
        if camera.sensor_fit == 'VERTICAL':
            data.sensor_size = (camera.sensor_height * ratio, camera.sensor_height)
        elif camera.sensor_fit == 'HORIZONTAL':
            data.sensor_size = (camera.sensor_width, camera.sensor_width / ratio)
        elif camera.sensor_fit == 'AUTO':
            data.sensor_size = (camera.sensor_width, camera.sensor_width / ratio) if ratio > 1.0 else \
                               (camera.sensor_width * ratio, camera.sensor_width)
        else:
            raise ValueError("Incorrect camera.sensor_fit value", camera, camera.sensor_fit)

    elif camera.type == 'ORTHO':
        data.mode = pyrpr.CAMERA_MODE_ORTHOGRAPHIC
        if camera.sensor_fit == 'VERTICAL':
            data.ortho_size = (camera.ortho_scale * ratio, camera.ortho_scale)
        elif camera.sensor_fit == 'HORIZONTAL':
            data.ortho_size = (camera.ortho_scale, camera.ortho_scale / ratio)
        elif camera.sensor_fit == 'AUTO':
            data.ortho_size = (camera.ortho_scale, camera.ortho_scale / ratio) if ratio > 1.0 else \
                              (camera.ortho_scale * ratio, camera.ortho_scale)

    elif camera.type == 'PANO':
        # TODO: Recheck parameters for PANO camera
        data.mode = pyrpr.CAMERA_MODE_LATITUDE_LONGITUDE_360
        data.focal_length = camera.lens
        if camera.sensor_fit == 'VERTICAL':
            data.sensor_size = (camera.sensor_height * ratio, camera.sensor_height)
        elif camera.sensor_fit == 'HORIZONTAL':
            data.sensor_size = (camera.sensor_width, camera.sensor_width / ratio)
        elif camera.sensor_fit == 'AUTO':
            data.sensor_size = (camera.sensor_width, camera.sensor_width / ratio) if ratio > 1.0 else \
                               (camera.sensor_width * ratio, camera.sensor_width)
        else:
            raise ValueError("Incorrect camera.sensor_fit value", camera, camera.sensor_fit)

    else:
        raise ValueError("Incorrect camera.type value",camera, camera.type)

    return data


def get_viewport_camera_data(context: bpy.types.Context):
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
        data = get_camera_data(camera_obj.data, context.region_data.view_matrix.inverted(), ratio)

        # This formula was taken from previous plugin with corresponded comment
        # See blender/intern/cycles/blender/blender_camera.cpp:blender_camera_from_view (look for 1.41421f)
        zoom = 4.0 / (2.0 ** 0.5 + context.region_data.view_camera_zoom / 50.0) ** 2

        data.lens_shift = (data.lens_shift[0] / zoom, data.lens_shift[1] / zoom)

        if data.mode == pyrpr.CAMERA_MODE_ORTHOGRAPHIC:
            data.ortho_size = (data.ortho_size[0] * zoom, data.ortho_size[1] * zoom)
        else:
            data.sensor_size = (data.sensor_size[0] * zoom, data.sensor_size[1] * zoom)

    else:
        raise KeyError("Not supported view_perspective type", context.region_data.view_perspective)

    return data


def set_camera_data(rpr_camera: pyrpr.Camera, data: CameraData):
    rpr_camera.set_mode(data.mode)
    rpr_camera.set_clip_plane(*data.clip_plane)
    rpr_camera.set_lens_shift(*data.lens_shift)

    if data.mode == pyrpr.CAMERA_MODE_PERSPECTIVE:
        rpr_camera.set_sensor_size(*data.sensor_size)
        rpr_camera.set_focal_length(data.focal_length)

    elif data.mode == pyrpr.CAMERA_MODE_ORTHOGRAPHIC:
        rpr_camera.set_ortho(*data.ortho_size)

    elif data.mode == pyrpr.CAMERA_MODE_LATITUDE_LONGITUDE_360:
        rpr_camera.set_sensor_size(*data.sensor_size)
        rpr_camera.set_focal_length(data.focal_length)

    rpr_camera.set_transform(np.array(data.transform, dtype=np.float32))
