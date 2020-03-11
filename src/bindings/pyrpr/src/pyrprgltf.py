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
import functools
import platform
import traceback
import inspect
import ctypes
import os
import sys
import gltfwrap
from gltfwrap import *

import pyrpr

lib_wrapped_log_calls = False


class _init_data:
    _log_fun = None


def init(log_fun, rprsdk_bin_path):

    _module = __import__(__name__)

    _init_data._log_fun = log_fun
    
    lib_platform = ""
    rel_path = "../../../RadeonProRender-GLTF"
    if "Windows" == platform.system():
        lib_name = 'ProRenderGLTF.dll'
        lib_platform = "Win/lib"
    elif "Linux" == platform.system():
        lib_name = 'libProRenderGLTF.so'
        lib_platform = "Linux-Ubuntu/lib"
    elif "Darwin" == platform.system():
        lib_name = "libProRenderGLTF.dylib"
        lib_platform = "Mac/lib"
    else:
        assert False

    import __gltf

    try:
        lib = __gltf.lib
    except AttributeError:
        lib_path = str(rprsdk_bin_path/lib_name)
        if not os.path.isfile(lib_path):
            lib_path = str(rprsdk_bin_path / rel_path / lib_platform / lib_name )
        lib = __gltf.ffi.dlopen(lib_path)

    gltfwrap.lib = lib
    gltfwrap.ffi = __gltf.ffi
    global ffi
    ffi = __gltf.ffi

    for name in gltfwrap._functions_names:

        wrapped = getattr(gltfwrap, name)

        if lib_wrapped_log_calls:
            wrapped = pyrpr.wrap_core_log_call(wrapped, log_fun, 'gltf')
        wrapped = pyrpr.wrap_core_check_success(wrapped, 'gltf')
        setattr(_module, name, wrapped)
    del _module 

class Object:

    core_type_name = 'void*'

    def __init__(self, core_type_name=None):
        self.ffi_type_name = (core_type_name if core_type_name is not None else self.core_type_name) + '*'
        self._reset_handle()

    def __init__(self, core_type_name, obj):
        self.ffi_type_name = (core_type_name if core_type_name is not None else self.core_type_name) + '*'
        self._handle_ptr = ffi.cast(self.ffi_type_name, obj._handle_ptr)

    def _reset_handle(self):
        self._handle_ptr = ffi.new(self.ffi_type_name, ffi.NULL)

    def _get_handle(self):
        return self._handle_ptr[0]

class ArrayObject:
    def __init__(self, core_type_name, init_data):
        self._handle_ptr = ffi.new(core_type_name, init_data)

    def __del__(self):
        del self._handle_ptr
