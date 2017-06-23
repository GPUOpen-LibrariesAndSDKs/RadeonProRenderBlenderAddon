import imageio
import numpy as np
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).parents[2]/'src/rprblender/support'))
import rprtesting

failure_dir = Path(sys.argv[1])

expected = None
expected_path = (failure_dir / 'expected.list')
if expected_path.is_file():
    expected = np.array(eval(expected_path.read_text()))[:,:,:3]
    print('expected:', np.min(expected), np.max(expected))

actual = None
actual_path = failure_dir / 'actual.list'
if actual_path.is_file():
    actual = np.array(eval((actual_path).read_text()))[:,:,:3]
    print('actual:', np.min(actual), np.max(actual))

    l, u = np.min(actual), np.max(actual)

    scale = 1/(u-l)
    offset = -l*scale
    print('recommended - scale: %s, offset: %s'%(scale, offset))

    if 2 < len(sys.argv):
        user_scale, user_offset = float(sys.argv[2]), float(sys.argv[3])

        print('will result in - lower: %s, upper: %s'%(user_scale*l+user_offset, user_scale*u+user_offset))
        scale, offset = user_scale, user_offset

if expected is not None and actual is not None:

    actual_normalized = actual * scale + offset
    expected_normalized = expected * scale + offset

    imageio.imsave('dev.png', np.abs(actual_normalized-expected_normalized))
    imageio.imsave('actual_normalized.png', actual_normalized)
    print('actual_normalized:', np.min(actual_normalized), np.max(actual_normalized))
    imageio.imsave('expected_normalized.png', expected_normalized)
    print('expected_normalized:', np.min(expected_normalized), np.max(expected_normalized))

    #imageio.imsave('expected_normalized_hi.png', expected_normalized > 0.9)

    rprtesting.assert_images_similar(imageio.imread('actual_normalized.png')/255, actual_normalized)
    #rprtesting.assert_images_similar(expected_normalized, actual_normalized)
    
