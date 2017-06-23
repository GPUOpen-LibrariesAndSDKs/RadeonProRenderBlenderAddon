#!python3
import platform
import sys
from pathlib import Path

import cffi

sys.path.append('src')
import pyrprapi

ffi = cffi.FFI()

rprsdk_path = Path('../../../ThirdParty/RadeonProRender SDK').resolve()

api_desc_fpath = str(Path(pyrprapi.__file__).parent / 'pyrprapi.json')
api = pyrprapi.load(api_desc_fpath)

with open('rprapi.h', 'w') as f:
    for name, c in api.constants.items():
        print('#define', name, eval(c.value), file=f)

    for name, t in api.types.items():
        print(name, t.kind)
        if 'struct' == t.kind:
            print('typedef struct', name, '{', file=f)
            for field in t.fields:
                print('    ' + field.type, field.name + ';', file=f)
            print('};', file=f)
        else:
            print('typedef ', t.type, name, ';', file=f)

    for name, t in api.functions.items():
        print(name, [(arg.name, arg.type) for arg in t.args])
        print(t.restype, name, '(' + ', '.join(arg.type + ' ' + arg.name for arg in t.args) + ');', file=f)

ffi.cdef(Path('rprapi.h').read_text())

lib_name = 'RadeonProRender64'
lib_folder = 'lib'
if "Windows" == platform.system():
    platform_folder = "Win"
elif "Linux" == platform.system():
    assert 'Ubuntu-16.04' in platform.platform()
    platform_folder = "Linux"
else:
    assert False

abi_mode = 'Windows' != platform.system()

if abi_mode:
    ffi.set_source("__rpr", None)
else:
    ffi.set_source("__rpr",
                   """
                   #include <RadeonProRender.h>
                   """,
                   libraries=[lib_name],
                   include_dirs=[str(rprsdk_path / platform_folder / 'inc')],
                   library_dirs=[str(rprsdk_path / platform_folder / lib_folder)],
                   source_extension='.cpp',
                   )

if __name__ == "__main__":
    build_dir = Path(__file__).parent / '.build'
    src_dir = Path(__file__).parent

    if not '--no-compile' in sys.argv:
        ffi.compile(tmpdir=str(build_dir), verbose=True)
    import _cffi_backend
    import shutil
    import subprocess

    with (build_dir / 'pyrprwrap.py').open('w') as pyrprwrap:
        subprocess.check_call([sys.executable, 'pyrprwrap_make.py', str(api_desc_fpath)], stdout=pyrprwrap)

    import _cffi_backend

    shutil.copy(_cffi_backend.__file__, str(build_dir))

    if 'Linux' == platform.system():
        for path in (Path(_cffi_backend.__file__).parent / '.libs_cffi_backend').iterdir():
            if '.so' in path.suffixes:
                # copy library needed for cffi backend
                # ffi_lib = '/usr/local/lib/python3.5/dist-packages/.libs_cffi_backend/libffi-72499c49.so.6.0.4'
                ffi_lib = str(path)
                shutil.copy(ffi_lib, str(build_dir))

        # change RPATH for cffi backend to find libffi in the same directory
        cffi_backend_path = (Path(build_dir) / Path(_cffi_backend.__file__).name).absolute()
        assert cffi_backend_path.is_file()
        cmd = ['patchelf', '--set-rpath', "$ORIGIN", str(cffi_backend_path)]
        print(' '.join(cmd))
        subprocess.check_call(cmd)
