import sys
import os
import imageio
import numpy as np

npy_path = sys.argv[1]

assert os.path.isfile(npy_path), npy_path

im = np.array(eval(open(npy_path).read()))

rgb = im[:,:,0:3]

 
if 4 == im.shape[2]:
    alpha = im[:,:,3]

    assert np.all(0<=alpha) and np.all(alpha<=1), 'alpha is outside of 0..1 range, how did it happen???'


bounds = np.min(rgb), np.max(rgb)

if 0<=bounds[0] and bounds[1]<=1:
    print('bounds:', bounds) 
else:
    print('WARNING!!! bounds are off (0, 1) - ', bounds)

    below_zero = np.amin(rgb, axis=2) < 0
    if np.any(below_zero):
        imageio.imwrite('WARNING_below_zero.png', np.repeat(below_zero[:,:,np.newaxis], 3, axis=2)*[1, 0, 0])

    above_one = np.amax(rgb, axis=2) > 1
    if np.any(above_one):
        imageio.imwrite('WARNING_above_one.png', np.repeat(above_one[:,:,np.newaxis], 3, axis=2)*[1, 0, 0])
    
    #print(list(zip(*))  

     

imageio.imwrite(os.path.splitext(npy_path)[0]+'.png', im)
