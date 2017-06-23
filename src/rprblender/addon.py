import bpy

from .logging import debug, info


class Addon:

    def __init__(self):
        self.classes_to_register = [] 
    
    def register_class(self, cls):
        self.classes_to_register.append(cls)
        return cls

    def register_all(self):
        for cls in self.classes_to_register:
            info('registering', cls)
            bpy.utils.register_class(cls)
        
    def unregister_all(self):
        for cls in reversed(self.classes_to_register):
            info('unregistering', cls)
            bpy.utils.unregister_class(cls)
