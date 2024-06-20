#!/bin/bash

BLENDER_EXE="$1"
BLEND_FILES_SUBDIR="$2"
GROUND_TRUTH_SUBDIR="$3"
SCRIPT_DIR=$(pwd)

clear

# # Install required modules
# pip3 show scikit-image &>/dev/null || pip3 install scikit-image

clear

echo "USING BLENDER: $BLENDER_EXE"
echo "BLEND FILES IN: $BLEND_FILES_SUBDIR"
echo "COMPARING WITH: $GROUND_TRUTH_SUBDIR"

# Check if Blender executable exists
if [[ ! -f "$BLENDER_EXE" ]]; then
    echo "Blender executable not found: $BLENDER_EXE"
    exit 1
fi

# Check if Blender files directory exists
if [[ ! -d "$BLEND_FILES_SUBDIR" ]]; then
    echo "Blender files directory not found: $BLEND_FILES_SUBDIR"
    exit 1
fi

# List all .blend files in the specified directory
for blend_file in "$BLEND_FILES_SUBDIR"/*.blend; 
do
    # Check if the blend file exists
    if [[ -f "$blend_file" ]]; then
        stripped_file=$(basename "$blend_file")
        SCENE="${stripped_file%.blend}"
        echo "Processing scene: $SCENE"
        echo "Blend file: $blend_file"

        # Generate render for this scene using Python script
        python3 cmd_script.py --blender-path "$BLENDER_EXE" --scene-path "$BLEND_FILES_SUBDIR" --scene-name "$SCENE"

        # Set RENDER_SUBDIR to the same as SCENE
        RENDER_SUBDIR="$SCENE"

        # Compare generated render with ground truth/actual
        python3 compare_render.py --scene "$SCENE" --ground_truth "$GROUND_TRUTH_SUBDIR" --render "$RENDER_SUBDIR"
    else
        echo "Blend file not found: $blend_file"
    fi
done
