from distutils.core import setup, Extension
from Cython.Build import cythonize

from pathlib import Path

rprsdk_path = Path('../../ThirdParty/RadeonProRender SDK/Win') 


setup(ext_modules = cythonize(Extension(
           "rpr",                                # the extension name
           sources=["rpr.pyx"], # the Cython source and
                                                  # additional C++ source files
           language="c++",                        # generate and compile C++ code
           library_dirs=[str(rprsdk_path/'lib')],
           libraries=["RadeonProRender64"],
      )))
