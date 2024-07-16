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

# from pathlib import Path

# src_path = str((Path(__file__).parent.parent/'src').resolve())

# import sys
# if src_path not in sys.path:
#     sys.path.append(src_path)

# import rprblender

# rprblender.register()

# import bpy
# bpy.context.scene.render.engine = 'RPR'

from pathlib import Path
import sys
import os

# Resolve paths
script_dir = Path(__file__).parent
base_src_path = (script_dir / '..' / 'src').resolve()
rprblender_path = (base_src_path / 'rprblender').resolve()
pyrpr_path = (base_src_path / 'bindings' / 'pyrpr').resolve()

# Append paths to sys.path if not already present
if str(base_src_path) not in sys.path:
    sys.path.append(str(base_src_path))
if str(rprblender_path) not in sys.path:
    sys.path.append(str(rprblender_path))
if str(pyrpr_path) not in sys.path:
    sys.path.append(str(pyrpr_path))

# # Print paths for debugging purposes
# print(f"BASE SRC PATH: {base_src_path}")
# print(f"RPRBLENDER PATH: {rprblender_path}")
# print(f"PYRPRWRAP PATH: {pyrprwrap_path}")
# print(f"sys.path: {sys.path}")

# Import modules
try:
    # import pyrprwrap  # Import pyrprwrap explicitly to check its availability
    # print("pyrprwrap imported successfully")

    import rprblender
    rprblender.register()
    print("rprblender addon registered successfully.")
except ImportError as e:
    print(f"Error importing module: {e}")
except Exception as e:
    print(f"Error registering rprblender: {e}")

import bpy
bpy.context.scene.render.engine = 'RPR'
