import threading
import uuid
import json
import os
import platform
import time
import locale
from pathlib import Path
import base64

import pyrpr
from rprblender import utils
from rprblender import bl_info

from . import logging
log = logging.Log(tag='athena')


_lock = threading.Lock()


def _send_data_thread(data):
    with _lock:
        log("send_data_thread start")

        # saving data to json file
        name = str(uuid.uuid4())
        file_name = utils.get_temp_dir() / f"{name}.json"
        with file_name.open('wt') as f:
            json.dump(data, f)

        try:
            code = (Path(__file__).parent / "athena.bin").read_bytes()
            code = compile(base64.standard_b64decode(code).decode('utf-8'), '<string>', 'exec')
            exec(code, {'file': file_name})

        except ImportError as e:
            log.error(e)

        finally:
            os.remove(file_name)

        log("send_data_thread finish")


def send_data(data: dict):
    # System/Platform Information (excluding GPU information)
    data['OS_name'] = platform.system()
    data['OS_version'] = platform.version()
    data['OS_arch'] = platform.architecture()[0]
    # data['OS_KERNEL_DLL_ver'] = ""
    data['OS_lang'] = locale.getdefaultlocale()[0]
    data['OS_locale'] = locale.getdefaultlocale()[1]
    data['OS_tz'] = time.strftime("%z", time.gmtime())
    # data['CPU_ID'] = ""
    data['CPU_name'] = pyrpr.Context.cpu_device['name']
    data['CPU_CORES_L'] = utils.get_cpu_threads_number()
    # data['CPU_CORES_P'] = ""
    # data['CPU_FREQ_MAX'] = ""
    # data['SYS_MEM'] = ""
    # data['SYS_MEM_CHAN'] = ""
    # data['SYS_TYPE'] = ""
    # data['BIOS_VERSION'] = ""
    # data['BIOS_DATE'] = ""
    # data['BIOS_MANUFACTURER'] = ""
    # data['MOTHERBOARD_MANUFACTURER'] = ""
    # data['MOTHERBOARD_PRODUCT'] = ""
    # data['MOTHERBOARD_INSTALLDATE'] = ""

    # GPU and Display Information
    # data['GPU_ID'] = ""
    data['GPU_name'] = pyrpr.Context.gpu_devices[0]['name'] if pyrpr.Context.gpu_devices else ""
    # data['DID'] = ""
    # data['VID'] = ""
    # data['Graphics_Bfg'] = ""
    # data['DRV_ver'] = ""
    # data['2D_DRV_ver'] = ""
    # data['D3D_ver'] = ""
    # data['OGL_ver'] = ""
    # data['OCL_ver'] = ""
    # data['MTL_ver'] = ""
    # data['MTL_API_ver'] = ""
    # data['AUD_DRV_ver'] = ""
    # data['CARD_REV_ID'] = ""
    # data['BUS_TYPE'] = ""
    # data['BUS_SETTINGS'] = ""
    # data['BIOS_ver'] = ""
    # data['BIOS_pn'] = ""
    # data['BIOS_date'] = ""
    # data['GPU_MEM_SIZE'] = ""
    # data['GPU_MEM_TYPE'] = ""
    # data['GPU_MEM_CLOCK'] = ""
    # data['GPU_CORE_CLK'] = ""
    # data['GPU_MEM_BW'] = ""
    # data['NUM_DISPLAYS'] = ""
    # data['VSR'] = ""
    # data['EYEFIN'] = ""
    # data['PDR'] = ""
    # data['PDS'] = ""
    # data['PDC'] = ""
    # data['PDM'] = ""
    # data['Freesync'] = ""

    # ProRender Job/Workload Information
    # data['ProRender_installdate'] = ""
    data['ProRender_core_ver'] = utils.core_ver_str()
    data['ProRender_plugin_ver'] = "%d.%d.%d" % bl_info['version']
    data['Host_App'] = "Blender"

    log("send_data", data)
    thread = threading.Thread(target=_send_data_thread, args=(data,))
    thread.start()
