param (
    [string]$BlendFilesSubdir,
    [string]$GroundTruthSubdir,
    [string]$BlenderSubdir,
    [string]$Scene,
    # default viewport flag to 0
    [int]$ViewportFlag = 0
)

$env:BLENDER_EXE = $BlenderSubdir

$env:RPR_BLENDER_DEBUG = "1"

$CmdRenderScript = "cmd_render.py"

# Define the command to run final render
$FinalRenderCommand = @(
    "python3.11", $CmdRenderScript,
    "--blender-path", $BlenderSubdir,
    "--script-path", "final_render.py",
    "--scene-path", $BlendFilesSubdir,
    "--scene-name", $Scene
)

# Define the command to run viewport render
$ViewportRenderCommand = @(
    "python3.11", $CmdRenderScript,
    "--blender-path", $BlenderSubdir,
    "--script-path", "viewport_render.py",
    "--scene-path", $BlendFilesSubdir,
    "--scene-name", $Scene
)

# Define the command to run image comparison
$CompareCommand = @(
    "python3.11", "compare_render.py",
    "--output-dir", $Scene,
    "--scene-name", $Scene
)

# Run final render
Write-Output "Running final render..."
& "python3.11" @($CmdRenderScript, "--blender-path", $BlenderSubdir, "--script-path", "final_render.py", "--scene-path", $BlendFilesSubdir, "--scene-name", $Scene)

# Run image comparison
Write-Output "Comparing images..."
& "python" @("compare_render.py", "--output-dir", $Scene, "--scene-name", $Scene)

# Run viewport render
Write-Output "Running viewport render..."
& "python3.11" @($CmdRenderScript, "--blender-path", $BlenderSubdir, "--script-path", "viewport_render.py", "--scene-path", $BlendFilesSubdir, "--scene-name", $Scene, "--viewport-flag", $ViewportFlag)
