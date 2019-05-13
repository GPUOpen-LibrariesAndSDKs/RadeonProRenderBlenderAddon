''' Engine is the functionality of the rendering process, 
maintains context, processes, etc.

Other modules in this directory could be viewport, etc.
'''

''' main Render object '''

import weakref
import numpy as np
from abc import ABCMeta, abstractmethod

import bpy
import mathutils
import pyrpr

from .context import RPRContext
from rprblender.export import object, instance
from rprblender.properties.view_layer import RPR_ViewLayerProperites

from rprblender.utils import logging
log = logging.Log(tag='Engine')


ITERATED_OBJECT_TYPES = ('MESH', 'LIGHT', 'CURVE', 'FONT', 'SURFACE', 'META')


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

    def _set_render_result(self, render_passes: bpy.types.RenderPasses):
        """
        Sets render result to render passes
        :param render_passes: render passes to collect
        :return: images
        """
        def zeros_image(channels):
            return np.zeros((self.rpr_context.height, self.rpr_context.width, channels), dtype=np.float32)

        images = []

        for p in render_passes:
            # finding corresponded aov
            aov = next((aov for aov in RPR_ViewLayerProperites.aovs_info if aov['name'] == p.name), None)
            if aov:
                try:
                    image = self.rpr_context.get_image(aov['rpr'])

                except KeyError:
                    # This could happen when Depth or Combined was not selected, but they still are in view_layer.use_pass_*
                    log.warn("AOV '{}' is not enabled in rpr_context".format(aov['name']))
                    image = zeros_image(p.channels)
            else:
                log.warn("AOV '{}' is not found in aovs_info".format(p.name))
                image = zeros_image(p.channels)

            if p.channels != image.shape[2]:
                image = image[:, :, 0:p.channels]

            image = self.apply_render_stamp(image, p.channels)

            images.append(image.flatten())

        # efficient way to copy all AOV images
        render_passes.foreach_set('rect', np.concatenate(images))

    def resolve_update_render_result(self, tile_pos, tile_size, layer_name=""):
        self.rpr_context.resolve()
        self.rpr_context.resolve_extras()

        result = self.rpr_engine.begin_result(*tile_pos, *tile_size, layer=layer_name)
        self._set_render_result(result.layers[0].passes)
        self.rpr_engine.end_result(result)

    def depsgraph_objects(self, depsgraph: bpy.types.Depsgraph, with_camera=False):
        """ Iterates evaluated objects in depsgraph with ITERATED_OBJECT_TYPES """

        object_types = ITERATED_OBJECT_TYPES if not with_camera else (ITERATED_OBJECT_TYPES + ('CAMERA',))

        for obj in depsgraph.objects:
            if obj.type in object_types:
                yield obj

    def depsgraph_instances(self, depsgraph: bpy.types.Depsgraph):
        """ Iterates evaluated instances in depsgraph with ITERATED_OBJECT_TYPES """

        # Comment from Depsgrapgh.object_instances description:
        # WARNING: only use this as an iterator, never as a sequence, and do not keep any references to its items
        for instance in depsgraph.object_instances:
            if instance.is_instance and instance.object.type in ITERATED_OBJECT_TYPES:
                yield instance

    def sync_motion_blur(self, depsgraph: bpy.types.Depsgraph):
        """ """

        def set_motion_blur(rpr_object, prev_matrix, cur_matrix):
            velocity = (prev_matrix - cur_matrix).to_translation()
            rpr_object.set_linear_motion(*velocity)

            mul_diff = prev_matrix @ cur_matrix.inverted()

            quaternion = mul_diff.to_quaternion()
            if quaternion.axis.length > 0.5:
                rpr_object.set_angular_motion(*quaternion.axis, quaternion.angle)
            else:
                rpr_object.set_angular_motion(1.0, 0.0, 0.0, 0.0)

            if not isinstance(rpr_object, pyrpr.Camera):
                scale_motion = mul_diff.to_scale() - mathutils.Vector((1, 1, 1))
                rpr_object.set_scale_motion(*scale_motion)

        cur_matrices = {}

        # getting current frame matrices
        for obj in self.depsgraph_objects(depsgraph, with_camera=True):
            if not obj.rpr.motion_blur:
                continue

            key = object.key(obj)
            rpr_object = self.rpr_context.objects.get(key, None)
            if not rpr_object or not isinstance(rpr_object, (pyrpr.Shape, pyrpr.AreaLight, pyrpr.Camera)):
                continue

            cur_matrices[key] = obj.matrix_world.copy()

        for inst in self.depsgraph_instances(depsgraph):
            if not inst.parent.rpr.motion_blur:
                continue

            key = instance.key(inst)
            rpr_object = self.rpr_context.objects.get(key, None)
            if not rpr_object or not isinstance(rpr_object, (pyrpr.Shape, pyrpr.AreaLight)):
                continue

            cur_matrices[key] = inst.matrix_world.copy()

        if not cur_matrices:
            return

        cur_frame = depsgraph.scene.frame_current
        prev_frame = cur_frame - depsgraph.scene.frame_step

        # set to previous frame and calculate motion blur data
        self.rpr_engine.frame_set(prev_frame, 0.0)
        try:
            for obj in self.depsgraph_objects(depsgraph, with_camera=True):
                key = object.key(obj)
                cur_matrix = cur_matrices.get(key, None)
                if cur_matrix is None:
                    continue

                set_motion_blur(self.rpr_context.objects[key], obj.matrix_world, cur_matrix)

            for inst in self.depsgraph_instances(depsgraph):
                key = instance.key(inst)
                cur_matrix = cur_matrices.get(key, None)
                if cur_matrix is None:
                    continue

                set_motion_blur(self.rpr_context.objects[key], inst.matrix_world, cur_matrix)

        finally:
            # restore current frame
            self.rpr_engine.frame_set(cur_frame, 0.0)
