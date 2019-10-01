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
        
        # load the shared lib from a common path where the
        # dependent libs have been remapped
        if "Darwin" == platform.system():
            rprsdk_path = "/Users/Shared/RadeonProRender"
        else:
            rprsdk_path = str(project_root / 'ThirdParty/RadeonProRender SDK')

        bin_folder = { 'Windows': 'Win/bin', 'Linux': 'Linux-Ubuntu/lib', 'Darwin': 'lib' }[platform.system()]

        rprsdk_bin_path = Path(rprsdk_path) / bin_folder

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

cache_path = str(utils.package_root_dir() / '.core_cache' / hex(pyrpr.API_VERSION))
if not os.path.isdir(cache_path):
    os.makedirs(cache_path)

tahoe = {
    'Windows': 'Tahoe64.dll',
    'Linux': 'libTahoe64.so',
    'Darwin': 'libTahoe64.dylib',
} [platform.system()]

tahoe_path = str(rprsdk_bin_path / tahoe)
log_pyrpr.info(f"Registering plugin with: tahoe_path={tahoe_path}, cache_path={cache_path}")
pyrpr.Context.register_plugin(tahoe_path, cache_path)
log_pyrpr.info(f"Plugin is registered: plugins={pyrpr.Context.plugins}, "
               f"cpu_device={pyrpr.Context.cpu_device}, gpu_devices={pyrpr.Context.gpu_devices}")

# enabling hybrid only for Windows now
pyhybrid.enabled = config.enable_hybrid and utils.IS_WIN

if pyhybrid.enabled:
    hybrid = {
        'Windows': 'Hybrid.dll',
        'Linux': 'Hybrid.so',
        # 'Darwin': 'Hybrid.dylib',
    }[platform.system()]
    hybrid_path = str(rprsdk_bin_path / hybrid)
    hybrid_cache = str(utils.package_root_dir() / '.hybrid_cache' / hex(pyrpr.API_VERSION))
    log_pyrpr.info(f"Registering plugin with: hybrid_path={hybrid_path}, cache_path={hybrid_cache}")
    try:
        pyhybrid.Context.register_plugin(hybrid_path, hybrid_cache)
        log_pyrpr.info(f"Plugin is registered: plugins={pyhybrid.Context.plugins}, "
                     f"gpu_devices={pyhybrid.Context.gpu_devices}")

    except RuntimeError as e:
        pyhybrid.enabled = False
        log_pyrpr.error(e)

# we do import of helper_lib just to load RPRBlenderHelper.dll at this stage
import rprblender.utils.helper_lib
