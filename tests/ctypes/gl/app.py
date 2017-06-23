#!python3

import ctypes
from ctypes import wintypes
from ctypes import windll
from ctypes import Structure, WINFUNCTYPE, c_uint, c_int, byref, c_long, pointer, sizeof, c_char, c_float
from ctypes.wintypes import BYTE, WORD, DWORD, HWND, HANDLE, LPCWSTR, WPARAM, LPARAM, RECT, POINT, MSG

#import OpenGL
#OpenGL.ERROR_ON_COPY = True
#import OpenGL.GL

import win32con
from win32con import *

WM_DESTROY = 0x0002

PFD_TYPE_RGBA       = 0
PFD_TYPE_COLORINDEX = 1

PFD_MAIN_PLANE      = 0
PFD_OVERLAY_PLANE   = 1
PFD_UNDERLAY_PLANE  = (-1)


PFD_DOUBLEBUFFER         = 0x00000001
PFD_STEREO               = 0x00000002
PFD_DRAW_TO_WINDOW       = 0x00000004
PFD_DRAW_TO_BITMAP       = 0x00000008
PFD_SUPPORT_GDI          = 0x00000010
PFD_SUPPORT_OPENGL       = 0x00000020
PFD_GENERIC_FORMAT       = 0x00000040
PFD_NEED_PALETTE         = 0x00000080
PFD_NEED_SYSTEM_PALETTE  = 0x00000100
PFD_SWAP_EXCHANGE        = 0x00000200
PFD_SWAP_COPY            = 0x00000400
PFD_SWAP_LAYER_BUFFERS   = 0x00000800
PFD_GENERIC_ACCELERATED  = 0x00001000
PFD_SUPPORT_DIRECTDRAW   = 0x00002000
PFD_DIRECT3D_ACCELERATED = 0x00004000
PFD_SUPPORT_COMPOSITION  = 0x00008000

PFD_DEPTH_DONTCARE        = 0x20000000
PFD_DOUBLEBUFFER_DONTCARE = 0x40000000
PFD_STEREO_DONTCARE       = 0x80000000


