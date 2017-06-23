import sys
from pathlib import Path
import numpy as np
import imageio

lib_path = 'production_material_library'
icons_fpath = 'icons.png' 

names = { path.stem for path in Path(lib_path).iterdir() if path.is_file()}



if 1<len(sys.argv):
    external_lib_path = sys.argv[1] 
    icons_fpath = 'icons_other.png'
     
    paths = []   
    for path in Path(external_lib_path).iterdir():
        if path.is_dir():
            for f in path.iterdir():
                if (f.stem==path.stem) and (path.stem in names):
                    paths.append(f)
else:
    paths = list(Path(lib_path).iterdir()) 


paths = list(sorted(paths))


def iter_images():
    for path in paths:
        if path.is_file() and path.suffix in ['.png', '.jpg']:
            try:
                yield imageio.imread(str(path))
            except:
                print(path)
                raise
    

shapes = [im.shape for im in iter_images()]

count = len(shapes)

assert 1 == len(set(shapes))

s = shapes[0]


import math

for i in range(count):
    if i*i>=count:
        break

square_size = i


# we don't need it bigger that number of rows 
rect_height = count//square_size+(1 if count%square_size else 0)

r = np.zeros((s[0]*rect_height, s[1]*square_size, s[2]), dtype=np.float32)

for i, im in enumerate(iter_images()):
    x, y = i % square_size, i//square_size
    r[y*s[1]:(y+1)*s[1], x*s[0]:(x+1)*s[0], 0:s[2] ] = im

imageio.imwrite(icons_fpath, r.copy())

print(r.shape, s)