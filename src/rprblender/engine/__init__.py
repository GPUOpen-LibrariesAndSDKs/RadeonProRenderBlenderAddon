import os
import sys
import platform
import threading
from pathlib import Path
import contextlib
import traceback

import gc

import rprblender
from rprblender import config, logging

import bpy


#_lock = threading.Lock()

#@contextlib.contextmanager
#def core_operations(raise_error=False):
#    """ Contextmanager for all render calls, besides locking catches all exceptions
#    and forwards them to log file"""
#    try:
#        with _lock:
#            yield
#    except:
#        logging.critical(traceback.format_exc(), tag='render')
#        if raise_error:
#            raise


def get_package_root_dir():
    return Path(rprblender.__file__).parent


def log_pyrpr(*argv):
    logging.info(*argv, tag='engine')


def pyrpr_init(bindings_import_path, rprsdk_bin_path):
    log_pyrpr("pyrpr_init: bindings_path=%s, rpr_bin_path=%s" % (bindings_import_path, rprsdk_bin_path))

    if bindings_import_path not in sys.path:
        sys.path.append(bindings_import_path)

    try:
        import pyrpr
        import pyrprapi  # import this to be have it in the sys.modules available later

        log_pyrpr("RPR Core version", hex(pyrpr.API_VERSION))
        pyrpr.lib_wrapped_log_calls = config.pyrpr_log_calls
        pyrpr.init(log_pyrpr, rprsdk_bin_path=rprsdk_bin_path)

        import pyrpr_load_store
        pyrpr_load_store.init(rprsdk_bin_path)

        import pyrprx
        log_pyrpr("RPRX Support version", hex(pyrprx.SUPPORT_API_VERSION))
        pyrprx.lib_wrapped_log_calls = config.pyrprx_log_calls
        pyrprx.init(log_pyrpr, rprsdk_bin_path=rprsdk_bin_path)

        import pyrprimagefilters
        log_pyrpr("Image Filters version", hex(pyrprimagefilters.API_VERSION))
        pyrprimagefilters.lib_wrapped_log_calls = config.pyrprimagefilters_log_calls
        pyrprimagefilters.init(log_pyrpr, rprsdk_bin_path=rprsdk_bin_path)

        import pyrprgltf
        pyrprgltf.lib_wrapped_log_calls = config.pyrprgltf_log_calls
        pyrprgltf.init(log_pyrpr, rprsdk_bin_path=rprsdk_bin_path)
    except:
        logging.critical(traceback.format_exc(), tag='')
        return False
    finally:
        sys.path.remove(bindings_import_path)
    return True


if 'pyrpr' not in sys.modules:

    # TODO: nasty dependency on cffi_backend module that is implicitly imported from our ffi
    # solution - use something without this dependency, ctypes, cython, SWIG

    # try loading pyrpr for installed addon
    bindings_import_path = str(get_package_root_dir())
    rprsdk_bin_path = get_package_root_dir()
    if not pyrpr_init(bindings_import_path, rprsdk_bin_path):
        logging.warn("Failed to load rpr from %s. One more attempt will be provided.", bindings_import_path)

        # try loading pyrpr from source
        src = get_package_root_dir().parent
        project_root = src.parent
        
        # load the shared lib from a common path where the
        # dependent libs have been remapped
        if "Darwin" == platform.system():
            rprsdk_path = "/Users/Shared/RadeonProRender"
        else:
            rprsdk_path = str(project_root / 'ThirdParty/RadeonProRender SDK')

        if "Windows" == platform.system():
            bin_folder = 'Win/bin'
        elif "Linux" == platform.system():
            bin_folder = 'Linux-Ubuntu/lib'
        elif "Darwin" == platform.system():
            bin_folder = 'lib'
        else:
            assert False

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


#def ensure_core_trace_folder():
#    if bpy.context.scene.rpr.dev.trace_dump_folder == '':
#        path = str(get_package_root_dir() / '.core_trace')
#    else:
#        path = bpy.path.native_pathsep(bpy.path.abspath(bpy.context.scene.rpr.dev.trace_dump_folder))

#    if not os.path.isdir(path):
#        os.makedirs(path)
#    return path


