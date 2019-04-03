#!python3
import platform
import sys
import os

from pathlib import Path

import cffi

sys.path.append('src')
import pyrprapi

def export(json_file_name, dependencies, header_file_name, cffi_name, output_name, output_name_make, abi_mode):
    ffi = cffi.FFI()

    rprsdk_path = Path('../../../ThirdParty/RadeonProRender SDK').resolve()

    api_desc_fpath = str(Path(pyrprapi.__file__).parent / json_file_name)

    with open('rprapi.h', 'w') as f:
        for dep in dependencies:
            write_api(str(Path(pyrprapi.__file__).parent / dep), f, abi_mode)
        write_api(api_desc_fpath, f, abi_mode)

    ffi.cdef(Path('rprapi.h').read_text())

    lib_names = ['RadeonProRender64', 'RprSupport64','RadeonImageFilters64', 'ProRenderGLTF','python37']

    if "Windows" == platform.system():
        inc_dir = [str(rprsdk_path / "../../src/bindings/pyrpr"),
                   str(rprsdk_path / "Win/inc"),
                   str(rprsdk_path / "../RadeonProImageProcessing/Windows/inc"),
                   str(rprsdk_path / "../RadeonProRender-GLTF/Win/inc")]
        lib_dir = [str(rprsdk_path / "Win/lib"),
                   str(rprsdk_path / "../RadeonProImageProcessing/Windows/lib"),
                   str(rprsdk_path / "../RadeonProRender-GLTF/Win/lib")]
    elif "Linux" == platform.system():
        assert 'Ubuntu' in platform.version()
        # assert '16.04' in platform.version()
        inc_dir = [str(rprsdk_path / "../../src/bindings/pyrpr"),
                   str(rprsdk_path / "Linux-Ubuntu/inc"),
                   str(rprsdk_path / "../RadeonProImageProcessing/Linux/Ubuntu/include"),
                   str(rprsdk_path / "../RadeonProRender-GLTF/Linux-Ubuntu/inc")]
        lib_dir = [str(rprsdk_path / "Linux-Ubuntu/lib"),
                   str(rprsdk_path / "../RadeonProImageProcessing/Linux/Ubuntu/lib64"),
                   str(rprsdk_path / "../RadeonProRender-GLTF/Linux-Ubuntu/lib")]
    elif "Darwin" == platform.system():
        inc_dir = [str(rprsdk_path / "../../src/bindings/pyrpr"),
                   str(rprsdk_path / "Mac/inc"),
                   str(rprsdk_path / "../RadeonProImageProcessing/Mac/inc"),
                   str(rprsdk_path / "../RadeonProRender-GLTF/Mac/inc")]
        lib_dir = [str(rprsdk_path / "Mac/lib"),
                   str(rprsdk_path / "../RadeonProImageProcessing/Mac/lib"),
                   str(rprsdk_path / "../RadeonProRender-GLTF/Mac/lib")]
    else:
        assert False

    for d in inc_dir:
        assert os.path.isdir(d), "Bad include path: '%s'" % d
    for d in lib_dir:
        assert os.path.isdir(d), "Bad lib path: '%s'" % d

    if abi_mode:
        ffi.set_source(cffi_name, None)
    else:
        ffi.set_source(cffi_name,
                       """
                       #include <""" + header_file_name + """>
                       """,
                       libraries=lib_names,
                       include_dirs=inc_dir,
                       library_dirs=lib_dir,
                       source_extension='.cpp',
                       )


    build_dir = Path(__file__).parent / '.build'

    if not '--no-compile' in sys.argv:
        ffi.compile(tmpdir=str(build_dir), verbose=True)

    import _cffi_backend
    import shutil
    import subprocess

    with (build_dir / output_name).open('w') as pyrprwrap:
        cmd = [sys.executable, output_name_make, str(api_desc_fpath)]
        print(cmd)
        subprocess.check_call(cmd, stdout=pyrprwrap)

    shutil.copy(_cffi_backend.__file__, str(build_dir))

    if 'Linux' == platform.system():
        for path in (Path(_cffi_backend.__file__).parent / '.libs_cffi_backend').iterdir():
            if '.so' in path.suffixes:
                # copy library needed for cffi backend
                ffi_lib = str(path)
                shutil.copy(ffi_lib, str(build_dir))

        # change RPATH for cffi backend to find libffi in the same directory
        cffi_backend_path = (Path(build_dir) / Path(_cffi_backend.__file__).name).absolute()
        assert cffi_backend_path.is_file()
        cmd = ['patchelf', '--set-rpath', "$ORIGIN", str(cffi_backend_path)]
        print(' '.join(cmd))
        subprocess.check_call(cmd)

    if 'Darwin' == platform.system():
        for path in (Path(_cffi_backend.__file__).parent).iterdir():
            if '.so' in path.suffixes and "cffi" in str(path):
                # copy library needed for cffi backend
                ffi_lib = str(path)
                shutil.copy(ffi_lib, str(build_dir))

def eval_constant(s):
    if s.endswith('U'):
        s = s[:-1]

    return eval(s)
    

def write_api(api_desc_fpath, f, abi_mode):
    api = pyrprapi.load(api_desc_fpath)
    for name, c in api.constants.items():
        print(name)
        print('#define', name, eval_constant(c.value) if abi_mode else '...' , file=f)
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
        if 'rprxGetLog' == name:
            continue
        if 'rifContextExecuteCommandQueue' == name:
            print('rif_int rifContextExecuteCommandQueue(rif_context context, rif_command_queue command_queue, void *executeFinishedCallbackFunction(void* userdata), void* data, float* time);', file=f)
            continue
        print(name, [(arg.name, arg.type) for arg in t.args])
        print(t.restype, name, '(' + ', '.join(arg.type + ' ' + arg.name for arg in t.args) + ');', file=f)


if __name__ == "__main__":
    abi_mode = 'Windows' != platform.system()
    if '--abi-mode' in sys.argv:
        abi_mode = True
        
                
    export('pyrprwrapapi.json', [], 'rprwrap.h', 
           '__rpr', 'pyrprwrap.py', 'pyrprwrap_make.py', abi_mode)

    export('pyrprsupportapi.json', ['pyrprapi.json'], 'RprSupport.h',
           '__rprx', 'pyrprsupportwrap.py', 'pyrprsupportwrap_make.py', abi_mode)

    export('pyrprimagefiltersapi.json', [], 'imagefilterswrap.h' if platform.system() != 'Darwin' else 'imagefilterswrap_metal.h',
           '__imagefilters', 'pyrprimagefilterswrap.py', 'pyrprimagefilterswrap_make.py', abi_mode)

    export('pyrprgltfapi.json', ['pyrprapi.json', 'pyrprsupportapi.json'], 'ProRenderGLTF.h',
           '__gltf', 'gltfwrap.py', 'pyrprgltfwrap_make.py', abi_mode)

