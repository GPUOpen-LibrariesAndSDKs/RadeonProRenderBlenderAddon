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
import numpy as np
import gpu

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

    def __init__(self):
        self.image = None
        self.texture = None

    def _create(self):
        height, width, channels = self.image.shape
        pixels = gpu.types.Buffer('FLOAT', width * height * 4, self.image)
        self.texture = gpu.types.GPUTexture((width, height), format='RGBA16F', data=pixels)


    def clear(self):
        if self.image is not None:
            self._delete()

    def _delete(self):
        self.texture = None
        self.image = None

    def set_image(self, image: np.array):
        if self.image is image:
            return

        if self.image is None:
            self.image = image
            self._create()
        elif self.image.shape != image.shape:
            self._delete()
            self.image = image
            self._create()
        else:
            self.image = image
