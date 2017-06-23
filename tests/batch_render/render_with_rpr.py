import os
import subprocess
from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-a', '--addon-installed', action='store_true')
parser.add_argument('-f', '--file', default=None)
parser.add_argument('-s', '--scene', default=None)
parser.add_argument('--dry-run', action='store_true')
parser.add_argument('blenderargs', nargs='*')

args = parser.parse_args()

cmd = [os.environ['BLENDER_EXE']]

if not args.addon_installed:
    cmd.append('--python')
    cmd.append(str(Path(__file__).parents[2]/'src/tools/load_addon.py'))
    
if args.file:
    cmd.append(args.file)

if args.scene:
    cmd += ['--scene', args.scene]


cmd += ['--engine', 'RPR']
cmd += ['--render-output', '//render_output']
cmd += ['--render-frame', '1']
cmd += ['--background']  # no blender ui
cmd += args.blenderargs 

print(cmd)
print(' '.join(p if ' ' not in p else '"%s"'%p for p in cmd))
if not args.dry_run:
    subprocess.check_call(cmd)
