#!python3
import platform
import functools
import inspect
import traceback

from pathlib import Path
import ctypes

import bpy

import pyrpr
from pyrpr import ffi
from enum import IntEnum

from rprblender import config, logging, render

class SavedSettings():
    device_type = ''
    gpu_count = -1
    gpu_states_inited = False
    gpu_states = [False, False, False, False, False, False, False, False]
    include_uncertified_devices = False

    device_type_plus_cpu = False
    samples = 1
    notify_update_addon = True

    initialized = False

    @classmethod
    def is_changed(cls, settings):
        if cls.device_type != settings.device_type:
            return True
        if cls.gpu_count != settings.gpu_count:
            return True
        if cls.gpu_states_inited != settings.gpu_states_inited:
            return True
        if cls.include_uncertified_devices != settings.include_uncertified_devices:
            return True
        if cls.device_type_plus_cpu != settings.device_type_plus_cpu:
            return True
        if cls.samples != settings.samples:
            return True
        if cls.notify_update_addon != settings.notify_update_addon:
            return True

        assert len(cls.gpu_states) == len(settings.gpu_states)
        res = [i for i in range(len(cls.gpu_states)) if cls.gpu_states[i] != settings.gpu_states[i]]
        if len(res) > 0:
            return True
        return False

    @classmethod
    def update(cls, settings):
        cls.device_type = settings.device_type
        cls.gpu_count = settings.gpu_count
        cls.gpu_states_inited = settings.gpu_states_inited
        cls.include_uncertified_devices = settings.include_uncertified_devices

        cls.device_type_plus_cpu = settings.device_type_plus_cpu
        cls.samples = settings.samples
        cls.notify_update_addon = settings.notify_update_addon

        for i in range(len(cls.gpu_states)):
            cls.gpu_states[i] = settings.gpu_states[i]


def settings_changed(self, context):
    if SavedSettings.is_changed(self) and self.gpu_states_inited:
        if SavedSettings.initialized:
            save_user_settings()
            SavedSettings.update(self)


devices_types_desc = (('gpu', "GPU", "Use GPU only"),
                      ('cpu', "CPU", "Use CPU only"))
                      # ('gpu_cpu', "GPU + CPU", "Use GPU + CPU (coming soon)"))

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
        return res[0], res[1]

    def is_device_compatible(self, device_id):
        compatibility = self.is_device_compatible_by_rpr(device_id)
        if compatibility not in [Compatibility.INCOMPATIBLE_UNCERTIFIED, Compatibility.COMPATIBLE]:
            #logging.info("device '%s' compatibility: %s" % (device_id, compatibility))
            return

        pluginID = pyrpr.RegisterPlugin(str(self.renderer_dll_path).encode('utf8'))
        assert -1 != pluginID

        flags, context_info = self.get_params_by_device_id(device_id)

        context = pyrpr.Object(core_type_name=pyrpr.Context.core_type_name)
        status = pyrpr.CreateContext(pyrpr.API_VERSION, [pluginID], 1, flags, ffi.NULL, ffi.NULL, context)
        if status is pyrpr.SUCCESS:
            size_ptr = ffi.new('size_t *', 0)
            status = pyrpr.ContextGetInfo(context, context_info, 0, ffi.NULL, size_ptr)
            if status is pyrpr.SUCCESS:
                size = size_ptr[0]
                name_ptr = ffi.new('char[]', size)
                pyrpr.ContextGetInfo(context, context_info, size, name_ptr, ffi.NULL)
                if status is pyrpr.SUCCESS:
                    device_name = ffi.string(name_ptr).decode('ascii')
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

    def get_used_gpu_info(self):
        info = ''
        gpu_certified = False
        gpu_non_certified = False

        for i, device in enumerate(self.devices):
            if device['certified']:
                gpu_certified = True
            else:
                gpu_non_certified = True

        settings = get_user_settings()

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
        settings = get_user_settings()
        if not settings.gpu_states_inited:
            logging.info('gpu states not inited')
            for i, device in enumerate(self.devices):
                settings.gpu_states[i] = device['certified']

            settings.gpu_states_inited = True
            set_gpu_count(settings, settings.gpu_count)
        else:
            SavedSettings.update(settings) # update data without saving
            self.update_gpu_states_in_settings(settings.gpu_states)


    def enable_autosave(self):
        SavedSettings.initialized = True  # allow save settings after that
        settings = get_user_settings()
        settings_changed(settings, None)

    def get_max_gpu_can_use(self):
        settings = get_user_settings()
        res = get_used_gpu_count(settings.gpu_states)
        res = min(len(self.devices), res)
        return res

    def get_used_devices_flags(self):
        settings = get_user_settings()
        flags = 0
        used = 0
        for i in range(len(settings.gpu_states)):
            if settings.gpu_states[i] is True and i < len(self.devices) and used < settings.gpu_count:
                gpu = self.devices[i]
                flags |= gpu['flags']
                logging.info('using GPU(%d): "%s"' % (used, gpu['name']))
                used += 1

        logging.info('total used %d gpu, flags(%d)' % (used, flags))
        return flags

    def get_used_devices(self):
        settings = get_user_settings()
        devices = ''
        used = 0
        for i in range(len(settings.gpu_states)):
            if settings.gpu_states[i] is True and i < len(self.devices) and used < settings.gpu_count:
                gpu = self.devices[i]
                devices = devices + gpu['name']
                used += 1

        return devices

    def update_gpu_states_in_settings(self, gpu_states):
        settings = get_user_settings()
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


        res = self.lib.check_device(path, 'Linux' != platform.system(), device_id,
                                    {'Windows': Os.WINDOWS, 'Linux': Os.LINUX}[platform.system()],
                                    str(render.ensure_core_cache_folder()).encode('latin1'))

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
        set_device_type(self,device_cpu)


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
    render_resources_helper.update_gpu_states_in_settings(settings.gpu_states)
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

            log_fun(f.__name__,
                    ', '.join(p.name+': '+str(value) for p, value in zip(signature.parameters.values(), argv)),
                    ', '.join(name+': '+str(value) for name, value in kwargs.items()),
                    )
            try:
                result = f(*argv, **kwargs)
            except:
                logging.critical(traceback.format_exc())
                raise
            if config.debug:
                log_fun(f.__name__, "done -> ", result)
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