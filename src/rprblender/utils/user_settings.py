import bpy

from .logging import Log
log = Log(tag="utils.user_settings")


def get_user_settings():
    """
    Returns render devices settings. If RPR installed as addon they are stored in addon preferences.
    In development debug mode they are stored in Scene.
    """
    if 'rprblender' in bpy.context.preferences.addons:
        return bpy.context.preferences.addons['rprblender'].preferences.settings
    else:
        return bpy.context.scene.rpr.debug_user_settings


def save_user_settings():
    """ Save User Preferences """
    if 'rprblender' in bpy.context.preferences.addons:
        log.info('Automatic save user preferences...')
        bpy.ops.wm.save_userpref()


def on_settings_changed(self, context):
    """ Callback for render devices settings change """
    # Checking that bpy.context.scene exists, because this function is called during plugin registration
    # while scene could not be created yet. This prevents following exception be raised:
    # AttributeError: '_RestrictContext' object has no attribute 'scene'
    if hasattr(bpy.context, 'scene'):
        save_user_settings()

