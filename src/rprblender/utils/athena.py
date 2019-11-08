import threading
import uuid
import json
import os
import platform
import time
import locale
from pathlib import Path
import base64

import bpy
import pyrpr
from rprblender import utils
from rprblender import bl_info

from . import logging
from . import IS_MAC
log = logging.Log(tag='athena')


_lock = threading.Lock()
is_error = False


def _send_data_thread(data):
    global is_error

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

        except Exception as e:
            log.error(e)
            is_error = True

        finally:
            os.remove(file_name)

        log("send_data_thread finish")


def get_system_language():
    """ Get system language and locale """
    try:
        default_locale = locale.getdefaultlocale()
    except ValueError:
        if IS_MAC:
            # Fix for "ValueError: unknown locale: UTF-8" on Mac.
            # The default English locale on Mac is set as "UTF-8" instead of "en-US.UTF-8"
            # see https://bugs.python.org/issue18378
            return 'en_US', 'UTF-8'

        # re-throw any other issue
        raise

    system_lang = default_locale[0]
    system_locale = default_locale[1]

    return system_lang, system_locale


def send_data(data: dict):
    if is_error:
        return

    # System/Platform Information (excluding GPU information)
    data['OS Name'] = platform.system()
    data['OS Version'] = platform.version()
    data['OS Arch'] = platform.architecture()[0]
    data['OS Lang'], data['OS Locale'] = get_system_language()
    data['OS TZ'] = time.strftime("%z", time.gmtime())

    if pyrpr.Context.cpu_device:
        data['CPU Name'] = pyrpr.Context.cpu_device['name']
        data['CPU Cores'] = utils.get_cpu_threads_number()

    for i, gpu in enumerate(pyrpr.Context.gpu_devices):
        data[f'GPU{i} Name'] = gpu['name']

    # ProRender Job/Workload Information
    data['ProRender Core Version'] = utils.core_ver_str()
    data['ProRender Plugin Version'] = "%d.%d.%d" % bl_info['version']
    data['Host App'] = "Blender"
    data['App Version'] = ".".join(str(v) for v in bpy.app.version)

    log("send_data", data)
    thread = threading.Thread(target=_send_data_thread, args=(data,))
    thread.start()
