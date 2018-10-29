#!python3

import os
import platform
import functools
import inspect
import threading
import traceback
import math

from pathlib import Path
import ctypes

import bpy

import pyrpr
from pyrpr import ffi
from enum import IntEnum

from rprblender import config, logging, render

# Windows-only
if platform.system() == 'Windows':
    import winreg


def settings_changed(self, context):
    save_user_settings()


devices_types_desc = (('gpu', "GPU", "Use GPU only"),
                      ('cpu', "CPU", "Use CPU only"))


def get_device_type_index(device_type_name):
    for i, val in enumerate(devices_types_desc):
        if val[0] == device_type_name:
            return i
    assert False
    return 0


def get_user_settings():
    if __package__ in bpy.context.user_preferences.addons.keys():
        return bpy.context.user_preferences.addons[__package__].preferences.settings
    else:
        return bpy.context.scene.rpr.fake_user_settings;


def get_device_settings(production_render=True):
    return get_user_settings().final_device_settings if production_render else get_user_settings().viewport_device_settings


def save_user_settings():
    if __package__ in bpy.context.user_preferences.addons.keys():
        logging.info('Automatic save user preferences...')
        bpy.ops.wm.save_userpref()
    else:
        logging.info('Please save current scene for saving user settings')
        # if bpy.context.blend_data.filepath:
        #     logging.info('Automatic save user settings/scene(%s)...' % bpy.context.blend_data.filepath)
        #     bpy.ops.wm.save_mainfile()


def get_used_gpu_count(gpu_states):
    return len([gpu_states[i] for i in range(len(gpu_states)) if gpu_states[i] is True and i < len(render_resources_helper.devices)])


def is_osx_mojave():
    if platform.system() == 'Darwin':
        mac_vers_major = platform.mac_ver()[0].split('.')[1]
        return float(mac_vers_major) >= 14
    else:
        return False


def use_mps():
    ''' determines if metal MPS should be used. Only on OSX 10.14 or greater '''
    if is_osx_mojave():
        return get_user_settings().use_mps
    else:
        return False


def get_ooc_cache_size(preview_render):
    ''' return texture cache size if > 0 and enabled, else return 0.  Only for preview '''
    viewport_settings = get_user_settings().viewport_render_settings
    if preview_render and viewport_settings.ooc_tex_cache:
        return viewport_settings.ooc_cache_size
    else:
        return 0


def get_cpu_name():
    if platform.system() == 'Windows':
        return ""
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0",
                                      0, winreg.KEY_READ)
        value, regtype = winreg.QueryValueEx(registry_key, 'ProcessorNameString')
        winreg.CloseKey(registry_key)
        return value.strip()
    except WindowsError:
        return None


class DeviceId(IntEnum):  # sync with RprTools.h
    GPU0 = 0
    GPU1 = 1
    GPU2 = 2
    GPU3 = 3
    GPU4 = 4
    GPU5 = 5
    GPU6 = 6
    GPU7 = 7

class Compatibility(IntEnum):   # sync with RprTools.h
    COMPATIBLE = 0
    INCOMPATIBLE_UNKNOWN = 1
    INCOMPATIBLE_UNCERTIFIED = 2
    INCOMPATIBLE_CONTEXT_UNSUPPORTED = 3
    INCOMPATIBLE_CONTEXT_ERROR = 4


class Os(IntEnum):   # sync with RprTools.h
    WINDOWS = 0
    LINUX = 1
    MACOS = 2

def isMetalOn():
    if 'Darwin' == platform.system():
        useGpuOcl = 'USE_GPU_OCL' in os.environ
        return not useGpuOcl
    return False

