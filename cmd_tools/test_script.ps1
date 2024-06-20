param(
    [string]$BlenderExe,
    [string]$BlendFilesSubdir,
    [string]$GroundTruthSubdir
)

Clear-Host

# Install required skimage module if not already installed
if (-Not (pip show scikit-image)) {
    pip install scikit-image
}

Clear-Host

Write-Output "USING BLENDER: $BlenderExe"
Write-Output "BLEND FILES IN: $BlendFilesSubdir"
Write-Output "COMPARING WITH: $GroundTruthSubdir"

# Check if Blender executable exists
if (-Not (Test-Path $BlenderExe)) {
    Write-Output "Blender executable not found: $BlenderExe"
    exit 1
}

# Check if Blender files directory exists
if (-Not (Test-Path $BlendFilesSubdir)) {
    Write-Output "Blender files directory not found: $BlendFilesSubdir"
    exit 1
}

# List all .blend files in the specified directory
$blendFiles = Get-ChildItem "$BlendFilesSubdir\*.blend"
foreach ($blendFile in $blendFiles) {
    $scene = [System.IO.Path]::GetFileNameWithoutExtension($blendFile)
    Write-Output "Processing scene: $scene"
    Write-Output "Blend file: $blendFile"

    # Generate render for this scene using Python script
    python cmd_script.py --blender-path "$BlenderExe" --scene-path "$BlendFilesSubdir" --scene-name "$scene"

    # Set RENDER_SUBDIR to the same as SCENE
    #$RenderSubdir = $scene

    # Compare generated render with ground truth/actual
    #python compare_render.py --scene "$scene" --ground_truth "$GroundTruthSubdir" --render "$RenderSubdir"
}
