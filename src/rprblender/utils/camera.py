import numpy as np

import bpy
import pyrpr


def get_camera_settings(camera: bpy.types.Camera, transform, ratio):
    settings = {
        'clip_plane': (camera.clip_start, camera.clip_end),
        'lens_shift': (camera.shift_x, camera.shift_y),   # TODO: Shift has to be fixed
        'focal_length': camera.lens,
        'sensor_size': (camera.sensor_width, camera.sensor_width / ratio),
        'transform': tuple(transform),
    }

    if camera.type == 'PERSP':
        settings['mode'] = pyrpr.CAMERA_MODE_PERSPECTIVE
        # TODO: check for more perspective parameters

    elif camera.type == 'ORTHO':
        settings['mode'] = pyrpr.CAMERA_MODE_ORTHOGRAPHIC
        # TODO: set orthographic parameters

    elif camera.type == 'PANO':
        settings['mode'] = pyrpr.CAMERA_MODE_LATITUDE_LONGITUDE_360
        #TODO: set panoramic parameters

    else:
        raise TypeError("Not supported camera type", camera.type)

    return settings


def get_viewport_camera_settings(context: bpy.types.Context):
    settings = {}

    ratio = context.region.width / context.region.height
    if context.region_data.view_perspective == 'PERSP':
        settings['mode'] = pyrpr.CAMERA_MODE_PERSPECTIVE
        settings['clip_plane'] = (context.space_data.clip_start, context.space_data.clip_end)
        settings['sensor_size'] = (context.space_data.lens, context.space_data.lens / ratio)

    elif context.region_data.view_perspective == 'CAMERA':
        # TODO: set camera parameters
        pass

    elif context.region_data.view_perspective == 'ORTHO':
        settings['mode'] = pyrpr.CAMERA_MODE_ORTHOGRAPHIC
        # TODO: set ORTHO parameters

    else:
        raise KeyError("Not supported view_perspective type", context.region_data.view_perspective)

    settings['transform'] = tuple(context.region_data.view_matrix.inverted())
    return settings


def set_camera_settings(rpr_camera: pyrpr.Camera, settings):
    rpr_camera.set_mode(settings['mode'])
    rpr_camera.set_clip_plane(*settings['clip_plane'])
    rpr_camera.set_sensor_size(*settings['sensor_size'])
    rpr_camera.set_transform(np.array(settings['transform'], dtype=np.float32))

    if 'focal_length' in settings:
        rpr_camera.set_focal_length(settings['focal_length'])
