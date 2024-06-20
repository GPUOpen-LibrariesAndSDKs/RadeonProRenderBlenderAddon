import os
import bpy
import sys
import time
import cv2
import numpy as np
import argparse
from skimage.metrics import structural_similarity as ssim


def create_output_dir(scene_name):
    # Set the path to the output directory based on the scene_name
    output_dir = os.path.abspath(scene_name)
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
        except OSError as e:
            print(f"Failed to create directory {output_dir}: {e}")
            return None
    return output_dir


def render_final_image(output_file):
    # Set the render engine to Radeon ProRender
    bpy.context.scene.render.engine = 'RPR'
    bpy.context.scene.render.filepath = output_file
    bpy.ops.render.render(write_still=True)
    print(f"Final render saved to: {output_file}")


def mse(imageA, imageB):
    err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    err /= float(imageA.shape[0] * imageA.shape[1])
    return err


def compare_images(imageA, imageB):
    mse_value = mse(imageA, imageB)
    ssim_value = ssim(imageA, imageB, win_size=7, multichannel=True, channel_axis=2) # 3 channels for RGB
    return mse_value, ssim_value


def main():
    blend_file = sys.argv[-3]
    scene_name = sys.argv[-2]
    mode = sys.argv[-1]

    if mode == "final":
        # Load the Blender file
        bpy.ops.wm.open_mainfile(filepath=blend_file)
        
        # Create the output directory based on the scene name
        output_dir = create_output_dir(scene_name)
        if not output_dir:
            print("Failed to create output directory. Exiting.")
            return
        
        # Define file names
        final_filename = f"{scene_name}_final.png"
        
        # Define full paths
        final_output_file = os.path.join(output_dir, final_filename)
        
        # Render the final image
        render_final_image(final_output_file)

        # Perform image comparison after rendering
        ground_truth_path = f"ground_truth/{scene_name}_actual.png"
        render_path = final_output_file

        # Load the images
        image1 = cv2.imread(ground_truth_path)
        image2 = cv2.imread(render_path)

        # Compare the images
        mse_value, ssim_value = compare_images(image1, image2)

        # Print the results
        print(f"Scene: {scene_name}")
        print(f"Mean Squared Error (MSE): {mse_value:.2f}")
        print(f"Structural Similarity Index (SSIM): {ssim_value:.2f}")

        # Write results to a text file
        with open(f"{output_dir}/{scene_name}_comparison.txt", 'w') as txt_file:
            txt_file.write(f"Scene: {scene_name}\n")
            txt_file.write(f"Mean Squared Error (MSE): {mse_value:.2f}\n")
            txt_file.write(f"Structural Similarity Index (SSIM): {ssim_value:.2f}\n")

if __name__ == "__main__":
    main()