#def get_context_creation_flags(is_production, is_viewport):
#    settings = helpers.get_device_settings(is_production)
#    flags = 0
#    if settings.use_cpu:
#        flags = pyrpr.CREATION_FLAGS_ENABLE_CPU
#        logging.info('Using CPU only')
#    if settings.use_gpu:
#        flags |= helpers.render_resources_helper.get_used_devices_flags(is_production)
#        assert flags != 0
#        # Keeping this mode for testing
#        useGpuOcl = 'USE_GPU_OCL' in os.environ
#        if useGpuOcl:
#            logging.info("Enabling OCL GPU rendering")
#        elif 'Darwin' == platform.system():
#            flags |= pyrpr.CREATION_FLAGS_ENABLE_METAL
#            logging.info("Enabling Metal GPU rendering")
#        if (settings.use_cpu) and (is_production):
#            logging.info('Using GPU+CPU')
#        if is_viewport:
#            flags |= pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP
#            logging.info('Using GL_INTEROP')

#    return flags


def create_context(flags, props=None):
    #tahoe_path = get_core_render_plugin_path()
    #plugin_id = pyrpr.register_plugin(tahoe_path)
    #if plugin_id == -1:
    #    raise RuntimeError("Plugin is not registered", tahoe_path)

    cache_path = str(get_package_root_dir() / '.core_cache' / hex(pyrpr.API_VERSION))
    if not os.path.isdir(cache_path):
        os.makedirs(cache_path)

    return pyrpr.Context([plugin_id,], flags, props, cache_path)


def get_core_render_plugin_path():
    lib_name = {
        'Windows': 'Tahoe64.dll',
        'Linux': 'libTahoe64.so',
        'Darwin': 'libTahoe64.dylib' 
        } [platform.system()]

    return str(rprsdk_bin_path / lib_name)


#support_path = str(get_package_root_dir() / 'support')
#if support_path not in sys.path:
#    sys.path.append(support_path)


#render_devices = {}


#def get_render_device(is_production=True, is_viewport=False, persistent=False):
#    import rprblender.render.device

#    flags = rprblender.render.get_context_creation_flags(is_production, is_viewport)
#    logging.debug("get_render_device(is_production=%s), flags: %s" %(is_production, hex(flags)), tag='render.device')

#    cpu_threads_number = 0
#    props = None
#    if is_production:
#        settings = helpers.get_device_settings(is_production)
#        if settings.use_cpu:
#            cpu_threads_number = max(helpers.MIN_CPU_THREADS_NUMBER,
#                                     min(helpers.MAX_CPU_THREADS_NUMBER, settings.cpu_threads))
#            props = [pyrpr.CONTEXT_CREATEPROP_CPU_THREAD_LIMIT, cpu_threads_number, 0]

#    if persistent:
#        key = (is_production, flags, cpu_threads_number)

#        if key in render_devices:
#            return render_devices[key]

#        render_devices.clear()  # don't keep more than one device(not to multiply memory usage for image cache)

#    logging.debug("create new device, not found in cache:", render_devices, tag='render.device')
#    device = rprblender.render.device.RenderDevice(is_production=is_production, context_flags=flags,
#                                                   context_props=props)
#    if persistent:
#        render_devices[key] = device
#    return device


#def register():
#    logging.debug('rpr.render.register')


#def unregister():
#    logging.debug('rpr.render.unregister')


#def free_render_devices():
#    logging.debug("free_render_devices", tag='render.device')
#    import rprblender.render.device
#    while render_devices:
#        render_device = render_devices.popitem()[1]  # type: rprblender.render.device.RenderDevice

#        if config.debug:
#            referrers = gc.get_referrers(render_device)
#            logging.critical("render_device has more than one reference(current frame and something else):")
#            for r in referrers:
#                if r != sys._getframe(0):
#                    logging.critical(r)
#                    try:
#                        logging.critical(r.f_code)
#                        while r.f_back is not None:
#                            r = r.f_back
#                            logging.critical(r.f_code)

#                    except AttributeError:pass
#            del referrers
#        del render_device

plugin_id = pyrpr.register_plugin(get_core_render_plugin_path())
if plugin_id == -1:
    raise RuntimeError("Plugin is not registered", get_core_render_plugin_path())

logging.info("Plugin is registered with plugin_id=%d" % plugin_id, get_core_render_plugin_path())