#@rpraddon.register_class
class RenderResourcesHelper:
    max_gpu_count = 8

    def get_params_by_device_id(self, device_id):
        data = [[pyrpr.CREATION_FLAGS_ENABLE_GPU0, pyrpr.CONTEXT_GPU0_NAME],
                [pyrpr.CREATION_FLAGS_ENABLE_GPU1, pyrpr.CONTEXT_GPU1_NAME],
                [pyrpr.CREATION_FLAGS_ENABLE_GPU2, pyrpr.CONTEXT_GPU2_NAME],
                [pyrpr.CREATION_FLAGS_ENABLE_GPU3, pyrpr.CONTEXT_GPU3_NAME],
                [pyrpr.CREATION_FLAGS_ENABLE_GPU4, pyrpr.CONTEXT_GPU4_NAME],
                [pyrpr.CREATION_FLAGS_ENABLE_GPU5, pyrpr.CONTEXT_GPU5_NAME],
                [pyrpr.CREATION_FLAGS_ENABLE_GPU6, pyrpr.CONTEXT_GPU6_NAME],
                [pyrpr.CREATION_FLAGS_ENABLE_GPU7, pyrpr.CONTEXT_GPU7_NAME],
                ]

        res = data[device_id]
 
        flags = res[0]
        if isMetalOn():
            flags = flags | pyrpr.CREATION_FLAGS_ENABLE_METAL
        
        return flags, res[1]

    def is_device_compatible(self, device_id):
        compatibility = self.is_device_compatible_by_rpr(device_id)
        if compatibility not in [Compatibility.INCOMPATIBLE_UNCERTIFIED, Compatibility.COMPATIBLE]:
            logging.info("device '%s' compatibility: %s" % (device_id, compatibility))
            return

        plugin_id = pyrpr.register_plugin(self.renderer_dll_path)
        if plugin_id == -1:
            raise RuntimeError("Plugin is not registered", self.renderer_dll_path)

        flags, context_info = self.get_params_by_device_id(device_id)

        context = pyrpr.Context([plugin_id,], flags)
        device_name = context.get_info_str(context_info)
        if not self.is_driver_compatible(device_name):
            logging.info("device %s' has incompatible driver, skip" % (device_name))
            return

        certified = compatibility != Compatibility.INCOMPATIBLE_UNCERTIFIED
        if certified:
            logging.info("   device '%s' is certified" % (device_name))
        else:
            logging.info("   device '%s' isn't certified" % (device_name))

        self.devices.append({'name': device_name, 'flags': flags, 'certified': certified})

    def __init__(self, renderer_dll_path):
        logging.info("   Renderer DLL Path:", renderer_dll_path)

        self.renderer_dll_path = renderer_dll_path
        self.devices = []
        self.lib_init()

        for d in DeviceId:
            self.is_device_compatible(d)


    def __del__(self):
        print (' self.lib_release()...')
        assert self.lib
        self.lib_release()

    def get_used_gpu_info(self, is_production):
        info = ''
        gpu_certified = False
        gpu_non_certified = False

        for i, device in enumerate(self.devices):
            if device['certified']:
                gpu_certified = True
            else:
                gpu_non_certified = True

        settings = get_device_settings(is_production)

        if not gpu_certified:
            if gpu_non_certified:
                if settings.include_uncertified_devices:
                    info = "RPR: Your graphics card has not been certified for use with Radeon ProRender so you may encounter rendering or stability issues."
                else:
                    info = "RPR: Your graphics card has not been certified for use with Radeon ProRender, so CPU rendering has been enabled by default to avoid any potential rendering or stability issues. You may override this behavior in the Radeon ProRender hardware settings."
            else:
                info = "RPR: Your graphics card or driver is not compatible with Radeon ProRender. OpenCL 1.2+ is required along with a compatible driver. CPU rendering has been enabled by default."

        return info


    def init_gpu_states(self):
        # do this for both final and viewport settings
        for settings in (get_device_settings(True), get_device_settings(False)):
            if not settings.gpu_states_inited:
                logging.info('gpu states not inited')
                for i, device in enumerate(self.devices):
                    settings.gpu_states[i] = device['certified']

                settings.gpu_states_inited = True
            else:
                self.update_gpu_states_in_settings(settings.gpu_states, settings)


    def enable_autosave(self):
        settings = get_user_settings()
        settings_changed(settings, None)

    def get_max_gpu_can_use(self):
        settings = get_device_settings()
        res = get_used_gpu_count(settings.gpu_states)
        res = min(len(self.devices), res)
        return res

    def get_used_devices_flags(self, is_production):
        settings = get_device_settings(is_production)
        flags = 0
        used = 0
        for i in range(len(settings.gpu_states)):
            if settings.gpu_states[i] is True and i < len(self.devices):
                gpu = self.devices[i]
                flags |= gpu['flags']
                logging.info('using GPU(%d): "%s"' % (used, gpu['name']))
                used += 1

        logging.info('total used %d gpu, flags(%d)' % (used, flags))
        return flags

    def get_used_devices(self):
        devices = ''
        settings = get_device_settings()
        if settings.use_cpu:
            cpu_name = get_cpu_name()
            devices = "CPU {}".format(cpu_name) if cpu_name else "CPU0"
        if settings.use_gpu:
            gpus_used = self.get_used_GPU_devices()
            for gpu in gpus_used:
                if devices:
                    devices += " | {}".format(gpu)
                else:
                    devices += gpu
        return devices

    def get_used_GPU_devices(self):
        settings = get_device_settings()
        devices = []
        used = 0
        for i in range(len(settings.gpu_states)):
            if settings.gpu_states[i] is True and i < len(self.devices):
                gpu = self.devices[i]
                devices.append(gpu['name'])
                used += 1

        return devices

    def update_gpu_states_in_settings(self, gpu_states, settings):
        have_selected_devices = False
        # update gpu states
        for i in range(len(gpu_states)):
            state = gpu_states[i]
            if len(self.devices) > i:
                device = self.devices[i]
                if not device['certified'] and not settings.include_uncertified_devices:
                    state = False
            else:
                state = False
            settings.gpu_states[i] = state
            if state:
                have_selected_devices = True

        if not have_selected_devices:
            for i, device in enumerate(self.devices):
                if not device['certified'] and not settings.include_uncertified_devices:
                    continue
                settings.gpu_states[i] = True
                break

    @staticmethod
    def _lib_paths():
        if 'Windows' == platform.system():
            yield str(Path(__file__).parent / 'RPRBlenderHelper.dll')
            yield str(Path(__file__).parents[2] / 'RPRBlenderHelper/.build/Release/RPRBlenderHelper.dll')
        elif 'Darwin' == platform.system():
            yield str(Path(__file__).parent / 'libRPRBlenderHelper.dylib')
            yield str(Path(__file__).parents[2] / 'RPRBlenderHelper/.build/libRPRBlenderHelper.dylib')
        else:
            yield str(Path(__file__).parent / 'libRPRBlenderHelper.so')
            yield str(Path(__file__).parents[2] / 'RPRBlenderHelper/.build/libRPRBlenderHelper.so')

    def lib_init(self):
        logging.info('Init lib...')
        for path in self._lib_paths():
            logging.info("trying to load", path)
            try:
                self.lib = ctypes.cdll.LoadLibrary(path)
                break
            except OSError as exc:
                logging.critical('failed to load', path)
        assert self.lib

        import rprblender.render
        addon_path = str(Path(__file__).parent).encode('utf8')
        logging.info('addon_path: ', addon_path)
        self.lib.init(addon_path)
        logging.info('Init lib ok.')

    def lib_release(self):
        #logging.info('Free lib...')
        assert self.lib
        del self.lib

    def is_driver_compatible(self, device_name):
        assert self.lib
        name = str(device_name).encode('utf8')
        res = self.lib.check_driver(name)
        return res

    def is_device_compatible_by_rpr(self, device_id):
        assert self.lib
        path = str(self.renderer_dll_path).encode('utf8')

        additionalflags = 0
        if isMetalOn():
            additionalflags = additionalflags | pyrpr.CREATION_FLAGS_ENABLE_METAL
            res = self.lib.check_device(path, 'Windows' == platform.system(), device_id,
                                        {'Windows': Os.WINDOWS, 'Linux': Os.LINUX, 'Darwin': Os.MACOS}[platform.system()],
                                        str(render.ensure_core_cache_folder()).encode('latin1'),
                                        additionalflags )
        else:
            res = self.lib.check_device(path, 'Windows' == platform.system(), device_id,
                                        {'Windows': Os.WINDOWS, 'Linux': Os.LINUX, 'Darwin': Os.MACOS}[platform.system()],
                                        str(render.ensure_core_cache_folder()).encode('latin1'),
                                        additionalflags )

        return Compatibility(res)


