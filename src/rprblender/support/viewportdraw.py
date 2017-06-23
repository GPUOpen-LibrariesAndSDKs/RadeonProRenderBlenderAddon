#!python3

import ctypes
import sys
from enum import Enum

import numpy as np
from ctypes import cdll

GL_RGBA = 0x1908
GL_FLOAT = 0x1406

if sys.platform == 'linux':
    gl = cdll.LoadLibrary('libGL.so')
else:
    gl = ctypes.windll.opengl32

glGetError = gl.glGetError

glPixelZoom = gl.glPixelZoom
glPixelZoom.argtypes = [ctypes.c_float, ctypes.c_float]

glRasterPos2f = gl.glRasterPos2f
glRasterPos2f.argtypes = [ctypes.c_float, ctypes.c_float]

glDrawPixels = gl.glDrawPixels
glDrawPixels.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]

GL_MODELVIEW = 0x1700
GL_PROJECTION = 0x1701
GL_TEXTURE = 0x1702

GL_LIGHTING = 0x0B50
GL_TEXTURE_2D = 0x0DE1

GL_TEXTURE_MAG_FILTER = 0x2800
GL_TEXTURE_MIN_FILTER = 0x2801
GL_TEXTURE_WRAP_S = 0x2802
GL_TEXTURE_WRAP_T = 0x2803

GL_CLAMP = 0x2900
GL_REPEAT = 0x2901

GL_NEAREST = 0x2600
GL_LINEAR = 0x2601

GL_QUADS = 0x0007


class _types:
    GLenum = ctypes.c_uint
    GLuint = ctypes.c_uint
    GLint = ctypes.c_int
    GLsizei = ctypes.c_int
    GLvoid = ctypes.c_void_p
    GLfloat = ctypes.c_float
    GLdouble = ctypes.c_double

gl.glGenTextures.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)]
gl.glDeleteTextures.argtypes = [_types.GLsizei, ctypes.POINTER(_types.GLuint)]

gl.glBindTexture.argtypes = [_types.GLenum, _types.GLuint]
gl.glTexParameteriv.argtypes = [_types.GLenum, _types.GLenum, ctypes.POINTER(_types.GLint)]
gl.glMatrixMode.argtypes = [_types.GLenum]
gl.glColor3f.argtypes = [_types.GLfloat]*3
gl.glColor3fv.argtypes = [ctypes.POINTER(_types.GLfloat)]
gl.glTexCoord2f.argtypes = [_types.GLfloat]*2
gl.glVertex3f.argtypes = [_types.GLfloat]*3

gl.glOrtho.argtypes = [_types.GLdouble, _types.GLdouble, _types.GLdouble, _types.GLdouble,
                       _types.GLdouble, _types.GLdouble]

gl.glTexParameteriv.argtypes = [
    _types.GLenum, _types.GLint, _types.GLint, _types.GLsizei, _types.GLsizei, _types.GLint,
    _types.GLenum, _types.GLenum, _types.GLvoid]

gl.glEnable.argtypes = [_types.GLenum]
gl.glDisable.argtypes = [_types.GLenum]


def draw_image_pixels(im, viewport_size, tile=(1, 1)):
    image_width, image_height = im.shape[1], im.shape[0]

    scale = 1.0/np.array(tile, dtype=np.float32)

    im = im.flatten()# have image data in continuous piece of memory

    for row in range(tile[1]):
        for col in range(tile[0]):
            glRasterPos2f(col*viewport_size[0]*scale[0], row*viewport_size[1]*scale[1])
            assert not glGetError()

            glPixelZoom(viewport_size[0]*scale[0]/image_width, viewport_size[1]*scale[1]/image_height)
            assert not glGetError()

            glDrawPixels(image_width, image_height, GL_RGBA, GL_FLOAT, ctypes.c_void_p(im.ctypes.data))
            assert not glGetError()


def draw_image_texture(texture, viewport_size, tile=(1, 1)):

    scale = 1.0/np.array(tile, dtype=np.float32)

    gl.glMatrixMode(GL_PROJECTION)
    gl.glPushMatrix()
    gl.glLoadIdentity()
    gl.glOrtho(0.0, viewport_size[0], 0.0, viewport_size[1], -1.0, 1.0)
    gl.glMatrixMode(GL_MODELVIEW)
    gl.glPushMatrix()

    gl.glLoadIdentity()
    gl.glDisable(GL_LIGHTING)

    gl.glColor3f(1,1,1)
    gl.glEnable(GL_TEXTURE_2D)
    gl.glBindTexture(GL_TEXTURE_2D, texture.name)

    gl.glBegin(GL_QUADS)
    uv = [[-(tile[0]-1)*0.5, -(tile[1]-tile[1]/tile[0])*0.5],
          [(tile[0]+1)*0.5, (tile[1]+tile[1]/tile[0])*0.5]]
    gl.glTexCoord2f(uv[0][0], uv[0][1]); gl.glVertex3f(-0.5, -0.5, 0)
    gl.glTexCoord2f(uv[0][0], uv[1][1]); gl.glVertex3f(-0.5, viewport_size[1], 0)
    gl.glTexCoord2f(uv[1][0], uv[1][1]); gl.glVertex3f(viewport_size[0], viewport_size[1], 0)
    gl.glTexCoord2f(uv[1][0], uv[0][1]); gl.glVertex3f(viewport_size[0], -0.5, 0)
    gl.glEnd()

    gl.glDisable(GL_TEXTURE_2D)
    gl.glPopMatrix()

    gl.glMatrixMode(GL_PROJECTION)
    gl.glPopMatrix()

    gl.glMatrixMode(GL_MODELVIEW)


class Texture:

    def __init__(self, name, size):
        self.name = name
        self.size = size

    def __del__(self):
        gl.glDeleteTextures(1, self.name)

    def update(self, im):
        size = im.shape[1], im.shape[0]
        image_width, image_height = size

        gl.glBindTexture(GL_TEXTURE_2D, self.name)
        if size != self.size:
            gl.glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image_width, image_height, 0, GL_RGBA, GL_FLOAT,
                            ctypes.c_void_p(im.ctypes.data))
            assert not glGetError()
            self.size = size
        else:
            gl.glTexSubImage2D(GL_TEXTURE_2D, 0,
                               0, 0, image_width, image_height,
                               GL_RGBA, GL_FLOAT, ctypes.c_void_p(im.ctypes.data))
            assert not glGetError()


def create_texture(im):
    assert im.flags['C_CONTIGUOUS']
    image_width, image_height = im.shape[1], im.shape[0]
    m_name = ctypes.c_uint()
    gl.glGenTextures(1, ctypes.byref(m_name))
    gl.glBindTexture(GL_TEXTURE_2D, m_name)
    gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
    gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    gl.glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image_width, image_height, 0, GL_RGBA, GL_FLOAT,
                    ctypes.c_void_p(im.ctypes.data))
    return Texture(m_name, (image_width, image_height))
