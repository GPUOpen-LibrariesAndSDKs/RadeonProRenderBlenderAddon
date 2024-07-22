import os
import cv2
import numpy as np
import argparse
from skimage.metrics import structural_similarity as ssim


class ImageComparer:
    def __init__(self, output_dir, scene_name):
        self.output_dir = output_dir
        self.scene_name = scene_name
        self.ground_truth_path = f"ground_truth/{scene_name}_actual.png"
        self.render_path = os.path.join(output_dir, f"{scene_name}_final.png")

    def mse(self, imageA, imageB):
        err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
        err /= float(imageA.shape[0] * imageA.shape[1])
        return err

    def compare_images(self):
        # Load the images
        image1 = cv2.imread(self.ground_truth_path)
        image2 = cv2.imread(self.render_path)

        if image1 is None or image2 is None:
            print("Error: One of the images could not be loaded.")
            return

        # Compare the images
        mse_value = self.mse(image1, image2)
        ssim_value = ssim(image1, image2, win_size=7, multichannel=True, channel_axis=2)

        # Print the results
        print(f"Scene: {self.scene_name}")
        print(f"Mean Squared Error (MSE): {mse_value:.2f}")
        print(f"Structural Similarity Index (SSIM): {ssim_value:.2f}")

        # Write results to a text file
        with open(f"{self.output_dir}/{self.scene_name}_comparison.txt", 'w') as txt_file:
            txt_file.write(f"Scene: {self.scene_name}\n")
            txt_file.write(f"Mean Squared Error (MSE): {mse_value:.2f}\n")
            txt_file.write(f"Structural Similarity Index (SSIM): {ssim_value:.2f}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare rendered images with ground truth images.")
    parser.add_argument('--output-dir', required=True, help='Directory where the rendered images are saved')
    parser.add_argument('--scene-name', required=True, help='Name of the scene to compare')

    args = parser.parse_args()

    comparer = ImageComparer(args.output_dir, args.scene_name)
    comparer.compare_images()
