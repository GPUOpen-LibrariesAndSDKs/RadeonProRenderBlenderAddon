import sys
import os
import subprocess

cwd = os.getcwd()

print('running support tests:')
os.chdir('src/rprblender/support')
subprocess.check_call([sys.executable, '-m', 'pytest'])
os.chdir(cwd)

print('running pyrpr tests:')
os.chdir('src/bindings/pyrpr')
subprocess.check_call([sys.executable, '-m', 'pytest'])
os.chdir(cwd)

print('running addon tests:')
subprocess.check_call([sys.executable, 'tests/blender_tests/run_all_tests.py', 'src/rprblender', '--', '-v'])

