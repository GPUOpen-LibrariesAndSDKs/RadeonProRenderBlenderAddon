import sys
import os
import platform
import time
import subprocess
from pathlib import Path

time_start = time.time()

blender_exe = sys.argv[1]
script_py = sys.argv[2]

# Note: Only the OSX run script sets the debugger from the command line currently
debugger = sys.argv[3] if len(sys.argv) >= 4 else None

# getting Blender python exe and running blender_pip.py
python_search = {
    'Windows': "2.8*/python/bin/python.exe",
    'Linux': "2.8*/python/bin/python3.*",
    'Darwin': "../Resources/2.8*/python/bin/python3.*"
}[platform.system()]
blender_python_exe = next(Path(blender_exe).parent.glob(python_search))

print(f"Using Blender Python executable '{blender_python_exe}'")

subprocess.check_call([str(blender_python_exe), 'cmd_tools/blender_pip.py'])

# Running Blender
call_args = [
    blender_exe,
    # '--factory-startup',
    '-noaudio',
    '--window-geometry', '200', '600', '1920', '1080',
    '--python', script_py
]

if debugger:
    print("Debugger: %s" % debugger)
    call_args.insert(0, debugger)

subprocess.check_call(call_args)

print('done in', time.time() - time_start)
