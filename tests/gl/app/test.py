#!python3

import sys
import os
import ctypes


from pathlib import Path

l = ctypes.cdll.LoadLibrary(str(Path(__file__).parent/'.build/Debug/lib.dll'))
print(l)

l.libfun()
print('draw')
l.libdraw()
print('draw done')


del l
