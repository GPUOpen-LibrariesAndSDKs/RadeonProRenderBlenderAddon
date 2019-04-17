''' Engine is the functionality of the rendering process, 
maintains context, processes, etc.

Other modules in this directory could be viewport, etc.
'''

''' main Render object '''

import bpy

import weakref
import numpy as np
from abc import ABCMeta, abstractmethod

from .context import RPRContext
from rprblender.properties.view_layer import RPR_ViewLayerProperites

from rprblender.utils import logging
log = logging.Log(tag='Engine')


SUPPORTED_OBJECT_TYPES = ('CAMERA', 'MESH', 'LIGHT', 'CURVE', 'FONT', 'SURFACE', 'META')


class Engine(metaclass=ABCMeta):
    """ This is the basic Engine class """

    def __init__(self, rpr_engine):
        self.rpr_engine = weakref.proxy(rpr_engine)
        self.rpr_context = RPRContext()

    @abstractmethod
    def render(self):
        pass

    @abstractmethod
    def sync(self, depsgraph):
        ''' sync all data '''
        pass

    def apply_render_stamp(self, image, channels):
        """
        Don't change anything unless it's the final render. Redefined in render_engine to apply render stamp.
        :param image: source image
        :type image: np.Array
        :param channels: image depth in bytes per pixel
        :type channels: int
        :return: image with applied render stamp text if text allowed, unchanged source image otherwise
        :rtype: np.Array
        """
        return image

    def set_render_result(self, render_passes: bpy.types.RenderPasses):
        """
        Sets render result to render passes
        :param render_passes: render passes to collect
        :return: images
        """
        def zeros_image(channels):
            return np.zeros((self.rpr_context.height, self.rpr_context.width, channels), dtype=np.float32)

        images = []

        for p in render_passes:
            try:
                # finding corresponded aov
                aov = next((aov for aov in RPR_ViewLayerProperites.aovs_info if aov['name'] == p.name), None)
                if not aov:
                    log.warn("AOV '{}' is not found in aovs_info".format(p.name))
                    image = zeros_image(p.channels)

                image = self.rpr_context.get_image(aov['rpr'])

            except KeyError:
                # This could happen when Depth or Combined was not selected, but they still are in view_layer.use_pass_*
                log.warn("AOV '{}' is not enabled in rpr_context".format(aov['name']))
                image = zeros_image(p.channels)

            if p.channels != image.shape[2]:
                image = image[:, :, 0:p.channels]

            image = self.apply_render_stamp(image, p.channels)

            images.append(image.flatten())

        # efficient way to copy all AOV images
        render_passes.foreach_set('rect', np.concatenate(images))

    def depsgraph_objects(self, depsgraph: bpy.types.Depsgraph):
        """ Iterates evaluated objects in depsgraph with SUPPORTED_OBJECT_TYPES """

        for obj in depsgraph.objects:
            if obj.type in SUPPORTED_OBJECT_TYPES:
                yield obj

    def depsgraph_instances(self, depsgraph: bpy.types.Depsgraph):
        """ Iterates evaluated instances in depsgraph with SUPPORTED_OBJECT_TYPES """

        # Comment from Depsgrapgh.object_instances description:
        # WARNING: only use this as an iterator, never as a sequence, and do not keep any references to its items
        for instance in depsgraph.object_instances:
            if instance.is_instance and instance.object.type in SUPPORTED_OBJECT_TYPES:
                yield instance
