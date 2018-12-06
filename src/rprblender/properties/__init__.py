import bpy

from rprblender import logging

from . import (
    Render,
    Output,
    Object,
    Mesh,
    Lamp,
    Material,
)


modules_to_register = (
    Render,
    Output,
    Object,
    Mesh,
    Material,
)


# Register/unregister all required classes of RPR properties in one go
classes = []
for module in modules_to_register:
    module_classes = getattr(module, "classes", None)
    if module_classes:
        classes.extend(module_classes)
logging.debug("Classes to register are {}".format(classes), tag="properties")
register, unregister = bpy.utils.register_classes_factory(classes)
