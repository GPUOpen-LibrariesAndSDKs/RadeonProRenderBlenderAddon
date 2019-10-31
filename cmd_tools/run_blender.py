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
blender_python_exe = ''

# The Python 3.8 is planned for use at some point in future.
# TODO: adjust the Python executable names once Python version is changed by Blender.
python_executable_names = {
    # Blender version directory: Win exe, Mac, Ubuntu
    '2.81': ('python.exe', 'python3.7m', 'python3.7m'),
    '2.80': ('python.exe', 'python3.7m', 'python3.7m'),
}

for ver_dir, exec_names in python_executable_names.items():
    if platform.system() == 'Windows':
        blender_python_exe = str(Path(blender_exe).parent / f"{ver_dir}/python/bin/{exec_names[0]}")
    elif platform.system() == 'Darwin':
        blender_python_exe = str(Path(blender_exe).parent / f"../Resources/{ver_dir}/python/bin/{exec_names[1]}")
    else:
        blender_python_exe = str(Path(blender_exe).parent / f"{ver_dir}/python/bin/{exec_names[2]}")

    if os.path.exists(blender_python_exe):
        break

assert blender_python_exe, f"Unable to find Blender Python executable"
print(f"Using Blender Python executable '{blender_python_exe}'")

subprocess.check_call([blender_python_exe, 'cmd_tools/blender_pip.py'])

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
