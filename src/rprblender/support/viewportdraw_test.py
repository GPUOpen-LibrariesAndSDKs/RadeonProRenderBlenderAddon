#!python3

import sys
import platform
import traceback
import ctypes
from ctypes import *

import numpy as np
import imageio
import pytest

import rprtesting
import viewportdraw

if sys.platform == 'linux':
    gl = ctypes.cdll.LoadLibrary('libGL.so')
elif sys.platform == 'darwin':
    gl = ctypes.cdll.LoadLibrary('libGL.dylib')
else:
    gl = ctypes.windll.opengl32

GL_PROJECTION = 0x1701
GL_RGBA = 0x1908
GL_UNSIGNED_BYTE = 0x1401
GL_COLOR_BUFFER_BIT = 0x00004000
GL_VERSION = 0x1F02

gl.glClearColor.argtypes = [ctypes.c_float] * 4


def draw_image(im, viewport_size, tile=(1, 1)):
    texture = viewportdraw.create_texture(im)
    viewportdraw.draw_image_texture(texture, viewport_size, tile)

if 'Linux' == platform.system():
    pass
elif 'Darwin' == platform.system():
    pass
else:
    from ctypes import windll
    from ctypes.wintypes import *
    import win32con

    windows_message2name = {}
    for name in dir(win32con):
        if name.startswith('WM_'):
            windows_message2name[getattr(win32con, name)] = name

    PFD_TYPE_RGBA = 0
    PFD_TYPE_COLORINDEX = 1

    PFD_MAIN_PLANE = 0
    PFD_OVERLAY_PLANE = 1
    PFD_UNDERLAY_PLANE = (-1)

    PFD_DOUBLEBUFFER = 0x00000001
    PFD_STEREO = 0x00000002
    PFD_DRAW_TO_WINDOW = 0x00000004
    PFD_DRAW_TO_BITMAP = 0x00000008
    PFD_SUPPORT_GDI = 0x00000010
    PFD_SUPPORT_OPENGL = 0x00000020
    PFD_GENERIC_FORMAT = 0x00000040
    PFD_NEED_PALETTE = 0x00000080
    PFD_NEED_SYSTEM_PALETTE = 0x00000100
    PFD_SWAP_EXCHANGE = 0x00000200
    PFD_SWAP_COPY = 0x00000400
    PFD_SWAP_LAYER_BUFFERS = 0x00000800
    PFD_GENERIC_ACCELERATED = 0x00001000
    PFD_SUPPORT_DIRECTDRAW = 0x00002000
    PFD_DIRECT3D_ACCELERATED = 0x00004000
    PFD_SUPPORT_COMPOSITION = 0x00008000

    PFD_DEPTH_DONTCARE = 0x20000000
    PFD_DOUBLEBUFFER_DONTCARE = 0x40000000
    PFD_STEREO_DONTCARE = 0x80000000

    WNDPROCTYPE = ctypes.WINFUNCTYPE(c_long, HWND, c_uint, WPARAM, LPARAM)

    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [
            ("cbSize", c_uint),
            ("style", c_uint),
            ("lpfnWndProc", WNDPROCTYPE),
            ("cbClsExtra", c_int),
            ("cbWndExtra", c_int),
            ("hInstance", HANDLE),
            ("hIcon", HANDLE),
            ("hCursor", HANDLE),
            ("hBrush", HBRUSH),
            ("lpszMenuName", LPCWSTR),
            ("lpszClassName", LPCWSTR),
            ("hIconSm", HANDLE),
        ]


    class RECT(ctypes.Structure):
        _fields_ = [
            ('left', c_long),
            ('top', c_long),
            ('right', c_long),
            ('bottom', c_long)
        ]


    class PAINTSTRUCT(ctypes.Structure):
        _fields_ = [
            ('hdc', c_int),
            ('fErase', c_int),
            ('rcPaint', RECT),
            ('fRestore', c_int),
            ('fIncUpdate', c_int),
            ('rgbReserved', c_char * 32)
        ]


    class Bitmap(ctypes.Structure):
        _fields_ = [
            ("bitmapType", c_long),
            ("width", c_long),
            ("height", c_long),
            ("widthBytes", c_long),
            ("planes", c_short),
            ("bitsPerPixel", c_short),
            ("data", ctypes.POINTER(c_ulong))]


    class PIXELFORMATDESCRIPTOR(ctypes.Structure):
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


    class WindowRendererFixture:

        def __init__(self):
            GetModuleHandle = windll.kernel32.GetModuleHandleW
            GetModuleHandle.restype = HMODULE
            GetModuleHandle.argtypes = [LPCWSTR]

            self.hinstance = GetModuleHandle(None)

            CS_OWNDC = 0x0020

            wc = WNDCLASSEX()
            wc.cbSize = ctypes.sizeof(WNDCLASSEX)
            wc.style = CS_OWNDC
            wc.lpfnWndProc = WNDPROCTYPE(self.wnd_proc)
            wc.cbClsExtra = 0
            wc.cbWndExtra = 0
            wc.hInstance = self.hinstance
            wc.hIcon = 0
            wc.hCursor = 0
            wc.hBrush = 0
            wc.lpszClassName = 0
            wc.lpszClassName = "oglversionchecksample"

            self.wc = wc

            result = windll.user32.RegisterClassExW(byref(wc))
            assert result

        def wnd_proc(self, hWnd, Msg, wParam, lParam):
            print("WndProc", hWnd, windows_message2name.get(Msg, Msg), wParam, lParam)

            if win32con.WM_CREATE == Msg:

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

                device_context = windll.user32.GetDC(hWnd)
                assert device_context
                windll.gdi32.SetPixelFormat(device_context, windll.gdi32.ChoosePixelFormat(device_context, byref(pfd)),
                                            byref(pfd))

                wgl_context = windll.opengl32.wglCreateContext(device_context)
                assert wgl_context
                windll.opengl32.wglMakeCurrent(device_context, wgl_context)

                windll.opengl32.glGetString.restype = ctypes.c_char_p
                print("GL_VERSION:", windll.opengl32.glGetString(GL_VERSION))

            elif win32con.WM_PAINT == Msg:
                # just an example how to paint window text
                rect = RECT()
                windll.user32.GetClientRect(c_int(hWnd), byref(rect))
                ps = PAINTSTRUCT()
                windll.user32.DrawTextW(c_int(windll.user32.BeginPaint(c_int(hWnd), byref(ps))),
                                        "hello, world!",
                                        c_int(-1), byref(rect),
                                        win32con.DT_SINGLELINE | win32con.DT_CENTER | win32con.DT_VCENTER)
                windll.user32.EndPaint(c_int(hWnd), byref(ps))

                width, height = rect.right - rect.left, rect.bottom - rect.top

                gl.glClearColor(1, 0, 0, 1)

                gl.glClear(GL_COLOR_BUFFER_BIT)
                assert not gl.glGetError()

                gl.glMatrixMode(GL_PROJECTION)
                gl.glLoadIdentity();
                gl.glOrtho(0, width, 0, height, -1.0, 1.0);

                try:
                    self.testee(width, height)
                except:
                    self.error = traceback.format_exc()

                windll.opengl32.glReadPixels.argtypes = [c_int, c_int, c_int, c_int, c_uint, c_uint, ctypes.c_void_p]

                im = np.ones((height, width, 4), dtype=np.ubyte)
                windll.opengl32.glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE,
                                             ctypes.c_void_p(im.ctypes.data))

                self.result.append(im)

                self.render_count_left -= 1

                if not self.render_count_left:
                    self.done = True
                    windll.user32.DestroyWindow(hWnd)
                else:
                    # render once more
                    windll.user32.InvalidateRect(hWnd, win32con.NULL, win32con.NULL)

            else:
                windll.user32.DefWindowProcW.restype = ctypes.c_long
                windll.user32.DefWindowProcW.argtypes = [HWND, c_uint, WPARAM, LPARAM]
                return windll.user32.DefWindowProcW(hWnd, Msg, wParam, lParam)
            return 0

        def render(self, testee, render_count=1):
            self.render_count_left = render_count
            self.done = False
            self.error = None

            self.testee = testee

            self.result = []

            WS_OVERLAPPEDWINDOW = 0xcf0000
            WS_VISIBLE = 0x10000000

            style = WS_OVERLAPPEDWINDOW | WS_VISIBLE

            rect = RECT()
            rect.left = 0
            rect.top = 0
            rect.right = 640
            rect.bottom = 480
            assert windll.user32.AdjustWindowRect(rect, style, False, 0)

            hwnd = windll.user32.CreateWindowExW(
                0,
                self.wc.lpszClassName,
                "viewportdraw",
                style,
                0, 0, rect.right - rect.left, rect.bottom - rect.top,
                None, None, self.hinstance, None)

            assert hwnd, ctypes.GetLastError()

            # windll.user32.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)

            msg = MSG()
            pMsg = pointer(msg)

            while not self.done:
                if windll.user32.PeekMessageW(pMsg, win32con.NULL, 0, 0, win32con.PM_REMOVE):
                    windll.user32.TranslateMessage(pMsg)
                    windll.user32.DispatchMessageW(pMsg)
            assert not self.error, self.error
            print('done')
            return self.result


    @pytest.fixture(scope="module")
    def window_renderer():
        return WindowRendererFixture()

    def make_nice_gradient(width, height):
        im = np.ones((height, width, 4), dtype=np.float32)
        # im[:,:,2] = np.sin(10*np.pi*(t+np.linspace(0, 1, region.height, dtype=np.float32)))[:, np.newaxis]
        im[:, :, 0] = np.linspace(0, 1, height, dtype=np.float32)[:, np.newaxis]
        im[:, :, 1] = np.linspace(0, 1, width, dtype=np.float32)[np.newaxis, :]
        return im

    def test_render_image(window_renderer):
        images = []

        def render(width, height):
            im = make_nice_gradient(width, height)
            im = np.flipud(im)

            images.append(im)

            draw_image(im.copy(), (width, height))

        actual = window_renderer.render(render)[0] / 255.0
        expected = images[0]

        check_images(actual, expected)

    def test_render_image_scaled(window_renderer):
        images = []

        def render(width, height):
            width_src, height_src = width // 2, height // 2

            im = make_nice_gradient(width_src, height_src)
            images.append(im)

            # copy() to pass contiguous image
            draw_image(im.copy(), (width, height))

        def fast_downsample_by_2(image):
            return image[:image.shape[0] - (image.shape[0] % 2):2, :image.shape[1] - (image.shape[1] % 2):2]

        actual = fast_downsample_by_2(window_renderer.render(render)[0]) / 255.0
        expected = images[0]

        check_images(actual, expected)

    def test_render_image_tiled(window_renderer):

        images = []

        def render(width, height):
            im = make_nice_gradient(width, height)
            # copy() to pass gontiguous image
            im = np.flipud(im)

            images.append(im)

            draw_image(im.copy(), (width, height), tile=(5, 5))

        actual = window_renderer.render(render)[0] / 255.0
        expected = np.tile(images[0][::5, ::5, ...], (5, 5, 1))

        check_images(actual, expected)

    def test_render_image_tiled_non_int(window_renderer):

        images = []

        def render(width, height):
            im = make_nice_gradient(width, height)
            im = np.flipud(im)

            images.append(im)

            draw_image(im.copy(), (width, height), tile=(2, 2))

        actual = window_renderer.render(render)[0] / 255.0
        expected = np.tile(images[0][::2, ::2, ...], (2, 2, 1))
        expected = np.roll(expected, expected.shape[0] // 4, axis=0)
        expected = np.roll(expected, expected.shape[1] // 4, axis=1)

        check_images(actual, expected)

    def test_render_image_update(window_renderer):
        images = []
        textures = []

        def render(width, height):

            im = make_nice_gradient(width, height)

            # use different images for first and concequent calls
            if not images:
                im = np.flipud(im)

            images.append(im)

            if not textures:
                textures.append(viewportdraw.create_texture(im.copy()))
                texture = textures[0]
            else:
                texture = textures[0]
                texture.update(im.copy())

            viewportdraw.draw_image_texture(texture, (width, height), (1, 1))

        actuals = window_renderer.render(render, 2)

        check_images(actuals[0] / 255.0, images[0])
        check_images(actuals[1] / 255.0, images[1])

    def check_images(actual, expected):
        try:
            rprtesting.assert_images_similar(expected, actual, max_std_dev=0.01)
        except AssertionError:
            imageio.imwrite('expected.png', expected)
            imageio.imwrite('actual.png', actual)
            raise
