import numpy as np
import bgl

import ctypes
import sys
from ctypes import cdll


if sys.platform == 'linux':
    gl = cdll.LoadLibrary('libGL.so')
elif sys.platform == 'darwin':
    # ToDo: fix this reference
    gl = cdll.LoadLibrary('/System/Library/Frameworks/OpenGL.framework/Versions/A/Libraries/libGL.dylib')
else:
    gl = ctypes.windll.opengl32


class Texture:
    channels = 4

    def __init__(self, width, height):
        self.width = width
        self.height = height

        textures = bgl.Buffer(bgl.GL_INT, [1,])
        bgl.glGenTextures(1, textures)
        self.gl_texture = textures[0]

        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.gl_texture)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_S, bgl.GL_REPEAT)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_T, bgl.GL_REPEAT)

        #self.buf = bgl.Buffer(bgl.GL_FLOAT, [self.width, self.height, self.channels])
        im = np.zeros((self.width, self.height, self.channels), dtype=np.float32)
        gl.glTexImage2D(
            bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA,
            self.width, self.height,
            0, bgl.GL_RGBA, bgl.GL_FLOAT,
            ctypes.c_void_p(im.ctypes.data)
        )

    def __del__(self):
        textures = bgl.Buffer(bgl.GL_INT, [1, ], [self.gl_texture, ])
        bgl.glDeleteTextures(1, textures)

    def set_image(self, im: np.array):
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.gl_texture)
        gl.glTexSubImage2D(
            bgl.GL_TEXTURE_2D, 0,
            0, 0, self.width, self.height,
            bgl.GL_RGBA, bgl.GL_FLOAT,
            ctypes.c_void_p(im.ctypes.data)
        )
