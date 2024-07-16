
param (
    [string]$BlendFilesSubdir,
    [string]$GroundTruthSubdir,
    [string]$BlenderSubdir,
    [string]$Scene,
    [string]$ViewportFlag
)

# Set the BLENDER_EXE environment variable
$env:BLENDER_EXE = $BlenderSubdir

# Set RPR_BLENDER_DEBUG environment variable
$env:RPR_BLENDER_DEBUG = "1"

# Define paths to the Python script that runs the Blender rendering
$CmdRenderScript = "cmd_render.py"

# Define the command to run final render
$FinalRenderCommand = @(
    "python", $CmdRenderScript,
    "--blender-path", $BlenderSubdir,
    "--script-path", "final_render.py",
    "--scene-path", $BlendFilesSubdir,
    "--scene-name", $Scene)

# Define the command to run viewport render
$ViewportRenderCommand = @(
    "python", $CmdRenderScript,
    "--blender-path", $BlenderSubdir,
    "--script-path", "viewport_render.py",
    "--scene-path", $BlendFilesSubdir,
    "--scene-name", $
    "--viewport-flag", $ViewportFlag
)

# Define the command to run image comparison
# $CompareCommand = @(
#     "python", "compare_render.py",
#     "--output-dir", $Scene,
#     "--scene-name", $Scene
# )

# Run final render
Write-Output "Running final render..."
& "python" $CmdRenderScript --blender-path $BlenderSubdir --script-path "final_render.py" --scene-path $BlendFilesSubdir --scene-name $Scene 

# Run image comparison
Write-Output "Comparing images..."
& "python" ".\compare_render.py" --output-dir $Scene --scene-name $Scene

# Run viewport render
Write-Output "Running viewport render..."
& "python" $CmdRenderScript --blender-path $BlenderSubdir --script-path "viewport_render.py" --scene-path $BlendFilesSubdir --scene-name $Scene --viewport-flag $ViewportFlag
