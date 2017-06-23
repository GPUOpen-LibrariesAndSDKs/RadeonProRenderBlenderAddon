#!python3

import sys
import os
import subprocess
import time
import site
        
from pathlib import Path


import argparse

blender_exe = os.environ.get('BLENDER_EXE', None)

parser = argparse.ArgumentParser()

parser.add_argument('--blender-exe', required=blender_exe is None, default=blender_exe, help='path to blender exucutable to use to run tests')
parser.add_argument('--keep-blender-running', action='store_true', help='do not include exit directive to test to keep blender app running after test completes')
parser.add_argument('--profile', action='store_true', help='run with python profiler')
parser.add_argument('--pythonpath', nargs='*', help='extra paths to add to PYTHONPATH for blender python to find packages(e.g. pytest)')
parser.add_argument('--single-blender-instance', action='store_true', help='run all tests in a single blender instance')
parser.add_argument('--no-single-blender-instance', action='store_false', dest='single_blender_instance', help='run everytest in a separate blender instance')
parser.add_argument('pytestargs', nargs='*', help='args to pass to pytest - http://doc.pytest.org/en/latest/usage.html')
parser.set_defaults(single_blender_instance=True)

args = parser.parse_args()

if not args.pytestargs:
    parser.print_help()
    print("Error: Pass desired tests as positional arguments and extra pytest args after '--'(double dash)")
    sys.exit(-1)

blender_exe = args.blender_exe
assert Path(blender_exe).is_file(), 'blender exe path provided is not a file: %' % blender_exe

if args.pythonpath:
    pythonpath = args.pythonpath 
    
else:
    # use best guess to add pytest location
    import pytest
    pythonpath = [str(Path(pytest.__file__).parent)]


pythonpath = [str(Path(__file__).parents[2]/'src')] + list(pythonpath)+['/usr/lib/python3/dist-packages']

root = Path(__file__).parent.parent.parent

def run_test(pytestargs):

    print(pytestargs)

    run_script = str(Path(__file__).parent/'run_script.py')

    keep_blender_running = args.keep_blender_running
    profile = args.profile

    with open(run_script, 'w') as f:
        print("""

import sys
import cProfile

sys.path.extend({pythonpath!r})

import rprblender
rprblender.register()

import rprblender.testing

rprblender.testing.run_all_tests({pytestargs}, {keep_blender_running})
""".format(
            keep_blender_running=keep_blender_running,
            addon_script_fpath=repr(str(root/'src/tools/load_addon.py')),
            pytestargs=repr(pytestargs),
            profile=repr(profile),
            pythonpath=pythonpath
    ),
file=f)
    time_start = time.time()

    cmd = [blender_exe,
        '--factory-startup',
        '-noaudio',
        '--background' if not keep_blender_running else '',
        '--python', run_script]

    print(cmd)
    ret = subprocess.call(cmd)
    if ret:
        print('FAILED')
        sys.exit(-1)
                                 
    print('done in', time.time()-time_start)

time_start = time.time()
print('tests root:', root)

run_test(args.pytestargs)

print('done all tests in', time.time()-time_start)

print('SUCCESS!')
