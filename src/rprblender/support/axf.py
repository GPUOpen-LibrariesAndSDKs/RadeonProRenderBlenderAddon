import os
from pathlib import Path
import subprocess
import platform

import ctypes

if 'Linux' == platform.system():
    pass
else:
    import ctypes.wintypes


class AxfConverter:
    def __init__(self, axf_converter_bin_path, use_dll=True):
        self.axf_converter_bin_path = axf_converter_bin_path
        self.use_dll = use_dll

    def convert(self, axf_path):
        if self.use_dll:
            path = Path(self.axf_converter_bin_path) / 'AxfConverter.dll'
            assert path.is_file()

            oldpath = os.environ['PATH']
            os.environ['PATH'] = str(self.axf_converter_bin_path) + os.pathsep + oldpath

            l = ctypes.cdll.LoadLibrary(str(path))

            l.convertAxFFile.argtypes = [
                ctypes.c_char_p, ctypes.c_char_p]

            xml_path = ctypes.create_string_buffer(ctypes.wintypes.MAX_PATH)

            assert os.path.isfile(axf_path)

            l.convertAxFFile(
                axf_path.encode('utf-8'),
                xml_path)
            return xml_path.value
        else:
            exe_path = Path(self.axf_converter_bin_path) / 'AxfConverter.exe'
            cmd = [str(exe_path), axf_path]
            print(cmd)
            ret = subprocess.call(cmd)
            if ret:
                return None
            axf_path = Path(axf_path)
            name = axf_path.with_suffix('').name
            return axf_path.parent / name / (name + '.xml')
