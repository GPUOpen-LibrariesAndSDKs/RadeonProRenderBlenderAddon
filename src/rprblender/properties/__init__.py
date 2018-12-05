import bpy

from rprblender.utils import logging

from . import Object
from . import Mesh
from . import Render


modules_to_register = (
    Object,
    Mesh,
    Render,
)


# Register/unregister all required classes of RPR properties in one go
classes = []
for module in modules_to_register:
    module_classes = getattr(module, "classes", None)
    if module_classes:
        classes.extend(module_classes)
logging.debug("Classes to register are {}".format(classes), tag="properties")
register, unregister = bpy.utils.register_classes_factory(classes)
