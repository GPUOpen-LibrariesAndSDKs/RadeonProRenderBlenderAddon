''' Engine is the functionality of the rendering process, 
maintains context, processes, etc.

Other modules in this directory could be viewport, etc.
'''

''' main Render object '''

import weakref
import numpy as np

import bpy
import mathutils
import pyrpr

from .context import RPRContext
from rprblender.export import object, instance
from rprblender.properties.view_layer import RPR_ViewLayerProperites
from . import image_filter

from rprblender.utils import logging
log = logging.Log(tag='Engine')


ITERATED_OBJECT_TYPES = ('MESH', 'LIGHT', 'CURVE', 'FONT', 'SURFACE', 'META')


class Engine:
    """ This is the basic Engine class """

    TYPE = None

    # RPRContext class
    _RPRContext = RPRContext

    def __init__(self, rpr_engine):
        self.rpr_engine = weakref.proxy(rpr_engine)
        self.rpr_context = self._RPRContext()
        self.rpr_context.engine_type = self.TYPE

        # image filter
        self.image_filter = None

    def _set_render_result(self, render_passes: bpy.types.RenderPasses, apply_image_filter):
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

            if p.name == "Combined":
                if apply_image_filter and self.image_filter:
                    image = self.image_filter.get_data()
                else:
                    image = self.rpr_context.get_image()

            elif p.name == "Color":
                image = self.rpr_context.get_image(pyrpr.AOV_COLOR)

            else:
                aov = next((aov for aov in RPR_ViewLayerProperites.aovs_info
                            if aov['name'] == p.name), None)
                if aov and self.rpr_context.is_aov_enabled(aov['rpr']):
                    image = self.rpr_context.get_image(aov['rpr'])
                else:
                    log.warn(f"AOV '{p.name}' is not enabled in rpr_context "
                             f"or not found in aovs_info")
                    image = zeros_image(p.channels)

            if p.channels != image.shape[2]:
                image = image[:, :, 0:p.channels]

            if p.name == "Object Index":
                # De-normalizing Object ID to match blender values
                # it appears values > 256 get clipped.
                image = image * 255.0

            images.append(image.flatten())

        # efficient way to copy all AOV images
        render_passes.foreach_set('rect', np.concatenate(images))

    def update_render_result(self, tile_pos, tile_size, layer_name="",
                             apply_image_filter=False):
        result = self.rpr_engine.begin_result(*tile_pos, *tile_size, layer=layer_name)
        self._set_render_result(result.layers[0].passes, apply_image_filter)
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

    def setup_image_filter(self, settings):
        if self.image_filter and self.image_filter.settings == settings:
            return False

        if settings['enable']:
            if not self.image_filter:
                self._enable_image_filter(settings)

            elif self.image_filter.settings['resolution'] == settings['resolution'] \
                    and self.image_filter.settings['filter_type'] == settings['filter_type'] \
                    and self.image_filter.settings['filter_type'] != 'ML':
                self._update_image_filter(settings)

            else:
                # recreating filter
                self._disable_image_filter()
                self._enable_image_filter(settings)

        elif self.image_filter:
            self._disable_image_filter()

        return True

    def _enable_image_filter(self, settings):
        width, height = settings['resolution']

        # Enabling AOV's which are used in all filters
        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)

        if settings['filter_type'] == 'BILATERAL':
            self.rpr_context.enable_aov(pyrpr.AOV_WORLD_COORDINATE)
            self.rpr_context.enable_aov(pyrpr.AOV_OBJECT_ID)
            self.rpr_context.enable_aov(pyrpr.AOV_SHADING_NORMAL)

            inputs = {'color', 'normal', 'world_coordinate', 'object_id'}
            sigmas = {
                'color': settings['color_sigma'],
                'normal': settings['normal_sigma'],
                'world_coordinate': settings['p_sigma'],
                'object_id': settings['trans_sigma'],
            }
            params = {'radius': settings['radius']}
            self.image_filter = image_filter.ImageFilterBilateral(
                self.rpr_context.context, inputs, sigmas, params, width, height)

        elif settings['filter_type'] == 'EAW':
            self.rpr_context.enable_aov(pyrpr.AOV_WORLD_COORDINATE)
            self.rpr_context.enable_aov(pyrpr.AOV_OBJECT_ID)
            self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)
            self.rpr_context.enable_aov(pyrpr.AOV_SHADING_NORMAL)

            inputs = {'color', 'normal', 'depth', 'trans', 'world_coordinate', 'object_id'}
            sigmas = {
                'color': settings['color_sigma'],
                'normal': settings['normal_sigma'],
                'depth': settings['depth_sigma'],
                'trans': settings['trans_sigma'],
            }
            self.image_filter = image_filter.ImageFilterEaw(
                self.rpr_context.context, inputs, sigmas, {}, width, height)

        elif settings['filter_type'] == 'LWR':
            self.rpr_context.enable_aov(pyrpr.AOV_WORLD_COORDINATE)
            self.rpr_context.enable_aov(pyrpr.AOV_OBJECT_ID)
            self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)
            self.rpr_context.enable_aov(pyrpr.AOV_SHADING_NORMAL)

            inputs = {'color', 'normal', 'depth', 'trans', 'world_coordinate', 'object_id'}
            params = {
                'samples': settings['samples'],
                'halfWindow': settings['half_window'],
                'bandwidth': settings['bandwidth'],
            }
            self.image_filter = image_filter.ImageFilterLwr(
                self.rpr_context.context, inputs, {}, params, width, height)

        elif settings['filter_type'] == 'ML':
            inputs = {'color'}

            if not settings['ml_color_only']:
                self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)
                self.rpr_context.enable_aov(pyrpr.AOV_DIFFUSE_ALBEDO)
                self.rpr_context.enable_aov(pyrpr.AOV_SHADING_NORMAL)
                inputs |= {'normal', 'depth', 'albedo'}

            self.image_filter = image_filter.ImageFilterML(
                self.rpr_context.context, inputs, {}, {}, width, height)

        self.image_filter.settings = settings

    def _disable_image_filter(self):
        self.image_filter = None

    def _update_image_filter(self, settings):
        self.image_filter.settings = settings

        if settings['filter_type'] == 'BILATERAL':
            self.image_filter.update_sigma('color', settings['color_sigma'])
            self.image_filter.update_sigma('normal', settings['normal_sigma'])
            self.image_filter.update_sigma('world_coordinate', settings['p_sigma'])
            self.image_filter.update_sigma('object_id', settings['trans_sigma'])
            self.image_filter.update_param('radius', settings['radius'])

        elif settings['filter_type'] == 'EAW':
            self.image_filter.update_sigma('color', settings['color_sigma'])
            self.image_filter.update_sigma('normal', settings['normal_sigma'])
            self.image_filter.update_sigma('depth', settings['depth_sigma'])
            self.image_filter.update_sigma('trans', settings['trans_sigma'])

        elif settings['filter_type'] == 'LWR':
            self.image_filter.update_param('samples', settings['samples'])
            self.image_filter.update_param('halfWindow', settings['half_window'])
            self.image_filter.update_param('bandwidth', settings['bandwidth'])

    def update_image_filter_inputs(self, tile_pos=(0, 0)):
        color = self.rpr_context.get_image()

        filter_type = self.image_filter.settings['filter_type']
        if filter_type == 'BILATERAL':
            world = self.rpr_context.get_image(pyrpr.AOV_WORLD_COORDINATE)
            object_id = self.rpr_context.get_image(pyrpr.AOV_OBJECT_ID)
            shading = self.rpr_context.get_image(pyrpr.AOV_SHADING_NORMAL)

            inputs = {
                'color': color,
                'normal': shading,
                'world_coordinate': world,
                'object_id': object_id,
            }

        elif filter_type == 'EAW':
            world = self.rpr_context.get_image(pyrpr.AOV_WORLD_COORDINATE)
            object_id = self.rpr_context.get_image(pyrpr.AOV_OBJECT_ID)
            depth = self.rpr_context.get_image(pyrpr.AOV_DEPTH)
            shading = self.rpr_context.get_image(pyrpr.AOV_SHADING_NORMAL)

            inputs = {
                'color': color,
                'normal': shading,
                'depth': depth,
                'trans': object_id,
                'world_coordinate': world,
                'object_id': object_id,
            }

        elif filter_type == 'LWR':
            world = self.rpr_context.get_image(pyrpr.AOV_WORLD_COORDINATE)
            object_id = self.rpr_context.get_image(pyrpr.AOV_OBJECT_ID)
            depth = self.rpr_context.get_image(pyrpr.AOV_DEPTH)
            shading = self.rpr_context.get_image(pyrpr.AOV_SHADING_NORMAL)

            inputs = {
                'color': color,
                'normal': shading,
                'depth': depth,
                'trans': object_id,
                'world_coordinate': world,
                'object_id': object_id,
            }

        elif filter_type == 'ML':
            inputs = {'color': color}

            if not self.image_filter.settings['ml_color_only']:
                inputs['depth'] = self.rpr_context.get_image(pyrpr.AOV_DEPTH)
                inputs['albedo'] = self.rpr_context.get_image(pyrpr.AOV_DIFFUSE_ALBEDO)
                inputs['normal'] = self.rpr_context.get_image(pyrpr.AOV_SHADING_NORMAL)

        else:
            raise ValueError("Incorrect filter type", filter_type)

        for input_id, data in inputs.items():
            self.image_filter.update_input(input_id, data, tile_pos)
