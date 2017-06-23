import numpy as np


def assert_images_similar(a, b, max_average_deviation=0.005, max_std_dev=0.005):
    deviations_flat = (a - b).ravel()
    variance = np.dot(deviations_flat, deviations_flat) / len(deviations_flat)
    std_dev = np.sqrt(variance)
    avg_dev = sum(np.abs(deviations_flat)) / len(deviations_flat)
    print("avg_dev: {avg_dev}, std_dev: {std_dev}".format(**locals()))
    assert avg_dev <= max_average_deviation and std_dev <= max_std_dev, (
        (avg_dev, max_average_deviation), (std_dev, max_std_dev))
