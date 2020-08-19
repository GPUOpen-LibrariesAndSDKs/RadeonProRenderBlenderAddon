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

import sys
import traceback

from rprblender import config
from rprblender import utils

from rprblender.utils import logging
log = logging.Log(tag='engine.init')


def pyrpr_init(bindings_import_path, rprsdk_bin_path):
    log("pyrpr_init: bindings_path=%s, rpr_bin_path=%s" % (bindings_import_path, rprsdk_bin_path))

    if bindings_import_path not in sys.path:
        sys.path.append(bindings_import_path)

    try:
        import pyrpr
        import pyhybrid
        import pyrpr2

        rpr_version = utils.core_ver_str(full=True)

        log.info(f"RPR Core version: {rpr_version}")
        pyrpr.lib_wrapped_log_calls = config.pyrpr_log_calls
        pyrpr.init(logging.Log(tag='core'), rprsdk_bin_path=rprsdk_bin_path)

        import pyrpr_load_store
        pyrpr_load_store.init(rprsdk_bin_path)

        import pyrprimagefilters
        rif_version = utils.rif_ver_str(full=True)
        log.info(f"Image Filters version {rif_version}")
        pyrprimagefilters.lib_wrapped_log_calls = config.pyrprimagefilters_log_calls
        pyrprimagefilters.init(log, rprsdk_bin_path=rprsdk_bin_path)

        # import pyrprgltf
        # pyrprgltf.lib_wrapped_log_calls = config.pyrprgltf_log_calls
        # pyrprgltf.init(log, rprsdk_bin_path=rprsdk_bin_path)

    except:
        logging.critical(traceback.format_exc(), tag='')
        return False

    finally:
        sys.path.remove(bindings_import_path)

    return True


if 'pyrpr' not in sys.modules:

    # try loading pyrpr for installed addon
    bindings_import_path = str(utils.package_root_dir())
    rprsdk_bin_path = utils.package_root_dir()
    if not pyrpr_init(bindings_import_path, rprsdk_bin_path):
        logging.warn("Failed to load rpr from %s. One more attempt will be provided." % bindings_import_path)

        # try loading pyrpr from source
        src = utils.package_root_dir().parent
        project_root = src.parent

        rprsdk_bin_path = project_root / ".sdk/rpr/bin"

        bindings_import_path = str(src / 'bindings/pyrpr/.build')
        pyrpr_import_path = str(src / 'bindings/pyrpr/src')

        if bindings_import_path not in sys.path:
            sys.path.append(pyrpr_import_path)

        try:
            assert pyrpr_init(bindings_import_path, rprsdk_bin_path)
        finally:
            sys.path.remove(pyrpr_import_path)

    logging.info('rprsdk_bin_path:', rprsdk_bin_path)


import pyrpr
import pyhybrid
import pyrpr2


def register_plugins():
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
    pyrpr2.enabled = config.enable_rpr2
    if pyrpr2.enabled:
        try:
            register_plugin(pyrpr2.Context,
                            {'Windows': 'Northstar64.dll',
                             'Linux': 'libNorthstar64.so',
                             'Darwin': 'libNorthstar64.dylib'}[utils.OS],
                            cache_dir / f"{hex(pyrpr.API_VERSION)}_rpr2")
        except RuntimeError as err:
            log.warn(err)
            pyrpr2.enabled = False


# we do import of helper_lib just to load RPRBlenderHelper.dll at this stage
import rprblender.utils.helper_lib


register_plugins()

pyrpr.Context.load_devices()
log(f"Loaded devices: cpu={pyrpr.Context.cpu_device}, gpu={pyrpr.Context.gpu_devices}")
