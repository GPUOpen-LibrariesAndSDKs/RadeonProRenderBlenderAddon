
#script to load addon from within blender text editor

import bpy
import os
import sys

import faulthandler

faulthandler.enable()

from pathlib import Path

src_path = str((Path(__file__).parent).resolve())

import sys
if src_path not in sys.path:
    sys.path.append(src_path)

import addon

addon.register()

import bpy
bpy.context.scene.render.engine = 'TEST'

