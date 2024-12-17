#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
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
from rprblender import config

from . import logging
from . import IS_MAC
log = logging.Log(tag='athena')


_lock = threading.Lock()
is_error = False


DEV_DISABLE_STATISTICS = "RPR_DEV_DISABLE_STATISTICS"


def is_disabled():
    """ Statistics disabled if env variable is present and has any non-empty value other than 'FALSE' """
    return config.disable_athena_report or os.environ.get(DEV_DISABLE_STATISTICS, 'FALSE').upper() not in ('FALSE', '')


def _send_data_thread(data):
    pass

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
    pass
