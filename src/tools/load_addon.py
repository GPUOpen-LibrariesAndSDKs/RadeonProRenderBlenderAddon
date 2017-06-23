
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
