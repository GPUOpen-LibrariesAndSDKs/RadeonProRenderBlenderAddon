from distutils.core import setup, Extension
from Cython.Build import cythonize

from pathlib import Path

rprsdk_path = Path('../../ThirdParty/RadeonProRender SDK/Win') 


setup(ext_modules = cythonize(Extension(
           "test_gl",                                # the extension name
           sources=["test_gl.pyx"], # the Cython source and
                                                  # additional C++ source files
           language="c++",                        # generate and compile C++ code
           libraries=["OpenGL32"],
      )))
