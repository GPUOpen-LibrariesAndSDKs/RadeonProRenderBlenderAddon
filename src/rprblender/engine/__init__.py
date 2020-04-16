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
import platform
import sys
import traceback
from pathlib import Path

from rprblender import config
from rprblender import utils
from rprblender.utils import logging

__all__ = tuple()


log_pyrpr = logging.Log(tag='core')


def pyrpr_init(bindings_import_path, rprsdk_bin_path):
    log_pyrpr("pyrpr_init: bindings_path=%s, rpr_bin_path=%s" % (bindings_import_path, rprsdk_bin_path))

    if bindings_import_path not in sys.path:
        sys.path.append(bindings_import_path)

    try:
        import pyrpr
        import pyrprapi  # import this to be have it in the sys.modules available later
        import pyhybrid
        import pyrpr2

        log_pyrpr.info("RPR Core version", hex(pyrpr.API_VERSION))
        pyrpr.lib_wrapped_log_calls = config.pyrpr_log_calls
        pyrpr.init(log_pyrpr, rprsdk_bin_path=rprsdk_bin_path)

        import pyrpr_load_store
        pyrpr_load_store.init(rprsdk_bin_path)

        import pyrprimagefilters
        log_pyrpr.info("Image Filters version", hex(pyrprimagefilters.API_VERSION))
        pyrprimagefilters.lib_wrapped_log_calls = config.pyrprimagefilters_log_calls
        pyrprimagefilters.init(log_pyrpr, rprsdk_bin_path=rprsdk_bin_path)

        # import pyrprgltf
        # pyrprgltf.lib_wrapped_log_calls = config.pyrprgltf_log_calls
        # pyrprgltf.init(log_pyrpr, rprsdk_bin_path=rprsdk_bin_path)

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

cache_path = utils.package_root_dir() / '.cache'

tahoe = {
    'Windows': 'Tahoe64.dll',
    'Linux': 'libTahoe64.so',
    'Darwin': 'libTahoe64.dylib',
}[platform.system()]
tahoe_path = rprsdk_bin_path / tahoe
rpr_cache = cache_path / f"{hex(pyrpr.API_VERSION)}_rpr"
if not rpr_cache.is_dir():
    rpr_cache.mkdir(parents=True)

log_pyrpr.info(f"Registering plugin with: tahoe_path={tahoe_path}, cache_path={rpr_cache}")
pyrpr.Context.register_plugin(str(tahoe_path), str(rpr_cache))
log_pyrpr.info(f"Plugin is registered: plugins={pyrpr.Context.plugins}, "
               f"cpu_device={pyrpr.Context.cpu_device}, gpu_devices={pyrpr.Context.gpu_devices}")

# enabling hybrid only for Windows and Linux now
pyhybrid.enabled = config.enable_hybrid and (utils.IS_WIN or utils.IS_LINUX)

if pyhybrid.enabled:
    hybrid = {
        'Windows': 'Hybrid.dll',
        'Linux': 'Hybrid.so',
        # 'Darwin': 'Hybrid.dylib',
    }[platform.system()]
    hybrid_path = rprsdk_bin_path / hybrid
    hybrid_cache = cache_path / f"{hex(pyrpr.API_VERSION)}_hybrid"
    if not hybrid_cache.is_dir():
        hybrid_cache.mkdir(parents=True)

    log_pyrpr.info(f"Registering plugin with: hybrid_path={hybrid_path}, cache_path={hybrid_cache}")
    try:
        pyhybrid.Context.register_plugin(str(hybrid_path), str(hybrid_cache))
        log_pyrpr.info(f"Plugin is registered: plugins={pyhybrid.Context.plugins}, "
                       f"gpu_devices={pyhybrid.Context.gpu_devices}")
        pyhybrid.enabled = bool(pyhybrid.Context.gpu_devices)

    except RuntimeError as e:
        pyhybrid.enabled = False
        log_pyrpr.error(e)


# checking for RPR 2.0
rpr2_path = rprsdk_bin_path / "Northstar64.dll"
pyrpr2.enabled = config.enable_rpr2 and utils.IS_WIN and rpr2_path.exists()

if pyrpr2.enabled:
    rpr2_cache = cache_path / f"{hex(pyrpr.API_VERSION)}_rpr2"
    if not rpr2_cache.is_dir():
        rpr2_cache.mkdir(parents=True)

    log_pyrpr.info(f"Registering plugin with: core2_path={rpr2_path}, cache_path={rpr2_cache}")
    try:
        pyrpr2.Context.register_plugin(str(rpr2_path), str(rpr2_cache))
        log_pyrpr.info(f"Plugin is registered: plugins={pyrpr2.Context.plugins}, "
                       f"gpu_devices={pyrpr2.Context.gpu_devices}")
        pyrpr2.enabled = bool(pyrpr2.Context.gpu_devices)

    except RuntimeError as e:
        pyrpr2.enabled = False
        log_pyrpr.error(e)

# we do import of helper_lib just to load RPRBlenderHelper.dll at this stage
import rprblender.utils.helper_lib
