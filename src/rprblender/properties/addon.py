"""
Keep addon settings:
- selected render devices
"""

import bpy

from .render import RPR_UserSettings


class RPR_AddonPreferences(bpy.types.AddonPreferences):
    """ Settings stored in Blender User Preferences instead of .blend scene files"""

    bl_idname = 'rprblender'
    settings: bpy.props.PointerProperty(type=RPR_UserSettings)
