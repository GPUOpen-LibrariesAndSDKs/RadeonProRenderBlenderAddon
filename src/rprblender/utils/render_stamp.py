"""
Render render stamp text to the image in the right bottom corner.
This version uses Windows API so it's compatible only with Windows operation system.
"""
# TODO: try to use bgl and blf modules to render text in platform independent way

import platform


from . import logging
log = logging.Log(tag="render_stamp")


# WinAPI text rendering doesn't work on Ubuntu and MacOS, use empty placeholder
if platform.system() == 'Windows':
    # Windows specific imports and constants
    import numpy as np

    import ctypes
    from ctypes import windll
    from ctypes.wintypes import RECT, SIZE

    TEXT_BRIGHTNESS_DECREASE_COEFF = 510.0
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

    FONT_NAME = "MS Shell Dlg"


class BitmapInfoHeader(ctypes.Structure):
    """ DIB/BMP BITMAPINFOHEADER structure """
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


class BitmapInfo(ctypes.Structure):
    """ DIB/BMP BITMAPINFO structure """
    _fields_ = [
        ('bmiHeader', BitmapInfoHeader),
        ('bmiColors', ctypes.c_ulong * 3)
    ]


class Win32GdiFont:
    """ Support class to handle Win32 GDI font object for stamp text rendering """
    def __init__(self, font_name):
        """ Create GDI font object """
        self.font_header = windll.gdi32.CreateFontW(-12, 0, 0, 0, FW_NORMAL, 0, 0, 0,
                                               DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                               NONANTIALIASED_QUALITY, DEFAULT_PITCH | FF_DONTCARE,
                                               font_name)
        assert self.font_header, f"GDI font '{font_name}' creation failure"

    def __enter__(self):
        return self.font_header

    def __exit__(self, exc_type, exc_val, exc_tb):
        ctypes.windll.gdi32.DeleteDC(self.font_header)


class Win32GdiDeviceContext:
    """ Support class to handle Win32 GDI device context object """
    def __init__(self, font_header):
        self.device_context = windll.gdi32.CreateCompatibleDC(None)
        assert self.device_context, "GDI device context creation failure"
        windll.gdi32.SetTextColor(self.device_context, (255 | 255 << 8 | 255 << 16))
        windll.gdi32.SetBkColor(self.device_context, (0 | 0 << 8 | 0 << 16))
        windll.gdi32.SelectObject(self.device_context, font_header)

    def __enter__(self):
        return self.device_context

    def __exit__(self, exc_type, exc_val, exc_tb):
        ctypes.windll.gdi32.DeleteDC(self.device_context)


class Win32GdiBitmap:
    """ Support class to handle Win32 GDI device independent bitmap object """
    def __init__(self, device_context, width, height):
        self.bitmap_info = BitmapInfo()
        bitmap_header = self.bitmap_info.bmiHeader
        ctypes.memset(ctypes.byref(bitmap_header), 0, ctypes.sizeof(self.bitmap_info.bmiHeader))
        bitmap_header.biSize = ctypes.sizeof(BitmapInfoHeader)
        bitmap_header.biWidth = width
        bitmap_header.biHeight = height
        bitmap_header.biPlanes = 1
        bitmap_header.biBitCount = 32
        bitmap_header.biCompression = BI_RGB
        self.bitmap = windll.gdi32.CreateDIBSection(device_context, ctypes.byref(self.bitmap_info), DIB_RGB_COLORS, None, None, 0)
        assert self.bitmap, "GDI bitmap creation failed"

    def __enter__(self):
        return self.bitmap, self.bitmap_info

    def __exit__(self, exc_type, exc_val, exc_tb):
        ctypes.windll.gdi32.DeleteDC(self.bitmap)


if platform.system() != 'Windows':
    def render(text, image_width, image_height):
        """ Unable to render """
        log.debug(f"Render stamp for operation system '{platform.system()}' is not implemented yet")
        raise NotImplementedError()
else:
    def render(text, image_width, image_height):
        """
        Render stamp text as bitmap using Windows GDI32 API, return pixels and actual stamp image size
        """
        with Win32GdiFont(FONT_NAME) as font_header:
            with Win32GdiDeviceContext(font_header) as device_context:
                # compute text size
                text_size = SIZE()
                assert windll.gdi32.GetTextExtentPoint32W(device_context, text, len(text), ctypes.byref(text_size))

                # add some margins
                width = text_size.cx + 6
                height = text_size.cy + 6

                buffer_length = width * height * 4

                # clip by image size
                if width > image_width:
                    width = image_width
                if height > image_height:
                    height = image_height

                r = RECT()
                r.left = 0
                r.top = 2  # offset text a little bit down
                r.right = r.left + width - 1
                r.bottom = r.top + height - 1

                # render text to bitmap
                with Win32GdiBitmap(device_context, width, height) as (bitmap, bitmap_info):
                    old_bitmap = windll.gdi32.SelectObject(device_context, bitmap)
                    assert windll.user32.DrawTextW(device_context, text, -1, ctypes.byref(r),
                                                   DT_CENTER | DT_VCENTER | DT_NOPREFIX)
                    ctypes.windll.gdi32.SelectObject(device_context, old_bitmap)
                    text_image_buffer = ctypes.create_string_buffer(buffer_length)
                    windll.gdi32.GetDIBits(device_context, bitmap, 0, ctypes.c_uint32(height),
                                           ctypes.byref(text_image_buffer), ctypes.byref(bitmap_info),
                                           DIB_RGB_COLORS)

                    # extract bitmap pixels to array
                    text_image_bytes = np.frombuffer(text_image_buffer, dtype=np.uint8, count=width * height * 4)

        # Turn text int pixels to white-over-black floats
        ordered_text_bytes = np.reshape(text_image_bytes, (height * width, 4))
        black_white_rect = [
            [1.0, 1.0, 1.0, 1.0] if e[0] > 0 else [0.0, 0.0, 0.0, 1.0]
            for e in ordered_text_bytes
        ]

        return black_white_rect, width, height