render_resources_helper = None

########################################################################################################################
# getters & setters

def get_gpu_count(self):
    value = render_resources_helper.get_max_gpu_can_use()
    res = self.get('gpu_count', value)
    #logging.info('get_gpu_count: ', res)
    return res


def set_gpu_count(self, value):
    max = render_resources_helper.get_max_gpu_can_use()
    if value > max:
        value = max
    self['gpu_count'] = value
    if value == 0:
        device_cpu = 1
        assert devices_types_desc[device_cpu][0] == 'cpu'
        set_device_type(self, device_cpu)


def get_cpu_cores_count():
    try:
        from multiprocessing import cpu_count
        return cpu_count()
    except (ImportError, NotImplementedError, AttributeError):
        pass

    return os.cpu_count()


MIN_CPU_THREADS_NUMBER = 2
MAX_CPU_THREADS_NUMBER = 128

cpu_cores = get_cpu_cores_count()
if cpu_cores is None:  # use min threads number if cores number is unavailable for whatever reason
    cpu_threads_default_number = MIN_CPU_THREADS_NUMBER
else:
    cpu_threads_default_number = min(max(cpu_cores, MIN_CPU_THREADS_NUMBER), MAX_CPU_THREADS_NUMBER)
logging.debug("helpers: CPU cores found {}; default threads number: {}".
             format(cpu_cores, cpu_threads_default_number))


def get_device_type(self):
    default_device_type_name = 'gpu' if len(render_resources_helper.devices) > 0 else 'cpu'
    default_device_type_index = get_device_type_index(default_device_type_name)

    # for check loaded values
    value = self.get('device_type', default_device_type_index)
    device_type = devices_types_desc[value][0]
    if device_type is not 'cpu' and len(render_resources_helper.devices) == 0:
        value = get_device_type_index('cpu')

    return value


