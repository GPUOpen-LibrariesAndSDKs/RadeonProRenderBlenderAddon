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
from cffi import FFI
from pathlib import Path

ffi = FFI()

ffi.set_source("_pyrpr_load_store", None)

ffi.cdef("""
    int rprsExport(char const * rprsFileName, void * context, void * scene,
                    int extraCustomParam_int_number, char const * * extraCustomParam_int_names,
                    int const * extraCustomParam_int_values, int extraCustomParam_float_number,
                    char const * * extraCustomParam_float_names, float const * extraCustomParam_float_values, unsigned int exportFlags);""")

if __name__ == "__main__":

    build_dir = Path(__file__).parent / '.build'

    ffi.compile(tmpdir=str(build_dir), verbose=True)
