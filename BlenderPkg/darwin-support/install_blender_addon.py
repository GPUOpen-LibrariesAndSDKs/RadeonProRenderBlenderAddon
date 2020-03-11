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
import bpy
from pathlib import Path

bpy.ops.preferences.addon_install(overwrite=True, filepath=r'/Users/Shared/RadeonProRender/Blender/addon/addon.zip')
bpy.ops.preferences.addon_enable(module='rprblender')
bpy.ops.wm.save_userpref()