def set_device_type(self, value):
    settings = get_user_settings()
    render_resources_helper.update_gpu_states_in_settings(settings.gpu_states, self)
    device_cpu = 1
    assert devices_types_desc[device_cpu][0] == 'cpu'

    device_type = devices_types_desc[value][0]
    max_gpu = render_resources_helper.get_max_gpu_can_use()

    if device_type == 'gpu' and max_gpu > 0:
        self['gpu_count'] = max_gpu

    if device_type != 'cpu' and max_gpu == 0:
        value = device_cpu

    #logging.info('device_type: ', value)
    self['device_type'] = value



def register():
    logging.debug("helpers.register()")
    global render_resources_helper

    render_resources_helper = RenderResourcesHelper(render.get_core_render_plugin_path())


def unregister():
    logging.debug("helpers.unregister()")
    global render_resources_helper
    del render_resources_helper





class CallLogger:
    """ Logs every wrapped call(printing args) and also prints exception if it was raised from the call -
    VERY useful for wrapping __del__ - as seems like blender swallows error messages that are printed
    by Python when an exception is thrown from destructot"""

    tag = ''

    def __init__(self, *, log_fun=None, tag=None):
        if tag:
            self.tag = tag
        if log_fun:
            self.log = log_fun

        self.thread_stack = {}

    def log(self, *args):
        if logging:
            logging.debug(*args, tag=self.tag)

    def logged(self, f):
        signature = inspect.signature(f)
        log_fun = self.log
        @functools.wraps(f)
        def wrapped(*argv, **kwargs):
            if not config.debug:
                return f(*argv, **kwargs)

            call_depth = self.thread_stack.setdefault(threading.get_ident(), 0)
            self.thread_stack[threading.get_ident()] = call_depth+1

            log_fun('-'*call_depth+'>', f.__name__,
                    ', '.join(p.name+': '+str(value) for p, value in zip(signature.parameters.values(), argv)),
                    ', '.join(name+': '+str(value) for name, value in kwargs.items()),
                    )
            try:
                result = f(*argv, **kwargs)
            except:
                logging.critical(traceback.format_exc())
                raise
            finally:
                self.thread_stack[threading.get_ident()] -= 1

            log_fun('-'*call_depth+'<', f.__name__, "done -> ", result)

            return result
        return wrapped


def create_core_enum_for_property(prefix, text_suffix):
    prop_items = []
    prop_prefix = prefix
    prop_remap = {}

    for identifier_name in dir(pyrpr):
        if identifier_name.startswith(prop_prefix):
            name = identifier_name[len(prop_prefix):]

            core_value = getattr(pyrpr, identifier_name)
            name_displayed = ' '.join(part.capitalize() for part in name.split('_'))
            prop_items.append((name, name_displayed, ' '.join(p.capitalize() for p in name.split('_'))+text_suffix, core_value ))
            prop_remap[name] = core_value

    prop_default = min(prop_items, key=lambda v:v[3])[0]

    return prop_items, prop_default, prop_remap


class subdivision_boundary_prop:
    items, default, remap = create_core_enum_for_property('SUBDIV_BOUNDARY_INTERFOP_TYPE_', " boundary")


def print_memory_usage(message):
    try:
        import psutil
    except ImportError:
        return
    p = psutil.Process()
    m = p.memory_info()
    logging.debug('memory. resident:', m.rss, 'virtual:', m.vms, "(", message, ")", tag='memory')


def convert_K_to_RGB(colour_temperature):
    # range check
    if colour_temperature < 1000:
        colour_temperature = 1000
    elif colour_temperature > 40000:
        colour_temperature = 40000

    tmp_internal = colour_temperature / 100.0
    # red
    if tmp_internal <= 66:
        red = 255
    else:
        tmp_red = 329.698727446 * math.pow(tmp_internal - 60, -0.1332047592)
        if tmp_red < 0:
            red = 0
        elif tmp_red > 255:
            red = 255
        else:
            red = tmp_red

    # green
    if tmp_internal <= 66:
        tmp_green = 99.4708025861 * math.log(tmp_internal) - 161.1195681661
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = tmp_green
    else:
        tmp_green = 288.1221695283 * math.pow(tmp_internal - 60, -0.0755148492)
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = tmp_green

    # blue
    if tmp_internal >= 66:
        blue = 255
    elif tmp_internal <= 19:
        blue = 0
    else:
        tmp_blue = 138.5177312231 * math.log(tmp_internal - 10) - 305.0447927307
        if tmp_blue < 0:
            blue = 0
        elif tmp_blue > 255:
            blue = 255
        else:
            blue = tmp_blue

    return red / 255.0, green / 255.0, blue / 255.0


# Automated tests runner support methods
def get_current_scene():
    return bpy.context.scene.name, bpy.data.scenes[bpy.context.scene.name]


def set_render_devices(use_cpu, use_gpu):
    settings = get_device_settings(True)
    settings.use_cpu = use_cpu
    settings.use_gpu = use_gpu
