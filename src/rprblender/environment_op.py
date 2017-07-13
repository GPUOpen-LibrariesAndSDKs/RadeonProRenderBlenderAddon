#!python3
import functools
import traceback

import bpy
import math
import numpy as np
import ctypes
import mathutils

import bgl
import blf

import rprblender
from . import rpraddon
from . import logging
from pathlib import Path
from bpy_extras.image_utils import load_image
from bpy_extras.view3d_utils import (region_2d_to_location_3d, location_3d_to_region_2d)
from . import helpers


def draw_line_3d(start, end, color=(1, 1, 1, 1), width=1):
    bgl.glLineWidth(width)
    bgl.glColor4f(*color)
    bgl.glBegin(bgl.GL_LINES)
    bgl.glVertex3f(*start)
    bgl.glVertex3f(*end)
    bgl.glEnd()


def draw_quad(x1, y1, x2, y2, color):
    bgl.glColor4f(*color)
    bgl.glBegin(bgl.GL_QUADS)
    bgl.glTexCoord2f(0, 0)
    bgl.glVertex2f(x1, y1)
    bgl.glTexCoord2f(0, 1)
    bgl.glVertex2f(x1, y2)
    bgl.glTexCoord2f(1, 1)
    bgl.glVertex2f(x2, y2)
    bgl.glTexCoord2f(1, 0)
    bgl.glVertex2f(x2, y1)
    bgl.glEnd()


image_sun = None
image_map = None


def get_sun_pos(env):
    lib = helpers.render_resources_helper.lib
    lib.set_sun_horizontal_coordinate.argtypes = [ctypes.c_float, ctypes.c_float]
    lib.get_sun_azimuth.restype = ctypes.c_float
    lib.get_sun_altitude.restype = ctypes.c_float

    # set parameters & calculate image
    sun_sky = env.sun_sky

    if sun_sky.type == 'analytical_sky':
        lib.set_sun_horizontal_coordinate(math.degrees(sun_sky.azimuth), math.degrees(sun_sky.altitude))

    sun_azimuth = lib.get_sun_azimuth()
    sun_altitude = lib.get_sun_altitude()

    rot = env.gizmo_rotation
    euler_main_rotation = mathutils.Euler((rot[0], rot[1], rot[2]))
    main_matrix = euler_main_rotation.to_matrix()
    euler_azimut_rotation = mathutils.Euler((0, -sun_altitude, -sun_azimuth - np.pi * 0.5))
    azimut_matrix = euler_azimut_rotation.to_matrix()
    mat = main_matrix * azimut_matrix
    v = mathutils.Vector((1.0, 0.0, 0.0))
    return mat * v


def log_error_context(f):
    @functools.wraps(f)
    def wrapped(*argv):
        try:
            return f(*argv)
        except:
            logging.critical(traceback.format_exc(), tag='render')
            raise
    return wrapped

# reason to add context manager here is to make sure that if code breaks error is logged
# otherwise Blender just swallows exception
@log_error_context
def callback_draw_sun(self, context):
    global image_sun

    if context.space_data.viewport_shade == 'RENDERED':
        return

    if not image_sun:
        path_img = str((Path(rprblender.__file__).parent / 'img/sun.tga').resolve())
        image_sun = load_image(path_img)
        logging.info('image loaded: ', image_sun)
        assert image_sun

    sun_size = 40
    sun_color = (1.0, 0.8, 0.6, 1.0)
    font_height = 18
    distance = 10.0

    vec = get_sun_pos(bpy.context.scene.world.rpr_data.environment)
    if not vec:
        return

    origin_xy = location_3d_to_region_2d(context.region, context.region_data, (0, 0, 0))
    sun_pos2d = location_3d_to_region_2d(context.region, context.region_data, vec * distance)
    if not sun_pos2d:
        return

    bgl.glDisable(bgl.GL_DEPTH_TEST)
    bgl.glEnable(bgl.GL_BLEND)

    sun_half_size = sun_size * 0.5

    x1 = sun_pos2d.x - sun_half_size * 0.5
    y1 = sun_pos2d.y - sun_half_size * 0.5
    x2 = sun_pos2d.x + sun_half_size * 0.5
    y2 = sun_pos2d.y + sun_half_size * 0.5

    bgl.glPolygonMode(bgl.GL_FRONT_AND_BACK, bgl.GL_FILL)

    # draw line from origin
    bgl.glEnable(bgl.GL_LINE_STIPPLE)
    bgl.glLineStipple(1, 0x33333)
    draw_line_3d((origin_xy.x, origin_xy.y, 0), (sun_pos2d.x, sun_pos2d.y, 0), sun_color)
    bgl.glDisable(bgl.GL_LINE_STIPPLE)

    # draw image
    image_sun.gl_load(bgl.GL_NEAREST, bgl.GL_NEAREST)
    bgl.glBindTexture(bgl.GL_TEXTURE_2D, image_sun.bindcode[0])
    bgl.glEnable(bgl.GL_TEXTURE_2D)

    bgl.glColor4f(*sun_color)
    bgl.glBegin(bgl.GL_QUADS)
    bgl.glTexCoord2f(0, 0)
    bgl.glVertex2f(x1, y1)
    bgl.glTexCoord2f(0, 1)
    bgl.glVertex2f(x1, y2)
    bgl.glTexCoord2f(1, 1)
    bgl.glVertex2f(x2, y2)
    bgl.glTexCoord2f(1, 0)
    bgl.glVertex2f(x2, y1)
    bgl.glEnd()
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glDisable(bgl.GL_TEXTURE_2D)

    # draw text
    font_id = 0

    x = sun_pos2d.x + sun_half_size
    y = sun_pos2d.y - font_height * 0.3
    blf.position(font_id, x, y, 0)
    blf.size(font_id, font_height, 72)
    blf.draw(font_id, "Sun")

    # restore opengl defaults
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)

    # reason to add glGetError is to make sure if code produces one it's cleared
    # before other gl code is executed and throws exception which is logged
    assert not bgl.glGetError()


