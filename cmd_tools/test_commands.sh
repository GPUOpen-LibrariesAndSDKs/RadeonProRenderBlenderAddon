# IN WSL
cd /mnt/c/Users/Spencer_Au_AMD/Documents/GitHub/rpr_testscript
./test_script.sh "/mnt/c/Program Files/Blender Foundation/Blender 4.0/blender.exe" blender_files ground_truth

# in windows
python cmd_script.py --blender-path "C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe" --scene-path "blender_files" --scene-name "RPR_BMW"
.\test_script.ps1 -BlenderExe "C:\Program Files\Blender Foundation\Blender 4.0\blender.exe" -BlendFilesSubdir "blender_files" -GroundTruthSubdir "ground_truth"         