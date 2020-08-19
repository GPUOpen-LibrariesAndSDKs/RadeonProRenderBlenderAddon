import math
import numpy as np

import pyrpr
from pyrprwrap import (
    ContextCreateSphereLight,
    SphereLightSetRadiantPower3f,
    SphereLightSetRadius,
    ContextCreateDiskLight,
    DiskLightSetRadiantPower3f,
    DiskLightSetRadius,
    DiskLightSetAngle,
)

# will be used in other modules to check if RPR 2 is enabled
enabled = False


class Context(pyrpr.Context):
    pass


class SphereLight(pyrpr.Light):
    def __init__(self, context):
        super().__init__(context)
        ContextCreateSphereLight(self.context, self)

        # keep target intensity and radius to adjust actual intensity when they are changed
        self._radius_squared = 1

    def set_radiant_power(self, r, g, b):
        # Adjust intensity by current radius
        SphereLightSetRadiantPower3f(self,
                                     r / self._radius_squared,
                                     g / self._radius_squared,
                                     b / self._radius_squared)

    def set_radius(self, radius):
        radius = max(radius, 0.01)
        self._radius_squared = radius * radius
        SphereLightSetRadius(self, radius)


class DiskLight(pyrpr.Light):
    def __init__(self, context):
        super().__init__(context)
        ContextCreateDiskLight(self.context, self)

        # keep target intensity and radius to adjust actual intensity when they are changed
        self._radius_squared = 1

    def set_radiant_power(self, r, g, b):
        # Adjust intensity by current radius
        DiskLightSetRadiantPower3f(self,
                                   r / self._radius_squared,
                                   g / self._radius_squared,
                                   b / self._radius_squared)

    def set_cone_shape(self, iangle, oangle):
        # Use external angle oangle
        DiskLightSetAngle(self, oangle)

    def set_radius(self, radius):
        radius = max(radius, 0.01)
        self._radius_squared = radius * radius
        DiskLightSetRadius(self, radius)
