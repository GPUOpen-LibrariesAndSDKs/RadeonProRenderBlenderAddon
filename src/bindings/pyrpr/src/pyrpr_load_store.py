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
from _pyrpr_load_store import ffi
import pyrpr

lib = None


def init(lib_dir):
    global lib

    lib_name = {
        'Windows': "RprLoadStore64.dll",
        'Linux': "libRprLoadStore64.so",
        'Darwin': "libRprLoadStore64.dylib"
    }[platform.system()]

    lib = ffi.dlopen(str(lib_dir / lib_name))


def export(name, context, scene, flags):
    # last param defines export bit flags.
    # image handling type flags:
    # RPRLOADSTORE_EXPORTFLAG_EXTERNALFILES (1 << 0) - image data will be stored to rprsb external file
    # RPRLOADSTORE_EXPORTFLAG_COMPRESS_IMAGE_LEVEL_1 (1 << 1) - image data will be lossless compressed during export
    # RPRLOADSTORE_EXPORTFLAG_COMPRESS_IMAGE_LEVEL_2 (1 << 2) - image data will be lossy compressed during export
    #  note: without any of above flags images will not be exported.
    return lib.rprsExport(pyrpr.encode(name), context._get_handle(), scene._get_handle(),
                          0, ffi.NULL, ffi.NULL, 0, ffi.NULL, ffi.NULL, flags, ffi.NULL)
