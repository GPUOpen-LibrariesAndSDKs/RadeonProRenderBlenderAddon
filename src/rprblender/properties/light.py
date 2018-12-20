import bpy
from bpy.props import (
    PointerProperty,
)

from rprblender import utils
from rprblender.utils import logging
from . import RPR_Properties


class RPR_LightProperties(RPR_Properties):
    def sync(self, rpr_context, obj):
        ''' sync the mesh '''
        light = self.id_data
        logging.info("Syncing light: %s" % light.name, tag='Light')

        rpr_light = rpr_context.create_light(utils.key(obj), 'point')
        rpr_light.set_name(light.name)
        rpr_light.set_radiant_power(10.0, 10.0, 10.0)
        rpr_light.set_transform(utils.get_transform(obj))
        rpr_context.scene.attach(rpr_light)

    @classmethod
    def register(cls):
        logging.info("register", tag='Light')
        bpy.types.Light.rpr = PointerProperty(
            name="RPR Light Settings",
            description="RPR light settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        logging.info("unregister", tag='Light')
        del bpy.types.Light.rpr