def draw_callback_map(self, context):
    global image_map, image_sun

    if self.area != context.area:
        return

    if not image_sun:
        path_img = str((Path(rprblender.__file__).parent / 'img/sun.tga').resolve())
        image_sun = load_image(path_img)
        logging.info('image loaded: ', image_sun)
        assert image_sun

    if not image_map:
        path_img = str((Path(rprblender.__file__).parent / 'img/worldmap.bmp').resolve())
        image_map = load_image(path_img)
        logging.info('image loaded: ', image_map)
        assert image_map

    # draw image
    image_map.gl_load(bgl.GL_NEAREST, bgl.GL_NEAREST)
    bgl.glBindTexture(bgl.GL_TEXTURE_2D, image_map.bindcode[0])
    bgl.glEnable(bgl.GL_TEXTURE_2D)

    viewport = bgl.Buffer(bgl.GL_INT, 4)
    bgl.glGetIntegerv(bgl.GL_VIEWPORT, viewport)
    width = int(viewport[2])
    height = int(viewport[3])

    dw = width / image_map.size[0]
    dh = height / image_map.size[1]

    d = min(dw, dh)

    im_width = image_map.size[0] * d
    im_height = image_map.size[1] * d

    bgl.glEnable(bgl.GL_BLEND)
    draw_quad(0, 0, width, height, (0, 0, 0, 0.4))
    bgl.glDisable(bgl.GL_BLEND)

    im_x1 = (width - im_width) * 0.5
    im_y1 = (height - im_height) * 0.5
    im_x2 = im_x1 + im_width
    im_y2 = im_y1 + im_height

    draw_quad(im_x1, im_y1, im_x2, im_y2, (1, 1, 1, 1))

    if self.pick_point:
        if self.target_point != self.pick_point:
            if self.pick_point[0] >= im_x1 and self.pick_point[0] <= im_x2 and self.pick_point[1] >= im_y1 and \
                    self.pick_point[1] <= im_y2:
                self.target_point = self.pick_point
                x = self.target_point[0] - im_x1
                y = self.target_point[1] - im_y1

                longi = x / im_width * 2 * np.pi - np.pi
                lati = y / im_height * np.pi - np.pi * 0.5

                self.result = (longi, lati)

    if not self.target_point:
        tp_x = (self.result[0] + np.pi) / (np.pi * 2) * im_width + im_x1
        tp_y = (self.result[1] + np.pi * 0.5) / np.pi * im_height + im_y1
        self.target_point = (tp_x, tp_y)

    if self.target_point:
        bgl.glEnable(bgl.GL_BLEND)
        line_color = (1, 1, 1, 0.2)
        draw_line_3d((0, self.target_point[1], 0), (width, self.target_point[1], 0), line_color)
        draw_line_3d((self.target_point[0], 0, 0), (self.target_point[0], height, 0), line_color)

        image_sun.gl_load(bgl.GL_NEAREST, bgl.GL_NEAREST)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, image_sun.bindcode[0])
        bgl.glEnable(bgl.GL_TEXTURE_2D)

        pt_half_size = 6

        x1 = self.target_point[0] - pt_half_size
        y1 = self.target_point[1] - pt_half_size
        x2 = self.target_point[0] + pt_half_size
        y2 = self.target_point[1] + pt_half_size

        draw_quad(x1, y1, x2, y2, (0, 0, 0, 1.0))

        pt_half_size = 4
        x1 = self.target_point[0] - pt_half_size
        y1 = self.target_point[1] - pt_half_size
        x2 = self.target_point[0] + pt_half_size
        y2 = self.target_point[1] + pt_half_size

        draw_quad(x1, y1, x2, y2, (1, 0.2, 0.2, 1.0))

        bgl.glDisable(bgl.GL_BLEND)
        bgl.glDisable(bgl.GL_TEXTURE_2D)

    # restore opengl
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)


