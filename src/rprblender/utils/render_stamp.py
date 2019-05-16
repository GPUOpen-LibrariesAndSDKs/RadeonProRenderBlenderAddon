"""
Render render stamp text to the image in the right bottom corner.
This version uses Windows API so it's compatible only with Windows operation system.
"""
# TODO: try to use bgl and blf modules to render text in platform independent way

import platform

import pyrpr

from . import logging
log = logging.Log(tag="render_stamp")


if 'Windows' != platform.system():
    # WinAPI text rendering doesn't work on Ubuntu and MacOS, use empty placeholder
    def render_stamp(text, image, image_width, image_height, channels, iter, frame_time):
        """Placeholder for non-Windows systems"""
        pass
    render_stamp_supported = False

else:
    # Windows specific imports and code
    import bpy
    import numpy as np
    import time

    import socket
    import ctypes
    from ctypes import windll
    from ctypes.wintypes import RECT, SIZE

    from rprblender import bl_info

    FW_NORMAL = 400
    DEFAULT_CHARSET = 1
    OUT_DEFAULT_PRECIS = 0
    CLIP_DEFAULT_PRECIS = 0
    NONANTIALIASED_QUALITY = 3
    DEFAULT_PITCH = 0
    FF_DONTCARE = 0
    BI_RGB = 0
    DIB_RGB_COLORS = 0
    CBM_INIT = 4
    TRANSPARENT = 1
    DT_CENTER = 0x00000001
    DT_VCENTER = 0x00000004
    DT_NOPREFIX = 0x00000800
    KEY_READ = 0x20019

    HKEY_CLASSES_ROOT = 0x80000000
    HKEY_CURRENT_USER = 0x80000001
    HKEY_LOCAL_MACHINE = 0x80000002


    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ('biSize', ctypes.c_uint32),
            ('biWidth', ctypes.c_int),
            ('biHeight', ctypes.c_int),
            ('biPlanes', ctypes.c_short),
            ('biBitCount', ctypes.c_short),
            ('biCompression', ctypes.c_uint32),
            ('biSizeImage', ctypes.c_uint32),
            ('biXPelsPerMeter', ctypes.c_long),
            ('biYPelsPerMeter', ctypes.c_long),
            ('biClrUsed', ctypes.c_uint32),
            ('biClrImportant', ctypes.c_uint32)
        ]


    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ('bmiHeader', BITMAPINFOHEADER),
            ('bmiColors', ctypes.c_ulong * 3)
        ]


    def render_stamp(text, image, image_width, image_height, channels, frame_iter, frame_time):
        """
        Render info text with requested data to the source image
        :param text: text string for render
        :type text: str
        :param image: source image to blend text into
        :type image: np.Array
        :param image_width: source image width
        :type image_width: int
        :param image_height: source image height
        :type image_height: int
        :param channels: source image bytes per pixel
        :type channels: int
        :param frame_iter: current frame iteration number
        :type frame_iter: int
        :param frame_time: current frame render time
        :type frame_time: Time
        :return: source image with integrated text
        :rtype: np.Array
        """
        # Collect info the user could request for render stamp
        ver = bl_info['version']

        cpu_name = pyrpr.Context.cpu_device['name']
        devices = bpy.context.scene.rpr.devices
        hardware = ''
        render_mode = ''
        selected_gpu_names = ''
        for i, gpu_state in enumerate(devices.gpu_states):
            if gpu_state:
                name = pyrpr.Context.gpu_devices[i]['name']
                if selected_gpu_names:
                    selected_gpu_names += " + {}".format(name)
                else:
                    selected_gpu_names += name

        if selected_gpu_names:
            hardware = selected_gpu_names
            render_mode = "GPU"
            if devices.cpu_state:
                 hardware = hardware + " / "
                 render_mode = render_mode + " + "
        if devices.cpu_state:
            hardware += cpu_name
            render_mode = render_mode + "CPU"

        # Replace markers with collected info
        text = text.replace("%pt", time.strftime("%H:%M:%S", time.gmtime(frame_time)))
        text = text.replace("%pp", str(frame_iter))
        text = text.replace("%so", str(len(bpy.data.meshes)))
        text = text.replace("%sl", str(len(bpy.data.lights)))
        text = text.replace("%c", cpu_name)
        text = text.replace("%g", selected_gpu_names)
        text = text.replace("%r", render_mode)
        text = text.replace("%h", hardware)
        text = text.replace("%i", socket.gethostname())
        text = text.replace("%d", time.strftime("%a, %d %b %Y", time.localtime()))
        text = text.replace("%b", "v%d.%d.%d" % (ver[0], ver[1], ver[2]))

        # do the actual text render
        return render_text_to_image(text, image, image_width, image_height, channels)


    def render_text_to_image(text, image, image_width, image_height, channels):
        """
        Use Windows API to draw text to source image
        :param text: text string to render
        :type text: str
        :param image: source image
        :type image: np.Array
        :param image_width:
        :type image_width: int
        :param image_height:
        :type image_height: int
        :param channels: bytes per pixel
        :type channels: int
        :return: source image with integrated text
        :rtype: np.Array
        """

        # Use Windows system font
        font_header = windll.gdi32.CreateFontW(-12, 0, 0, 0, FW_NORMAL, 0, 0, 0,
                                               DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                               NONANTIALIASED_QUALITY, DEFAULT_PITCH | FF_DONTCARE,
                                               "MS Shell Dlg")
        assert font_header

        # Setup device context
        device_context = windll.gdi32.CreateCompatibleDC(None)
        assert device_context
        windll.gdi32.SetTextColor(device_context, (255 | 255 << 8 | 255 << 16))
        windll.gdi32.SetBkColor(device_context, (0 | 0 << 8 | 0 << 16))
        windll.gdi32.SelectObject(device_context, font_header)

        # compute text size
        textSize = SIZE()
        assert windll.gdi32.GetTextExtentPoint32W(device_context, text, len(text), ctypes.byref(textSize))
        width = textSize.cx + 6  # add some margins
        height = textSize.cy + 6
        buffer_length = width * height * 4
        if width > image_width:
            width = image_width
        if height > image_height:
            height = image_height

        # prepare text bitmap info
        bitmap_info = BITMAPINFO()
        bitmap_header = bitmap_info.bmiHeader
        ctypes.memset(ctypes.byref(bitmap_header), 0, ctypes.sizeof(bitmap_info.bmiHeader))
        bitmap_header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bitmap_header.biWidth = width
        bitmap_header.biHeight = height
        bitmap_header.biPlanes = 1
        bitmap_header.biBitCount = 32
        bitmap_header.biCompression = BI_RGB
        bitmap = windll.gdi32.CreateDIBSection(device_context, ctypes.byref(bitmap_info), DIB_RGB_COLORS, None, None, 0)
        assert bitmap
        old_bitmap = ctypes.windll.gdi32.SelectObject(device_context, bitmap)

        # render text to bitmap
        r = RECT()
        r.left = 0
        r.top = 2  # offset text a little bit down
        r.right = r.left + width - 1
        r.bottom = r.top + height - 1
        assert windll.user32.DrawTextW(device_context, text, -1, ctypes.byref(r), DT_CENTER | DT_VCENTER | DT_NOPREFIX)
        image_text = ctypes.create_string_buffer(buffer_length)
        ctypes.windll.gdi32.SelectObject(device_context, old_bitmap)
        windll.gdi32.GetDIBits(device_context, bitmap, 0, ctypes.c_uint32(height),
                               ctypes.byref(image_text), ctypes.byref(bitmap_info),
                               DIB_RGB_COLORS)
        text_bytes = np.fromstring(image_text, dtype=np.uint8, count=width * height * 4)

        # reshape both images in the same way
        ordered_image = np.reshape(image, (image_height, image_width, channels))
        ordered_text_bytes = np.reshape(text_bytes, (height, width, 4))

        ctypes.windll.gdi32.DeleteObject(bitmap)
        ctypes.windll.gdi32.DeleteDC(device_context)
        ctypes.windll.gdi32.DeleteObject(font_header)

        # blend text image to the right bottom corner of the source image
        if channels == 1:
            ordered_image[0:height, image_width-width:, 0:1] = \
                ordered_image[0:height, image_width-width:, 0:1] * 0.5 + ordered_text_bytes[:, :, 0:1] / 510.0
        else:
            ordered_image[0:height, image_width-width:, 0:3] = \
                ordered_image[0:height, image_width-width:, 0:3] * 0.5 + ordered_text_bytes[:, :, 0:3] / 510.0

        return ordered_image

    render_stamp_supported = True
