#!python3

import sys
import os

from pathlib import Path

local_dir = str(Path(__file__).parent)

if local_dir not in sys.path:
    sys.path.insert(0, local_dir)

rprsdk_path = Path(Path(__file__).parent.parent.parent/'ThirdParty/RadeonProRender SDK/Win')
os.environ['PATH'] = str(rprsdk_path/'bin')+os.pathsep+os.environ['PATH']

import rpr
print(dir(rpr))
print(rpr.createContext())
