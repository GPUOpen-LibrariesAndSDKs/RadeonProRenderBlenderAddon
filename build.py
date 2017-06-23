#!python3

import sys
import os
import platform
import subprocess
from pathlib import Path
import shutil


arch = platform.architecture()

assert '64bit' == arch[0] and (('Windows' in arch[1]) or ('ELF' in arch[1])), arch

pyrpr_path = Path('src/bindings/pyrpr')

cwd = os.getcwd()
os.chdir(str(pyrpr_path))
pyrpr_build_dir = Path('.build')

if Path('.build').exists():
    shutil.rmtree(str(pyrpr_build_dir))

subprocess.check_call([sys.executable, 'rpr.py'])
subprocess.check_call([sys.executable, 'rpr_load_store.py'])
os.chdir(cwd)

os.chdir('RPRBlenderHelper')
os.makedirs('.build', exist_ok=True)
os.chdir('.build')
if 'Windows' == platform.system():
    subprocess.check_call(['cmake', '-G', 'Visual Studio 14 2015 Win64',  '..'])
else:
    subprocess.check_call(['cmake', '..'])
subprocess.check_call(['cmake', '--build',  '.', '--config', 'Release', '--clean-first'])
