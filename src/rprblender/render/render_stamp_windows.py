import time
import bpy
import numpy as np
import ctypes
from ctypes import windll
from ctypes import Structure, WINFUNCTYPE, c_uint, c_int, byref, c_long, pointer, sizeof, c_char, c_float
from ctypes.wintypes import BYTE, WORD, LONG, DWORD, HWND, HANDLE, LPCWSTR, WPARAM, LPARAM, RECT, POINT, MSG, SIZE
import socket
from . import helpers
from rprblender.versions import get_addon_version
import winreg


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


def get_cpu_name():
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0", 0,winreg.KEY_READ)
        value, regtype = winreg.QueryValueEx(registry_key, 'ProcessorNameString')
        winreg.CloseKey(registry_key)
        return value
    except WindowsError:
        return None


def render_stamp( text, context,  image, image_width, image_height,channels, iter, frame_time ):
    ver = get_addon_version()

    cpu_name = get_cpu_name()
    settings = helpers.get_user_settings()
    hardware = ''
    if settings.device_type == "gpu":
        hardware = helpers.render_resources_helper.get_used_devices()
    elif settings.device_type == "cpu":
        hardware = cpu_name
    else:
        hardware = helpers.render_resources_helper.get_used_devices() + " / " + cpu_name

    render_mode = settings.device_type
    if render_mode:
        render_mode = render_mode.upper()

    text = text.replace("%pt", time.strftime("%H:%M:%S", time.gmtime(frame_time)))
    text = text.replace("%pp", str(iter))
    text = text.replace("%so", str(len(bpy.data.meshes)))
    text = text.replace("%sl", str(len(bpy.data.lamps)))
    text = text.replace("%c", cpu_name)
    text = text.replace("%g", helpers.render_resources_helper.get_used_devices())
    text = text.replace("%r", render_mode) # rendering mode
    text = text.replace("%h", hardware) # used hardware
    text = text.replace("%i", socket.gethostname())            
    text = text.replace("%d", time.strftime("%a, %d %b %Y", time.localtime()))
    text = text.replace("%b", "v%d.%d.%d" % (ver[0], ver[1], ver[2]))
            
    render_text(text,image,image_width, image_height, channels)


def render_text( text, image, image_width, image_height,channels ):
    hf = windll.gdi32.CreateFontW(-12,0, 0, 0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,NONANTIALIASED_QUALITY,DEFAULT_PITCH | FF_DONTCARE,"MS Shell Dlg")
    assert hf

    # create DC
    dc = windll.gdi32.CreateCompatibleDC(None)
    assert dc

    # setup DC
    windll.gdi32.SetTextColor(dc, (255|255<<8|255<<16))
    windll.gdi32.SetBkColor(dc, (0|0<<8|0<<16))
    windll.gdi32.SelectObject(dc, hf)

        # compute text size
    textSize = SIZE()
    assert windll.gdi32.GetTextExtentPoint32W(dc, text, len(text), ctypes.byref(textSize))
    width = textSize.cx + 6	 # add some margins
    height = textSize.cy + 6
    buffer_length = width * height * 4
    if width > image_width:
        width = image_width
    if height > image_height:
        height = image_height

    # create DIB
    bmi = BITMAPINFO()
    head = bmi.bmiHeader
    ctypes.memset(ctypes.byref(head), 0, ctypes.sizeof(bmi.bmiHeader))
    head.biSize        = ctypes.sizeof(BITMAPINFOHEADER)
    head.biWidth       = width
    head.biHeight      = height
    head.biPlanes      = 1
    head.biBitCount    = 32
    head.biCompression = BI_RGB

    dib = windll.gdi32.CreateDIBSection(dc, ctypes.byref(bmi), DIB_RGB_COLORS, None, None, 0)
    assert dib
    old_bitmap = ctypes.windll.gdi32.SelectObject(dc, dib)
    # render text
    r = RECT()
    r.left = 0
    r.top = 2 # offset text a little bit down
    r.right = r.left + width - 1
    r.bottom = r.top + height - 1
    assert windll.user32.DrawTextW(dc, text, -1, byref(r), DT_CENTER | DT_VCENTER | DT_NOPREFIX)
    image_text = ctypes.create_string_buffer(buffer_length)
    ctypes.windll.gdi32.SelectObject(dc, old_bitmap)
    windll.gdi32.GetDIBits(dc, dib, 0, ctypes.c_uint32(height), ctypes.byref(image_text), ctypes.byref(bmi), DIB_RGB_COLORS)

    bytes = np.fromstring(image_text, dtype=np.uint8, count=width*height*4)
    ordered_bytes = np.reshape(bytes, (height, width, 4))

    if channels < 2:
        ordered_image = np.reshape(image, (image_height, image_width,1))
        ordered_image[0:height,image_width - width:,0:1] = ordered_image[0:height,image_width - width:,0:1] * 0.5 + ordered_bytes[:,:,0:1] / 510.0
    else:
        image[0:height,image_width - width:,0:3] = image[0:height,image_width - width:,0:3] * 0.5 + ordered_bytes[:,:,0:3] / 510.0 
                
    ctypes.windll.gdi32.DeleteObject(dib)
    ctypes.windll.gdi32.DeleteDC(dc)
    ctypes.windll.gdi32.DeleteObject(hf)
