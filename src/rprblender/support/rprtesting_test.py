from pathlib import Path

from rprtesting import *

import numpy as np

import pytest

np.seterr(all='raise')


def test_compare_images():
    a = np.full((30, 40, 4), 1.0)
    b = np.full((30, 40, 4), 0.99)

    with pytest.raises(AssertionError):
        assert_images_similar(a, b, max_average_deviation=0.005)

    assert_images_similar(a, b, max_average_deviation=0.011, max_std_dev=0.011)

    a = np.full((120, 160, 3), (0, 0, 0), dtype=np.float32)
    pos = (a.shape[0] // 2, a.shape[1] // 2)

    # bright fat dot
    b = a.copy()
    anomaly_size = 3
    draw_square(b, pos, anomaly_size, (0.5,) * 3)
    with pytest.raises(AssertionError):
        assert_images_similar(a, b, max_average_deviation=1.0, max_std_dev=0.01)

    # bright slim dot
    b = a.copy()
    anomaly_size = 2
    draw_square(b, pos, anomaly_size, (0.5,) * 3)
    assert_images_similar(a, b, max_average_deviation=0.002, max_std_dev=0.01)

    # big faint spot passing
    b = a.copy()
    anomaly_size = 20
    draw_square(b, pos, anomaly_size, (0.05,) * 3)
    assert_images_similar(a, b, max_average_deviation=0.002, max_std_dev=0.01)

    # big, faint but noticeable, spot failing
    b = a.copy()
    anomaly_size = 20
    draw_square(b, pos, anomaly_size, (0.1,) * 3)
    with pytest.raises(AssertionError):
        assert_images_similar(a, b, max_average_deviation=1.0, max_std_dev=0.01)

    # huge, faint but noticeable, spot
    b = a.copy()
    anomaly_size = 50
    draw_square(b, pos, anomaly_size, (0.025,) * 3)
    assert_images_similar(a, b, max_average_deviation=1.0, max_std_dev=0.01)

    # huge, faint but noticeable, spot
    b = a.copy()
    anomaly_size = 50
    draw_square(b, pos, anomaly_size, (0.05,) * 3)
    import imageio
    imageio.imwrite(str(Path(__file__).parent / 't.png'), b)
    with pytest.raises(AssertionError):
        assert_images_similar(a, b, max_average_deviation=1.0, max_std_dev=0.01)


def draw_square(image, pos, size, color):
    image[pos[0]:pos[0] + size, pos[1]:pos[1] + size, ...] = np.full((
        size, size, 3), color)


if __name__ == '__main__':
    import pytest

    pytest.main(args=[__file__,
                      '-s',
                      ])
