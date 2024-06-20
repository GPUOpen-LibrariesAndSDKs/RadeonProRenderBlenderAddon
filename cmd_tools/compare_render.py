import cv2
import numpy as np
import argparse
from skimage.metrics import structural_similarity as ssim


# Mean Squared Error (MSE):
#   - measures: The average squared difference between corresponding pixel values in two images.
#   - quantifies how much the pixel values differ overall.

# Structural Similarity Index (SSIM):
#   - measures: The structural similarity between two images, considering luminance, contrast, and structure.
#   - assesses how similar the structures (patterns, edges) are in the images.


# Compute pixel-wise mean squared error between the two images
def mse(imageA, imageB):
    err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    err /= float(imageA.shape[0] * imageA.shape[1])
    return err


# Compute MSE and SSIM between the two images
def compare_images(imageA, imageB):
    mse_value = mse(imageA, imageB)
    #ssim_value = ssim(imageA, imageB, win_size=7, multichannel=True)  # Use multichannel for color images
    ssim_value = ssim(imageA, imageB, win_size=7, multichannel=True, channel_axis=2) # 3 channels for RGB
    return mse_value, ssim_value


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Compare a rendered image to a ground truth image.')
    parser.add_argument('--scene', type=str, help='Scene name', required=True)
    parser.add_argument('--ground_truth', type=str, help='Directory of ground truth images', required=True)
    parser.add_argument('--render', type=str, help='Directory of rendered images', required=True)
    args = parser.parse_args()

    # Construct file paths
    ground_truth_path = f"{args.ground_truth}/{args.scene}_actual.png"
    render_path = f"{args.render}/{args.scene}_final.png"

    # Load the images
    image1 = cv2.imread(ground_truth_path)
    image2 = cv2.imread(render_path)

    # Compare the images
    mse_value, ssim_value = compare_images(image1, image2)

    # Print the results
    print(f"Scene: {args.scene}")
    print(f"Mean Squared Error (MSE): {mse_value:.2f}")
    print(f"Structural Similarity Index (SSIM): {ssim_value:.2f}")

    # Write results to a text file
    with open(f"{args.render}/{args.scene}_comparison.txt", 'w') as txt_file:
        txt_file.write(f"Scene: {args.scene}\n")
        txt_file.write(f"Mean Squared Error (MSE): {mse_value:.2f}\n")
        txt_file.write(f"Structural Similarity Index (SSIM): {ssim_value:.2f}\n")

if __name__ == "__main__":
    main()