@rpraddon.register_class
class OpLoacationSelectCore(bpy.types.Operator):
    bl_idname = "rpr.location_select_core"
    bl_label = "Location Select Core"

    def modal(self, context, event):
        context.area.tag_redraw()
        context.area.header_text_set("Esc to cancel, Enter/RMB to set location: (latitude: %.2f, longitude: %.2f)" %
                                     (math.degrees(self.result[1]), math.degrees(self.result[0])))

        if event.type == 'LEFTMOUSE':
            self.pick_point = (event.mouse_region_x, event.mouse_region_y)
        elif event.type in {'RIGHTMOUSE', 'RET'} and self.result:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')

            sun_sky = bpy.context.scene.world.rpr_data.environment.sun_sky
            sun_sky.latitude = self.result[1]
            sun_sky.longitude = self.result[0]

            lib = helpers.render_resources_helper.lib
            lib.get_world_utc_offset.argtypes = [ctypes.c_float, ctypes.c_float]
            lib.get_world_utc_offset.restype = ctypes.c_float
            sun_sky.time_zone = lib.get_world_utc_offset(math.degrees(sun_sky.latitude),
                                                         math.degrees(sun_sky.longitude))

            context.area.header_text_set()
            bpy.context.scene.update_tag()
            return {'FINISHED'}
        elif event.type == 'ESC':
            context.area.header_text_set()
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.area.type == 'VIEW_3D':
            sun_sky = bpy.context.scene.world.rpr_data.environment.sun_sky
            self.result = [sun_sky.longitude, sun_sky.latitude]
            self.pick_point = None
            self.target_point = None
            self.area = context.area
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_map, (self, context), 'WINDOW',
                                                                  'POST_PIXEL')
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "'3D View' area not found, cannot run operator")
            return {'CANCELLED'}


@rpraddon.register_class
class OpLoacationSelect(bpy.types.Operator):
    bl_idname = "view3d.location_select"
    bl_label = "Location Select"

    def execute(self, context):
        for wnd in bpy.context.window_manager.windows:
            scr = wnd.screen
            for area in scr.areas:
                if area.type == 'VIEW_3D':
                    for reg in area.regions:
                        if reg.type == 'WINDOW':
                            override = context.copy()
                            override['window'] = wnd
                            override['screen'] = scr
                            override['area'] = area
                            override['region'] = reg
                            bpy.ops.rpr.location_select_core(override, 'INVOKE_AREA')
                            return {'FINISHED'}

        self.report({'WARNING'}, "3D View area not found, please change area type to '3D View'")
        return {'FINISHED'}


@rpraddon.register_class
class OpLoacationSelectByCity(bpy.types.Operator):
    bl_label = "Search Type"
    bl_idname = "rpr.location_select_by_city"
    bl_property = "city_list"

    items = []

    def city_items(self, context):
        return OpLoacationSelectByCity.items

    city_list = bpy.props.EnumProperty(
        name="City list:",
        description="City List",
        items=city_items,
    )

    @staticmethod
    def load_cities():
        lib = helpers.render_resources_helper.lib
        lib.get_city_name_by_index.argtypes = [ctypes.c_int]
        lib.get_city_name_by_index.restype = ctypes.c_char_p
        index = 0
        while True:
            ret = lib.get_city_name_by_index(index)
            if ret is None:
                break
            city_found = ret.decode("utf-8")
            if city_found:
                OpLoacationSelectByCity.items.append((city_found, city_found, ''))
            index += 1

    def execute(self, context):
        lib = helpers.render_resources_helper.lib
        lib.get_city_data.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        lib.get_city_data.restype = ctypes.c_bool

        name = str(self.city_list).encode('utf8')

        latt = np.array([0], dtype=np.float32)
        longi = np.array([0], dtype=np.float32)
        utcoffset = np.array([0], dtype=np.float32)

        res = lib.get_city_data(name,
                                ctypes.c_void_p(latt.ctypes.data),
                                ctypes.c_void_p(longi.ctypes.data),
                                ctypes.c_void_p(utcoffset.ctypes.data))
        if res:
            sun_sky = bpy.context.scene.world.rpr_data.environment.sun_sky
            sun_sky.latitude = math.radians(latt)
            sun_sky.longitude = math.radians(longi)
            sun_sky.time_zone = utcoffset
            context.scene.update_tag()
        else:
            message = "Can't find city '%s'" % self.city_list
            self.report({'ERROR'}, message)
        return {'FINISHED'}

    def invoke(self, context, event):
        if not OpLoacationSelectByCity.items:
            OpLoacationSelectByCity.load_cities()
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


def register():
    logging.debug("environment_op.register()")


def unregister():
    logging.debug("environment_op.unregister()")
