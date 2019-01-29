import platform
import _cffi_backend
from _pyrpr_load_store import ffi

lib = None


def init(rpr_sdk_bin_path):

    global lib

    path = get_library_path(rpr_sdk_bin_path)
    lib = ffi.dlopen(path)


def export(name, context, scene):

    file_name = bytes(name, encoding="latin1")
    return lib.rprsExport(file_name, context._get_handle(), scene._get_handle(),
                          0, ffi.NULL, ffi.NULL, 0, ffi.NULL, ffi.NULL, 1) # last param is RPRLOADSTORE_EXPORTFLAG_EXTERNALFILES (1 << 0) 


def get_library_path(rpr_sdk_bin_path):

    os = platform.system()

    if os == "Windows":
        return str(rpr_sdk_bin_path / 'RprLoadStore64.dll')
    elif os == "Linux":
        return str(rpr_sdk_bin_path / 'libRprLoadStore64.so')
    elif os == "Darwin":
        return str(rpr_sdk_bin_path / 'libRprLoadStore64.dylib')
    else:
        assert False