WNDPROCTYPE = WINFUNCTYPE(c_long, wintypes.HWND, c_uint, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSEX(Structure):
    _fields_ = [
        ("cbSize", c_uint),
        ("style", c_uint),
        ("lpfnWndProc", WNDPROCTYPE),
        ("cbClsExtra", c_int),
        ("cbWndExtra", c_int),
        ("hInstance", wintypes.HANDLE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hBrush", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", HANDLE),
    ]

class RECT(Structure):
    _fields_ = [('left', c_long),
                ('top', c_long),
                ('right', c_long),
                ('bottom', c_long)]

class PAINTSTRUCT(Structure):
    _fields_ = [('hdc', c_int),
                ('fErase', c_int),
                ('rcPaint', RECT),
                ('fRestore', c_int),
                ('fIncUpdate', c_int),
                ('rgbReserved', c_char * 32)]

GL_COLOR_BUFFER_BIT             = 0x00004000
GL_VERSION                      = 0x1F02


GetModuleHandle = windll.kernel32.GetModuleHandleW
GetModuleHandle.restype = wintypes.HMODULE
GetModuleHandle.argtypes = [wintypes.LPCWSTR]

hInstance = GetModuleHandle(None)

print(hInstance)

class PIXELFORMATDESCRIPTOR(Structure):
     _fields_ = [
        ('nSize', WORD),
        ('nVersion', WORD),
        ('dwFlags', DWORD),
        ('iPixelType', BYTE),
        ('cColorBits', BYTE),
        ('cRedBits', BYTE),
        ('cRedShift', BYTE),
        ('cGreenBits', BYTE),
        ('cGreenShift', BYTE),
        ('cBlueBits', BYTE),
        ('cBlueShift', BYTE),
        ('cAlphaBits', BYTE),
        ('cAlphaShift', BYTE),
        ('cAccumBits', BYTE),
        ('cAccumRedBits', BYTE),
        ('cAccumGreenBits', BYTE),
        ('cAccumBlueBits', BYTE),
        ('cAccumAlphaBits', BYTE),
        ('cDepthBits', BYTE),
        ('cStencilBits', BYTE),
        ('cAuxBuffers', BYTE),
        ('iLayerType', BYTE),
        ('bReserved', BYTE),
        ('dwLayerMask', DWORD),
        ('dwVisibleMask', DWORD),
        ('dwDamageMask', DWORD),
        ]
        
def wnd_proc(hWnd, Msg, wParam, lParam):
    #print("WndProc", hWnd, Msg, wParam, lParam) 
    if WM_DESTROY == Msg:
        windll.user32.PostQuitMessage(0)
    elif WM_CREATE == Msg:

        pfd = PIXELFORMATDESCRIPTOR()
        pfd.nSize = sizeof(PIXELFORMATDESCRIPTOR)
        pfd.nVersion = 1
        pfd.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER
        pfd.iPixelType = PFD_TYPE_RGBA
        pfd.cColorBits = 32
        pfd.cDepthBits = 24
        pfd.cStencilBits = 8
        pfd.cAccumBits = 0
        pfd.iLayerType = PFD_MAIN_PLANE

        global ourWindowHandleToDeviceContext
        ourWindowHandleToDeviceContext = windll.user32.GetDC(hWnd)
        assert ourWindowHandleToDeviceContext

        letWindowsChooseThisPixelFormat = windll.gdi32.ChoosePixelFormat(ourWindowHandleToDeviceContext, byref(pfd)) 
        windll.gdi32.SetPixelFormat(ourWindowHandleToDeviceContext,letWindowsChooseThisPixelFormat, byref(pfd))

        global ourOpenGLRenderingContext
        ourOpenGLRenderingContext = windll.opengl32.wglCreateContext(ourWindowHandleToDeviceContext)
        windll.opengl32.wglMakeCurrent(ourWindowHandleToDeviceContext, ourOpenGLRenderingContext)
        assert ourOpenGLRenderingContext

        windll.opengl32.glGetString.restype = ctypes.c_char_p
        print("GL_VERSION:", windll.opengl32.glGetString(GL_VERSION))

        global ogllib
        ogllib = ctypes.cdll.LoadLibrary("OpenGL32.dll")
        assert(ogllib)
    elif WM_PAINT == Msg:
        ps = PAINTSTRUCT()
        rect = RECT()
        hdc = windll.user32.BeginPaint(c_int(hWnd), byref(ps))
        windll.user32.GetClientRect(c_int(hWnd), byref(rect))
        windll.user32.DrawTextW(c_int(hdc),
                                "Python Powered Windows" ,
                                c_int(-1), byref(rect), 
                                win32con.DT_SINGLELINE|win32con.DT_CENTER|win32con.DT_VCENTER)
        windll.user32.EndPaint(c_int(hwnd), byref(ps))

        #print("WM_PAINT")
        #ogllib.glClearColor(1, 1, 1, 1);
        windll.opengl32.glClearColor.argtypes = [c_float]*4
        windll.opengl32.glClearColor(1, 0, 0, 1);
        #OpenGL.GL.glClearColor(1, 0, 0, 1);
        #assert not windll.opengl32.glGetError()

        #ogllib.glClear(GL_COLOR_BUFFER_BIT);
        windll.opengl32.glClear(GL_COLOR_BUFFER_BIT);
        #OpenGL.GL.glClear(GL_COLOR_BUFFER_BIT);
        assert not windll.opengl32.glGetError()

        windll.gdi32.SwapBuffers(ourWindowHandleToDeviceContext);

    else:
        windll.user32.DefWindowProcW.restype = ctypes.c_long
        windll.user32.DefWindowProcW.argtypes = [wintypes.HWND, c_uint, wintypes.WPARAM, wintypes.LPARAM]
        return windll.user32.DefWindowProcW(hWnd, Msg, wParam, lParam)
    return 0

CS_OWNDC = 0x0020

wc = WNDCLASSEX() 
wc.cbSize = ctypes.sizeof(WNDCLASSEX)
wc.style = CS_OWNDC
wc.lpfnWndProc = WNDPROCTYPE(wnd_proc)
wc.cbClsExtra = 0
wc.cbWndExtra = 0
wc.hInstance = hInstance
wc.hIcon = 0
wc.hCursor = 0
wc.hBrush = 0
wc.lpszClassName = 0
wc.lpszClassName = "oglversionchecksample"
print(wc)

regRes = windll.user32.RegisterClassExW(byref(wc))
assert regRes
print(regRes) 

WS_OVERLAPPEDWINDOW = 0xcf0000
WS_VISIBLE = 0x10000000

hwnd = windll.user32.CreateWindowExW(
    0,
    wc.lpszClassName, 
    "openglversioncheck",
    WS_OVERLAPPEDWINDOW|WS_VISIBLE,
    0,0,640,480,
    None,None,hInstance,None);

assert hwnd, ctypes.GetLastError()

msg = MSG()
pMsg = pointer(msg)

while windll.user32.GetMessageW( pMsg, win32con.NULL, 0, 0) > 0:
    windll.user32.TranslateMessage(pMsg)
    windll.user32.DispatchMessageW(pMsg)

