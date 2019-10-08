import platform
import _cffi_backend
from _pyrpr_load_store import ffi

lib = None


def init(rpr_sdk_bin_path):

    global lib

    path = get_library_path(rpr_sdk_bin_path)
    lib = ffi.dlopen(path)


def export(name, context, scene, flags):

    file_name = bytes(name, encoding="latin1")

    # last param defines export bit flags.
    # image handling type flags:
    # RPRLOADSTORE_EXPORTFLAG_EXTERNALFILES (1 << 0) - image data will be stored to rprsb external file
    # RPRLOADSTORE_EXPORTFLAG_COMPRESS_IMAGE_LEVEL_1 (1 << 1) - image data will be lossless compressed during export
    # RPRLOADSTORE_EXPORTFLAG_COMPRESS_IMAGE_LEVEL_2 (1 << 2) - image data will be lossy compressed during export
    #  note: without any of above flags images will not be exported.
    return lib.rprsExport(file_name, context._get_handle(), scene._get_handle(),
                          0, ffi.NULL, ffi.NULL, 0, ffi.NULL, ffi.NULL, flags)


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
