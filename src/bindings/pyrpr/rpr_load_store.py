from cffi import FFI
from pathlib import Path

ffi = FFI()

ffi.set_source("_pyrpr_load_store", None)

ffi.cdef("""
    int rprsExport(char const * rprsFileName, void * context, void * scene,
                    int extraCustomParam_int_number, char const * * extraCustomParam_int_names,
                    int const * extraCustomParam_int_values, int extraCustomParam_float_number,
                    char const * * extraCustomParam_float_names, float const * extraCustomParam_float_values, unsigned int exportFlags);""")

if __name__ == "__main__":

    build_dir = Path(__file__).parent / '.build'

    ffi.compile(tmpdir=str(build_dir), verbose=True)
