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
import os
import sys

from rprblender import config
from rprblender import utils

from rprblender.utils import logging
log = logging.Log(tag='engine.init')


if utils.IS_DEBUG_MODE:
    project_root = utils.package_root_dir().parent.parent
    rpr_lib_dir = project_root / '.sdk/rpr/bin'
    rif_lib_dir = project_root / '.sdk/rif/bin'

    if utils.IS_WIN:
        os.environ['PATH'] = f"{rpr_lib_dir};{rif_lib_dir};" \
                             f"{os.environ.get('PATH', '')}"
    else:
        os.environ['LD_LIBRARY_PATH'] = f"{rpr_lib_dir}:{rif_lib_dir}:" \
                             f"{os.environ.get('LD_LIBRARY_PATH', '')}"

    sys.path.append(str(project_root / "src/bindings/pyrpr/.build"))
    sys.path.append(str(project_root / "src/bindings/pyrpr/src"))

else:
    rpr_lib_dir = rif_lib_dir = utils.package_root_dir()
    if utils.IS_WIN:
        os.environ['PATH'] = f"{rpr_lib_dir};{os.environ.get('PATH', '')}"
    else:
        os.environ['LD_LIBRARY_PATH'] = f"{rpr_lib_dir}:{os.environ.get('LD_LIBRARY_PATH', '')}"

    sys.path.append(str(utils.package_root_dir()))


import pyrpr
import pyhybrid
import pyrpr2

pyrpr.init(rpr_lib_dir, logging.Log(tag='core'), config.pyrpr_log_calls)
log.info("Core version:", utils.core_ver_str(full=True))

import pyrpr_load_store
pyrpr_load_store.init(rpr_lib_dir)

import pyrprimagefilters
pyrprimagefilters.init(rif_lib_dir, logging.Log(tag='rif'), config.pyrprimagefilters_log_calls)
log.info("RIF version:", utils.rif_ver_str(full=True))

from rprblender.utils import helper_lib
helper_lib.init()


def register_plugins():
    rprsdk_bin_path = utils.package_root_dir() if not utils.IS_DEBUG_MODE else \
        utils.package_root_dir().parent.parent / '.sdk/rpr/bin'

    def register_plugin(ContextCls, lib_name, cache_path):
        lib_path = rprsdk_bin_path / lib_name
        ContextCls.register_plugin(lib_path, cache_path)
        log(f"Registered plugin: plugin_id={ContextCls.plugin_id}, "
                  f"lib_path={lib_path}, cache_path={cache_path}")

    cache_dir = utils.core_cache_dir()

    register_plugin(pyrpr.Context,
                    {'Windows': 'Tahoe64.dll',
                     'Linux': 'libTahoe64.so',
                     'Darwin': 'libTahoe64.dylib'}[utils.OS],
                    cache_dir / f"{hex(pyrpr.API_VERSION)}_rpr")

    # enabling hybrid only for Windows and Linux
    pyhybrid.enabled = config.enable_hybrid and (utils.IS_WIN or utils.IS_LINUX)
    if pyhybrid.enabled:
        try:
            register_plugin(pyhybrid.Context,
                            {'Windows': 'Hybrid.dll',
                             'Linux': 'Hybrid.so'}[utils.OS],
                            cache_dir / f"{hex(pyrpr.API_VERSION)}_hybrid")
        except RuntimeError as err:
            log.warn(err)
            pyhybrid.enabled = False

    # enabling RPR 2
    try:
        register_plugin(pyrpr2.Context,
                        {'Windows': 'Northstar64.dll',
                            'Linux': 'libNorthstar64.so',
                            'Darwin': 'libNorthstar64.dylib'}[utils.OS],
                        cache_dir / f"{hex(pyrpr.API_VERSION)}_rpr2")
    except RuntimeError as err:
        log.warn(err)


register_plugins()

pyrpr.Context.load_devices()
log(f"Loaded devices: cpu={pyrpr.Context.cpu_device}, gpu={pyrpr.Context.gpu_devices}")
