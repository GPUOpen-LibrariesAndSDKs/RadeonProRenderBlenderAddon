import sys
import os
import time
import subprocess

time_start = time.time()

# check files existence
blender_exe = sys.argv[1]
if not os.path.isfile(blender_exe):
    print(f"Wrong or empty blender.exe executable file path: {blender_exe}")
    exit(1)

script_py = sys.argv[2]
if not os.path.isfile(script_py):
    print(f"Wrong or empty Python script file path: {script_py}")
    exit(1)

# Note: Only the OSX run script sets the debugger from the command line currently
debugger = sys.argv[3] if len(sys.argv) >= 4 else None

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
