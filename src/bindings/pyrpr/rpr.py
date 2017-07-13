#!python3
import platform
import sys
from pathlib import Path

import cffi

sys.path.append('src')
import pyrprapi

def export(json_file_name, dependencies, header_file_name, cffi_name, output_name, output_name_make):
    ffi = cffi.FFI()

    rprsdk_path = Path('../../../ThirdParty/RadeonProRender SDK').resolve()

    api_desc_fpath = str(Path(pyrprapi.__file__).parent / json_file_name)

    with open('rprapi.h', 'w') as f:
        for dep in dependencies:
            write_api(str(Path(pyrprapi.__file__).parent / dep), f)
        write_api(api_desc_fpath, f)

    ffi.cdef(Path('rprapi.h').read_text())

    lib_names = ['RadeonProRender64', 'RprSupport64']
    if "Windows" == platform.system():
        platform_folder = 'Win'
    elif "Linux" == platform.system():
        assert 'Ubuntu-16.04' in platform.platform()
        platform_folder = 'Linux'
    else:
        assert False

    abi_mode = 'Windows' != platform.system()

    if abi_mode:
        ffi.set_source(cffi_name, None)
    else:
        ffi.set_source(cffi_name,
                       """
                       #include <""" + header_file_name + """>
                       """,
                       libraries=lib_names,
                       include_dirs=[str(rprsdk_path / platform_folder / 'inc')],
                       library_dirs=[str(rprsdk_path / platform_folder / 'lib' )],
                       source_extension='.cpp',
                       )


    build_dir = Path(__file__).parent / '.build'
    src_dir = Path(__file__).parent

    if not '--no-compile' in sys.argv:
        ffi.compile(tmpdir=str(build_dir), verbose=True)
    import _cffi_backend
    import shutil
    import subprocess

    with (build_dir / output_name).open('w') as pyrprwrap:
        cmd = [sys.executable, output_name_make, str(api_desc_fpath)]
        print(cmd)
        subprocess.check_call(cmd, stdout=pyrprwrap)

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


def write_api(api_desc_fpath, f):
    api = pyrprapi.load(api_desc_fpath)
    for name, c in api.constants.items():
        print(name)
        print('#define', name, '...', file=f)
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
        if 'rprxGetLog' == name:continue
        print(name, [(arg.name, arg.type) for arg in t.args])
        print(t.restype, name, '(' + ', '.join(arg.type + ' ' + arg.name for arg in t.args) + ');', file=f)


if __name__ == "__main__":
    export('pyrprapi.json', [], 'RadeonProRender.h', '__rpr', 'pyrprwrap.py', 'pyrprwrap_make.py')
    export('pyrprsupportapi.json', ['pyrprapi.json'],
           'RprSupport.h', '__rprx', 'pyrprsupportwrap.py', 'pyrprsupportwrap_make.py')
