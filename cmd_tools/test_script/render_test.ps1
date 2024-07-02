param (
    [string]$BlendFilesSubdir,
    [string]$GroundTruthSubdir,
    [string]$BlenderSubdir,
    [string]$Scene,
    [string]$ViewportFlag,
    [string]$AddonPath
)

# Define paths to the Python script that runs the Blender rendering
$CmdRenderScript = "cmd_render.py"

# Download the addon ZIP if AddonZipUrl is provided
if ($AddonZipUrl) {
    $AddonZipPath = Join-Path $AddonPath "addon.zip"
    Invoke-WebRequest -Uri $AddonZipUrl -OutFile $AddonZipPath
    Expand-Archive -Path $AddonZipPath -DestinationPath $AddonPath
}

# Define the command to run final render
$FinalRenderCommand = @(
    "python", $CmdRenderScript,
    "--blender-path", $BlenderSubdir,
    "--script-path", "final_render.py",
    "--scene-path", $BlendFilesSubdir,
    "--scene-name", $Scene,
    "--addon-path", $AddonPath
)

# Define the command to run image comparison
$CompareCommand = @(
    "python", "compare_render.py",
    "--output-dir", $Scene,
    "--scene-name", $Scene
)

# Run final render
Write-Output "Running final render..."
& "python" $CmdRenderScript --blender-path $BlenderSubdir --script-path "final_render.py" --scene-path $BlendFilesSubdir --scene-name $Scene --addon-path $AddonPath

# Run image comparison
Write-Output "Comparing images..."
& "python" "compare_render.py" --output-dir $Scene --scene-name $Scene

# Conditionally run viewport render based on the viewport flag
if ($ViewportFlag -eq "1") {
    Write-Output "Running viewport render..."
    & "python" $CmdRenderScript --blender-path $BlenderSubdir --script-path "viewport_render.py" --scene-path $BlendFilesSubdir --scene-name $Scene --viewport-flag $ViewportFlag --addon-path $AddonPath
} else {
    Write-Output "Skipping viewport render..."
}

# .\render_test.ps1 -BlendFilesSubdir "blender_files" -GroundTruthSubdir "ground_truth" -BlenderSubdir "C:\\Program Files\\Blender Foundation\\Blender 4.1\\blender.exe" -Scene "RPR_BMW" -ViewportFlag 1 -AddonPath \\rprnas\Shared\build\rprbuilds\rprblender\win
