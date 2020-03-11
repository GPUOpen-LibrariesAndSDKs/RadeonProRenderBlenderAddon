#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
import platform
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


class GLTexture:
    channels = 4

    def __init__(self, width, height):
        self.width = width
        self.height = height

        textures = bgl.Buffer(bgl.GL_INT, [1,])
        bgl.glGenTextures(1, textures)
        self.texture_id = textures[0]

        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.texture_id)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_S, bgl.GL_REPEAT)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_T, bgl.GL_REPEAT)

        bgl.glTexImage2D(
            bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA if platform.system() == 'Darwin' else bgl.GL_RGBA16F,
            self.width, self.height, 0,
            bgl.GL_RGBA, bgl.GL_FLOAT,
            bgl.Buffer(bgl.GL_FLOAT, [self.width, self.height, self.channels])
        )

    def __del__(self):
        textures = bgl.Buffer(bgl.GL_INT, [1, ], [self.texture_id, ])
        bgl.glDeleteTextures(1, textures)

    def set_image(self, im: np.array):
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexSubImage2D(
            bgl.GL_TEXTURE_2D, 0,
            0, 0, self.width, self.height,
            bgl.GL_RGBA, bgl.GL_FLOAT,
            ctypes.c_void_p(im.ctypes.data)
        )
