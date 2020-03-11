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

#script to load addon from within blender text editor

import bpy
import os
import sys

from pathlib import Path

src_path = str(Path(__file__).parent.parent)

import sys
if src_path not in sys.path:
    sys.path.append(src_path)
    import rprblender
else:    
    import rprblender
    rprblender.unregister()    
    import importlib

    import rprblender.properties
    import rprblender.ui
    import rprblender.render
    import rprblender.editor_nodes
    import rprblender.nodes
    import viewportdraw
    
    importlib.reload(rprblender)
    importlib.reload(rprblender.properties)
    importlib.reload(rprblender.ui)
    importlib.reload(rprblender.render)
    importlib.reload(rprblender.editor_nodes)
    importlib.reload(rprblender.nodes)
    importlib.reload(viewportdraw)

rprblender.register()

print('DONE')
