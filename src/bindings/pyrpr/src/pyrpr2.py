import numpy as np

import pyrpr


# will be used in other modules to check if RPR 2 is enabled
enabled = False


class Context(pyrpr.Context):
    pass


class Scene(pyrpr.Scene):
    def attach(self, obj):
        if isinstance(obj, pyrpr.Curve):
            return

        super().attach(obj)


class Curve(pyrpr.Curve):
    def __init__(self, context, control_points, points_radii, uvs):
        pass

    def delete(self):
        pass

    def set_material(self, material):
        pass

    def set_transform(self, transform: np.array, transpose=True):
        pass

    def set_name(self, name):
        self.name = name
