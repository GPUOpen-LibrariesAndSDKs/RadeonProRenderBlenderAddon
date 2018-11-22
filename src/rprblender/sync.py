import functools
import math
import sys

import bpy
import numpy as np
import pyrpr

import rprblender
from rprblender import logging, versions
from rprblender.core.nodes import log_mat, Material, ShaderType
from rprblender.export import extract_mesh, get_blender_mesh, prev_world_matrices_cache
from rprblender.helpers import CallLogger, get_user_settings
from rprblender.properties import environment_override_categories
from rprblender.timing import TimedContext
import rprblender.core.image

import mathutils

from rprblender import lights


call_logger = CallLogger(tag='export.sync.scene')


class EnvironmentOverride:
    core_override_id = {"background": pyrpr.SCENE_ENVIRONMENT_OVERRIDE_BACKGROUND,
                        "reflection": pyrpr.SCENE_ENVIRONMENT_OVERRIDE_REFLECTION,
                        "refraction": pyrpr.SCENE_ENVIRONMENT_OVERRIDE_REFRACTION,
                        "transparency": pyrpr.SCENE_ENVIRONMENT_OVERRIDE_TRANSPARENCY,
                        }

    def __init__(self, category: str, scene_synced, file_name, core_environment, core_image):
        self.category = category
        self.core_environment = core_environment
        self.scene_synced = scene_synced
        self.name = file_name
        self.image = core_image

    @property
    def is_enabled(self):
        return self.scene_synced.is_environment_override_enabled(self.category, self)

    def enable(self):
        if not self.core_override_id[self.category]:
            return
        self.scene_synced.add_scene_environment_override(self.core_override_id[self.category], self.core_environment)

    def disable(self):
        self.scene_synced.remove_scene_environment_override(self.core_override_id[self.category])

    def set_rotation(self, rotation_gizmo):
        rot = (-rotation_gizmo[0], -rotation_gizmo[1], -rotation_gizmo[2])
        euler = mathutils.Euler(rot)
        mat_rot = np.array(euler.to_matrix(), dtype=np.float32)
        fixup = np.array([[1, 0, 0],
                          [0, 0, 1],
                          [0, 1, 1]], dtype=np.float32)
        matrix = np.identity(4, dtype=np.float32)
        matrix[:3, :3] = np.dot(fixup, mat_rot)

        self.core_environment.set_transform(matrix, False)


class SceneSynced:

    @property
    def context(self):
        return self.render_device.context

    @property
    def material_system(self):
        return self.render_device.material_system

    @property
    def x_context(self):
        return self.render_device.x_context

    def __init__(self, render_device, settings):
        self.render_device = render_device

        self.core_scene = None  # type: pyrpr.Scene

        self.settings = settings
        self.render_camera = None  # type: RenderCamera

        self.objects_synced = {}  # type: dict[ObjectSynced]
        self.meshes = set()
        self.volumes = set()
        self.portal_lights_meshes = set()
        self.core_render_camera = None
        self.lamps = {}

        self.materialsNodes = {}
        self.activeMaterialKey = None

        self.has_error = False

        self.ibls_attached = set()
        self.environment_overrides = dict([(key, None) for key in environment_override_categories])

    @call_logger.logged
    def __del__(self):
        self.destroy()

    @call_logger.logged
    def destroy(self):

        # Delete material nodes BEFORE deleting shapes
        # deleting materials uses imlicitly shapes object
        # so shapes must exists during deleting material nodes
        self.environment_overrides.clear()
        self.ibls_attached.clear()
        if self.core_scene:
            self.core_scene.clear()
        self.materialsNodes.clear()
        for mesh in self.meshes:
            if hasattr(mesh, 'x_material') and mesh.x_material:
                mesh.x_material.detach(mesh)
        self.meshes.clear()
        self.volumes.clear()
        self.portal_lights_meshes.clear()
        self.lamps.clear()
        self.objects_synced.clear()
        self.core_render_camera = None
        self.core_scene = None

    def get_core_context(self):
        return self.context

    def get_uber_rprx_context(self):
        return self.x_context

    def get_core_scene(self):
        return self.core_scene

    def set_scene_environment(self, light):
        self.core_scene.attach(light)

    def remove_scene_environment(self, light):
        self.core_scene.detach(light)

    def add_scene_environment_override(self, core_flag, override):
        self.core_scene.add_environment(core_flag, override)

    def remove_scene_environment_override(self, core_flag):
        self.core_scene.remove_environment(core_flag)

    def get_material_system(self):
        return self.material_system

    def add_synced_obj(self, obj_key, core_obj):
        self.objects_synced[obj_key] = ObjectSynced(core_obj)

    def clear_synced_obj(self, obj_key):
        del self.objects_synced[obj_key]

    def get_synced_obj(self, obj_key):
        return self.objects_synced[obj_key]

    def get_core_obj(self, obj_key):
        return self.objects_synced[obj_key].core_obj

    def make_core_scene(self):
        self.core_scene = pyrpr.Scene(self.context)
        self.context.set_scene(self.core_scene)
        self.reset_scene()

    @call_logger.logged
    def reset_scene(self):

        # materials should be deleted before deleting shapes
        # because it implicitly uses shapes object
        self.materialsNodes = {}

        self.core_scene.clear()

        self.meshes = set()
        self.volumes = set()
        self.portal_lights_meshes = set()
        self.lamps = {}
        self.objects_synced = {}

        self.ibls_attached = set()
        self.background = None

        self.setup_core_camera()

    def setup_core_camera(self):
        logging.debug('setup_core_camera: ', self.render_camera, tag='render.camera')

        camera = pyrpr.Camera(self.context)
        self.core_render_camera = camera

        mode = {
            'ORTHO': pyrpr.CAMERA_MODE_ORTHOGRAPHIC,
            'PERSP': pyrpr.CAMERA_MODE_PERSPECTIVE,
            'PANO': pyrpr.CAMERA_MODE_LATITUDE_LONGITUDE_360,
        }.get(self.render_camera.type, None)

        self.camera_zoom = None
        self.camera_aspect = self.render_camera.aspect

        if 'CUBEMAP' == self.render_camera.type:
            self.update_camera_transform(camera, self.render_camera.matrix_world)
            if self.render_camera.stereo:
                mode = pyrpr.CAMERA_MODE_CUBEMAP_STEREO
            else:
                mode = pyrpr.CAMERA_MODE_CUBEMAP
            self.camera_zoom = self.render_camera.zoom
        if 'SPHERICAL_PANORAMA' == self.render_camera.type:
            self.update_camera_transform(camera, self.render_camera.matrix_world)
            if self.render_camera.stereo:
                mode = pyrpr.CAMERA_MODE_LATITUDE_LONGITUDE_STEREO
            else:
                mode = pyrpr.CAMERA_MODE_LATITUDE_LONGITUDE_360
            self.camera_zoom = self.render_camera.zoom

        if 'PERSP' == self.render_camera.type:
            self.update_camera_transform(camera, self.render_camera.matrix_world)
            camera.set_lens_shift(*self.render_camera.shift)

            logging.debug('camera.focal_length: ', self.render_camera.lens)
            logging.debug('camera.sensor_size: %s' % (self.render_camera.sensor_size,))
            camera.set_focal_length(self.render_camera.lens)
            camera.set_sensor_size(*self.render_camera.sensor_size)

            if self.render_camera.dof_enable:
                fd = self.render_camera.dof_focus_distance

                logging.debug('camera.dof_f_stop: ', self.render_camera.dof_f_stop)
                logging.debug('camera.dof_blades: ', self.render_camera.dof_blades)
                logging.debug('camera.dof_focus_distance (m): ', fd)

                camera.set_f_stop(self.render_camera.dof_f_stop)
                camera.set_aperture_blades(self.render_camera.dof_blades)
                camera.set_focus_distance(max(fd, 0.001))
            else:
                camera.set_f_stop(sys.float_info.max)

        elif 'ORTHO' == self.render_camera.type:
            self.update_camera_transform_ortho(camera, self.render_camera.matrix_world, self.render_camera.ortho_depth)
            camera.set_lens_shift(*self.render_camera.shift)
            camera.set_ortho(self.render_camera.ortho_width, self.render_camera.ortho_height)

        logging.debug('motion_blur: ', self.render_camera.motion_blur_enable, self.render_camera.motion_blur_exposure)
        if self.render_camera.motion_blur_enable:
            camera.set_exposure(self.render_camera.motion_blur_exposure)
            if self.render_camera.prev_matrix_world is not None:
                mat = mathutils.Matrix(self.render_camera.matrix_world)
                prev_mat = mathutils.Matrix(self.render_camera.prev_matrix_world)

                quat = (prev_mat * mat.inverted()).to_quaternion();
                camera.set_angular_motion(quat.axis.x, quat.axis.y, quat.axis.z, quat.angle)
                trans = (prev_mat - mat).to_translation()
                camera.set_linear_motion(trans.x, trans.y, trans.z)
        
        camera.set_mode(mode)
        self.core_scene.set_camera(camera)

    def create_environment_light(self, color=None, image=None, ibl_map=None):
        ibl = lights.EnvironmentLight(self)

        for obj_key in self.portal_lights_meshes:
            ibl.attach_portal(self.core_scene, self.get_synced_obj(obj_key).core_obj)

        if color is not None:
            ibl.set_image_data(np.full((2, 2, 4), tuple(color) + (1,), dtype=np.float32))
        elif image is not None:
            ibl.set_image(image)
        elif ibl_map is not None:
            ibl.set_image(self.get_core_environment_image_for_blender_image(ibl_map))

        return ibl

    def create_environment_override(self, category, ibl_map):
        core_image = self.get_core_environment_image_for_blender_image(ibl_map)
        return self.create_environment_override_from_core_image(category, ibl_map, core_image)

    def create_environment_override_from_core_image(self, category, name, core_image):
        core_light = self._make_core_environment_light_from_core_image(self.context, core_image)
        return EnvironmentOverride(category, self, name, core_light, core_image=core_image)

    def create_environment_override_from_color(self, category, color):
        im = np.full((2, 2, 4), tuple(color) + (1,), dtype=np.float32)
        ibl, image = self._make_core_environment_light_from_image_data(im)
        return EnvironmentOverride(category, self, '', ibl, core_image=image)

    def set_environment_override(self, category, override):
        if override:
            if self.environment_overrides.get(category):
                self.environment_overrides[category].disable()
                del (self.environment_overrides[category])
            self.environment_overrides[category] = override
            override.enable()

    def remove_environment_override(self, category):
        if self.environment_overrides[category]:
            self.environment_overrides[category].disable()
        del self.environment_overrides[category]

    def is_environment_override_enabled(self, category, override):
        return self.environment_overrides.get(category) and self.environment_overrides[category] == override

    def get_core_environment_image_for_blender_image(self, image):
        """ Environment has an issue that it's flipped the other way then usual textures without a way
        to use ibl transform to fix it - thus we need a separate method for loading it's image"""

        try:
            if not versions.is_blender_support_ibl_image():
                # in Blender before 2.79 ibl had filepath, newer use Image reference
                return rprblender.core.image.create_core_image_from_image_file_via_blender(
                    self.context, image, flipud=False)

            # TODO: RPR(as of 1.272) IBL seems to be flipped vertically and this can't be fixed by IBL transform
            # - scaling by -1 doesn't work, only rotation is used. So we extract pixels from Blender image
            # and flip them(again, actuall - they are once flipped inside to match RPR's CreateImageFromFile)
            img = pyrpr.ImageData(self.context, rprblender.core.image.extract_pixels_from_blender_image(image, flipud=True))
        except Exception as e:
            logging.warn("Cant's read environment image: ", image, ", reason:", str(e), tag="sync")
            img = pyrpr.ImageData(self.context, np.full((2, 2, 4), (1, 0, 1, 1,), dtype=np.float32))
        return img

    def extract_image(self, image):
        im = self._extract_image_pixels(image).reshape(image.size[1], image.size[0], 4)
        return im

    def _extract_image_pixels(self, image):
        return np.array(image.pixels[:], dtype=np.float32)

    def _make_core_environment_light_from_image_data(self, image: np.ndarray):
        with TimedContext("make_core_envmap"):
            core_image = pyrpr.ImageData(self.context, image)
            ibl = self._make_core_environment_light_from_core_image(self.context, core_image)

        return ibl, core_image

    def _make_core_environment_light_from_core_image(self, context, core_image):
        ibl = pyrpr.EnvironmentLight(context)
        ibl.set_image(core_image)
        return ibl

    def add_lamp(self, obj_key, blender_obj):
        logging.debug('add_lamp', obj_key, tag='sync')
        assert obj_key not in self.lamps

        light = lights.Light(blender_obj.data, self.get_material_system())
        light.set_transform(np.array(blender_obj.matrix_world, dtype=np.float32))
        light.attach(self.get_core_scene())
        self.lamps[obj_key] = light

        self.add_synced_obj(obj_key, light.get_core_obj())

    def remove_lamp(self, obj_key):
        logging.debug('remove_lamp', obj_key, tag='sync')
        assert obj_key in self.objects_synced
        assert obj_key in self.lamps

        light = self.lamps[obj_key]

        if not self.get_synced_obj(obj_key).hidden:
            light.detach(self.get_core_scene())

        self.clear_synced_obj(obj_key)
        del self.lamps[obj_key]

    def hide_lamp(self, obj_key):
        logging.debug('hide_lamp', obj_key, tag='sync')

        assert obj_key in self.objects_synced
        assert obj_key in self.lamps

        self.get_synced_obj(obj_key).hidden = True

        self.lamps[obj_key].detach(self.get_core_scene())

    def show_lamp(self, obj_key):
        logging.debug('show_lamp', obj_key, tag='sync')

        assert obj_key in self.objects_synced

        obj_synced = self.get_synced_obj(obj_key)

        if not obj_synced.hidden:
            return

        logging.debug('show_mesh: reattaching', )

        obj_synced.hidden = False

        self.lamps[obj_key].attach(self.get_core_scene())

    @call_logger.logged
    def update_camera_transform_ortho(self, camera, matrix_world, depth):
        m = matrix_world.reshape(4, 4)  # np.ndarray

        logging.debug("matrix_world:", m, tag='render.camera')

        origin, target, up = self.get_lookat_from_matrix(m)
        logging.debug("frCameraLookAt:", origin, target, up, tag='render.camera')

        dir = target - origin
        origin -= dir * depth * 0.5
        target += dir * depth * 0.5

        camera.look_at(origin, target, up)

    def update_camera_transform(self, camera, matrix_world):
        m = matrix_world.reshape(4, 4)  # np.ndarray
        logging.debug("matrix_world:", m, tag='render.camera')

        origin, target, up = self.get_lookat_from_matrix(m)
        logging.debug("frCameraLookAt:", origin, target, up, tag='render.camera')
        camera.look_at(origin, target, up)

    def get_lookat_from_matrix(self, m):
        origin = m.dot([0, 0, 0, 1])[:3]
        target = m.dot([0, 0, -1, 1])[:3]
        up = m.dot([0, 1, 0, 0])[:3]

        return origin, target, up

    @call_logger.logged
    def add_material(self, key, blender_mat):
        log_mat("add_material : %s (key: %s)" % (blender_mat, key))
        rpr_material = Material(self)
        rpr_material.parse(blender_mat)

        log_mat("node_list:", len(rpr_material.node_list), rpr_material.node_list)

        self.materialsNodes[key] = rpr_material
        if rpr_material.has_error:
            self.has_error = True

    @call_logger.logged
    def remove_material(self, key):
        if key in self.materialsNodes:
            self.materialsNodes.pop(key)

    @call_logger.logged
    def remove_material_from_mesh(self, obj_key, material_key):
        log_mat('remove_material_from_mesh')
        if obj_key not in self.objects_synced:
            return
        shape = self.get_core_obj(obj_key)

        if material_key in self.materialsNodes:
            self.materialsNodes[material_key].detach_from_shape(shape)

        shape.set_material(None)

    @call_logger.logged
    def assign_material_to_mesh(self, mat_key, obj_key):
        log_mat('assign material...')

        if mat_key not in self.materialsNodes:
            logging.debug('material not added:', mat_key, tag='export.sync.scene')
            # log_mat("assign_material_to_mesh : Material (key: %s) not exist: " % mat_key)
            return

        if obj_key not in self.objects_synced:
            logging.debug('object not added:', obj_key, tag='export.sync.scene')
            # log_mat("assign_material_to_mesh : Object (key: %s) not exist: " % obj_key)
            return

        rpr_material = self.materialsNodes[mat_key]
        assert rpr_material

        self._assign_material_to_shape(mat_key, self.get_core_obj(obj_key), rpr_material)

        log_mat("assign_material_to_mesh : set mesh (key: %s) material (key: %s) ok: " % (mat_key, obj_key))

    @call_logger.logged
    def assign_material_to_mesh_instance(self, mat_key, instance_key):
        log_mat('assign_material_to_mesh_instance')

        if mat_key not in self.materialsNodes:
            return

        if instance_key not in self.objects_synced:
            return

        rpr_material = self.materialsNodes[mat_key]
        assert rpr_material

        self._assign_material_to_shape(mat_key, self.get_core_obj(instance_key), rpr_material)

        log_mat(
            "assign_material_to_mesh_instance : set mesh (key: %s) material (key: %s) ok: " % (mat_key, instance_key))

    def commit_materials(self):
        for key in self.materialsNodes.keys():
            self.commit_material(key)

    def commit_material(self, mat_key):
        log_mat('commit material...')

        if mat_key not in self.materialsNodes:
            logging.debug('material not added:', mat_key, tag='export.sync.scene')
            # log_mat("assign_material_to_mesh : Material (key: %s) not exist: " % mat_key)
            return

        # commit the material
        rpr_material = self.materialsNodes[mat_key]
        if rpr_material.shader != None and rpr_material.shader.type == ShaderType.UBER2:
            shader = rpr_material.get_handle()
            shader.commit()

    def _assign_material_to_shape(self, mat_key, shape, rpr_material):
        shader = rpr_material.get_handle()

        shape.set_volume_material(None)
        shape.set_displacement_material(None)

        if rpr_material.shader != None and rpr_material.shader.type == ShaderType.UBER2:
            shader.attach(shape)
        else:

            if shader:
                shader.set_name(rpr_material.name)
                shape.set_material(shader)

            volume = rpr_material.get_volume()
            if volume:
                logging.info('assign volume material: ', mat_key, volume)
                shape.set_volume_material(volume)

            displacement = rpr_material.get_displacement()
            if displacement and displacement[0]:
                logging.info('assign displacement: ', mat_key, displacement)
                shape.set_displacement_material(displacement[0].node.get_handle())
                shape.set_displacement_scale(displacement[1], displacement[2])

    @call_logger.logged
    def remove_material_from_mesh_instance(self, instance_key):
        if instance_key not in self.objects_synced:
            return
        shape = self.get_core_obj(instance_key)
        shape.set_material(None)

    ########################################################################################################################
    # Meshes work
    ########################################################################################################################

    @call_logger.logged
    def add_mesh(self, obj_key, extracted_mesh, matrix_world):
        logging.debug('add mesh:', obj_key, extracted_mesh)

        core_shape = self._core_make_mesh(extracted_mesh)
        core_shape.set_name(extracted_mesh['name'])
        self.core_scene.attach(core_shape)

        self.shape_set_transform(core_shape, matrix_world)
        self.add_synced_obj(obj_key, core_shape)
        self.meshes.add(core_shape)

        # all meshes are set to light group 3 for emissive objects
        core_shape.set_light_group_id(3)

        logging.debug('add mesh done')
        return True

    @call_logger.logged
    def add_volume(self, obj_key, extracted_volume, matrix_world):
        logging.debug('add volume:', obj_key, extracted_volume)

        core_volume = self._core_make_volume(extracted_volume)
        # rprlog("core_make_mesh: done", extracted_mesh)
        core_shape = self.get_core_obj(obj_key)

        core_shape.set_hetero_volume(core_volume)
        self.core_scene.attach(core_volume)
        
        matrix = np.array(matrix_world, dtype=np.float32)
        # volumes must be scaled by 2
        matrix[0,0] *= 2.0
        matrix[1,1] *= 2.0
        matrix[2,2] *= 2.0
        
        if pyrpr.is_transform_matrix_valid(matrix):
            core_volume.set_transform(matrix)
          
        self.volumes.add(core_volume)

        logging.debug('add volume done')
        return True

    def shape_set_transform(self, core_shape, matrix_world):
        matrix = np.array(matrix_world, dtype=np.float32)

        if pyrpr.is_transform_matrix_valid(matrix):
            core_shape.set_transform(matrix)
            return

        self.report_error("invalid matrix supplied: %s" % matrix_world)
        matrix = np.eye(4, dtype=np.float32)
        core_shape.set_transform(matrix)

    @call_logger.logged
    def set_motion_blur(self, obj_key, obj_matrix, prev_obj_matrix, scale):
        if (obj_matrix == prev_obj_matrix):
            self.reset_motion_blur(obj_key)
            return

        logging.debug('obj_matrix', obj_matrix);
        logging.debug('prev_obj_matrix', prev_obj_matrix);

        mul_diff = prev_obj_matrix * obj_matrix.inverted()
        transform_quat = mul_diff.to_quaternion();
        logging.debug('transform_quat', transform_quat, '; axis', transform_quat.axis, '; angle', transform_quat.angle);

        scale_vec = mul_diff.to_scale()
        logging.debug('scale_vec', scale_vec);
        
        translation = (prev_obj_matrix - obj_matrix).to_translation()
        logging.debug('translation', translation);

        velocity = translation * scale
        momentum_axis = transform_quat.axis
        momentum_angle = transform_quat.angle * scale
        momentum_scale = (scale_vec - mathutils.Vector((1, 1, 1))) * scale
        if momentum_axis.length < 0.5:
            momentum_axis.x, momentum_axis.y, momentum_axis.z, momentum_angle = 1.0, 0.0, 0.0, 0.0

        logging.debug('LinearMotion', velocity.x, velocity.y, velocity.z)
        logging.debug('AngularMotion', momentum_axis.x, momentum_axis.y, momentum_axis.z, momentum_angle)
        logging.debug('ScaleMotion', momentum_scale.x, momentum_scale.y, momentum_scale.z)       
        self.get_synced_obj(obj_key).set_motion_blur((velocity.x, velocity.y, velocity.z),
                                                     (momentum_axis.x, momentum_axis.y, momentum_axis.z, momentum_angle),
                                                     (momentum_scale.x, momentum_scale.y, momentum_scale.z))


    @call_logger.logged
    def reset_motion_blur(self, obj_key):
        self.get_synced_obj(obj_key).reset_motion_blur()

    @call_logger.logged
    def mesh_set_shadowcatcher(self, obj_key, value):
        self.get_core_obj(obj_key).set_shadow_catcher(value)

    @call_logger.logged
    def mesh_set_shadows(self, obj_key, value):
        self.get_core_obj(obj_key).set_shadow(value)

    @call_logger.logged
    def mesh_set_visibility(self, obj_key, value):
        self.get_core_obj(obj_key).set_visibility(value)

    @call_logger.logged
    def mesh_set_visibility_in_primary_rays(self, obj_key, value):
        self.get_core_obj(obj_key).set_visibility_primary_only(value)

    @call_logger.logged
    def mesh_set_visibility_in_specular(self, obj_key, value):
        self.get_core_obj(obj_key).set_visibility_in_specular(value)

    @call_logger.logged
    def mesh_set_subdivision(self, obj_key, factor, boundary, crease_weight):
        core_shape = self.core_shape(obj_key)
        core_shape.set_subdivision_factor(factor)
        core_shape.set_subdivision_boundary_interop(boundary)
        core_shape.set_subdivision_crease_weight(crease_weight)

    @call_logger.logged
    def mesh_set_autosubdivision(self, obj_key, factor, boundary, crease_weight):
        core_shape = self.core_shape(obj_key)
        core_shape.set_auto_adapt_subdivision_factor(self.render_device.render_targets.get_frame_buffer('default'), self.core_render_camera, factor)
        core_shape.set_subdivision_boundary_interop(boundary)
        core_shape.set_subdivision_crease_weight(crease_weight)

    @call_logger.logged
    def mesh_attach_portallight(self, obj_key):
        if obj_key in self.portal_lights_meshes:
            return
        self.portal_lights_meshes.add(obj_key)

        logging.info("mesh_attach_portallight: self.ibls_attached {}".format(self.ibls_attached))
        for ibl in self.ibls_attached:
            ibl.attach_portal(self.core_scene, self.core_shape(obj_key))

    def core_shape(self, obj_key):
        return self.get_synced_obj(obj_key).core_obj

    @call_logger.logged
    def mesh_detach_portallight(self, obj_key):
        if obj_key not in self.portal_lights_meshes:
            return
        self.portal_lights_meshes.discard(obj_key)
        logging.info("mesh_detach_portallight: self.ibls_attached {}".format(self.ibls_attached))
        for ibl in self.ibls_attached:
            ibl.detach_portal(self.core_scene, self.get_synced_obj(obj_key).core_obj)

    preview_mesh_data = None

    @staticmethod
    def create_preview_mesh():
        if SceneSynced.preview_mesh_data:
            return

        logging.debug('create_preview_mesh...')

        w = 20
        d = 7
        top = 20
        bottom = -5
        verts = [(-w, 0, top), (-w, 0, bottom),
                 (0, d, top), (0, d, bottom),
                 (w, 0, top), (w, 0, bottom),
                 (0, -d, top), (0, -d, bottom),
                 (-w * 2, -d, top), (-w * 2, -d, bottom),
                 (w * 2, -d, top), (w * 2, -d, bottom),
                 ]
        faces = [(0, 1, 3, 2), (3, 2, 4, 5), (0, 2, 4, 6), (1, 3, 5, 7), (0, 1, 9, 8), (5, 4, 10, 11)]
        mymesh = bpy.data.meshes.new("preview_plane")
        mymesh.from_pydata(verts, [], faces)
        mymesh.update(calc_edges=True)
        uvtex = mymesh.uv_textures.new()
        myobject = bpy.data.objects.new("preview_plane", mymesh)
        myobject.location = (0, 0, 0)
        mesh_for_add = get_blender_mesh(bpy.context.scene, myobject)
        SceneSynced.preview_mesh_data = extract_mesh(mesh_for_add)

        bpy.data.objects.remove(myobject)
        bpy.data.meshes.remove(mymesh)
        bpy.data.meshes.remove(mesh_for_add)

    def add_back_preview(self, is_icon):
        if is_icon:
            return

        logging.debug('add_back_preview...')
        assert SceneSynced.preview_mesh_data

        key = 'preview_temp'

        matrix = mathutils.Matrix()
        matrix.identity()
        self.add_mesh(key, SceneSynced.preview_mesh_data, matrix)
        shape = self.get_core_obj(key)

        shader = pyrpr.MaterialNode(self.get_material_system(), pyrpr.MATERIAL_NODE_DIFFUSE)
        self.add_synced_obj('temp_shader', shader)

        checker = pyrpr.MaterialNode(self.get_material_system(), pyrpr.MATERIAL_NODE_CHECKER_TEXTURE)
        self.add_synced_obj('temp_checker', checker)
        shader.set_input('color', checker)

        shape.set_material(shader)
        logging.debug('add_back_preview ok.')
        return True

    @call_logger.logged
    def remove_mesh(self, obj_key):
        logging.debug('remove_mesh:', obj_key)
        self.remove_shape(obj_key)

    @call_logger.logged
    def add_mesh_instance(self, key, mesh_key, matrix_world, name):
        logging.debug('add_mesh_instance:', key, mesh_key, matrix_world)

        shape = pyrpr.Instance(self.context, self.get_synced_obj(mesh_key).core_obj)
        shape.set_name(name)
        self.core_scene.attach(shape)

        self.shape_set_transform(shape, matrix_world)

        self.add_synced_obj(key, shape)
        self.meshes.add(shape)

    @call_logger.logged
    def remove_mesh_instance(self, obj_key):
        logging.debug('remove_mesh_instance:', obj_key)
        self.remove_shape(obj_key)

    @call_logger.logged
    def remove_shape(self, obj_key):
        if obj_key not in self.objects_synced:
            return

        mesh = self.get_core_obj(obj_key)
        if not self.objects_synced[obj_key].hidden:
            self.core_scene.detach(mesh)

        self.clear_synced_obj(obj_key)
        self.meshes.remove(mesh)

    @call_logger.logged
    def hide_mesh(self, obj_key):
        obj_synced = self.get_synced_obj(obj_key)

        obj_synced.hidden = True
        self.core_scene.detach(self.get_core_obj(obj_key))

    @call_logger.logged
    def show_mesh(self, obj_key):
        obj_synced = self.get_synced_obj(obj_key)
        if not obj_synced.hidden: 
            return

        obj_synced.hidden = False
        self.core_scene.attach(self.get_core_obj(obj_key))


    @call_logger.logged
    def update_mesh_transform(self, key, matrix_world):
        self.update_shape_transform(key, matrix_world)

    @call_logger.logged
    def update_instance_transform(self, key, matrix_world):
        self.update_shape_transform(key, matrix_world)

    @call_logger.logged
    def update_shape_transform(self, key, matrix_world):
        assert key in self.objects_synced

        self.shape_set_transform(self.get_core_obj(key), matrix_world)

    def _core_make_mesh(self, obj):
        logging.debug("core_make_mesh")

        mesh = obj['data']

        vertices = np.ascontiguousarray(mesh['vertices'])
        normals = np.ascontiguousarray(mesh['normals'])

        if mesh.get('uvs', None) is not None:
            uvs = np.ascontiguousarray(mesh['uvs'])
        else:
            uvs = None

        indices = np.ascontiguousarray(mesh['indices'])

        if 'vertex_indices' in mesh:
            vertex_indices = np.ascontiguousarray(mesh['vertex_indices'])
        else:
            vertex_indices = indices

        faces_counts = np.ascontiguousarray(mesh['faces_counts'])
        core_mesh = pyrpr.Mesh(self.context, vertices, normals, uvs,
                               vertex_indices, indices, indices,
                               faces_counts)

        return core_mesh

    def _core_make_volume(self, volume_data):
        logging.debug("core_make_volume")
        
        x ,y, z = volume_data['dimensions']
        size = x * y * z

        grid_data = np.ascontiguousarray(volume_data['density'].reshape(size * 4))
        logging.debug("grid_data_count: ", size * 4)

        indices = np.ascontiguousarray(range(0,size), dtype=np.uint64)
        logging.debug("index_count: ", size)

        core_volume = pyrpr.HeteroVolume(self.context,
            x, y, z,
            indices, pyrpr.HETEROVOLUME_INDICES_TOPOLOGY_I_U64,
            grid_data)

        return core_volume

    @call_logger.logged
    def set_render_camera(self, render_camera):
        self.render_camera = render_camera

        if self.core_scene:
            self.setup_core_camera()

    def report_error(self, message):
        logging.error(message)


class ObjectSynced:
    def __init__(self, core_obj, hidden=False):
        self.core_obj = core_obj
        self.hidden = hidden
        self.motion_blur = False

    def set_motion_blur(self, linear, angular, scale):
        self.motion_blur = True
        self.core_obj.set_linear_motion(*linear)
        self.core_obj.set_angular_motion(*angular)
        self.core_obj.set_scale_motion(*scale)

    def reset_motion_blur(self):
        if not self.motion_blur:
            return
        self.motion_blur = False
        self.core_obj.set_linear_motion(0.0, 0.0, 0.0)
        self.core_obj.set_angular_motion(1.0, 0.0, 0.0, 0.0)
        self.core_obj.set_scale_motion(0.0, 0.0, 0.0)


class RenderCamera:
    type = None  # 'PERSP', 'ORTHO', 'CUBEMAP', 'SPHERICAL_PANORAMA'

    matrix_world = np.identity(4, dtype=np.float32)

    stereo = False

    lens = 32.0  # focal_length
    sensor_size = (36.0, 24.0)
    zoom = 1.0
    aspect = 1.0

    ortho_width = None
    ortho_height = None
    ortho_depth = None

    # dof
    dof_enable = False
    dof_focus_distance = 0
    dof_f_stop = 0
    dof_blades = 0

    # motion blur
    motion_blur_enable = False
    motion_blur_exposure = None  # type: float
    prev_matrix_world = None

    shift = (0, 0)

    def __str__(self):
        return ' '.join(
            ["{}: {}".format(name, getattr(self, name)) for name in [
                'type',
                'stereo',
                'lens', 'sensor_size', 'zoom',
                'matrix_world',
                'ortho_width', 'ortho_height', 'ortho_depth',
                'motion_blur_enable', 'motion_blur_exposure',
                'shift'
            ]])

    def is_same(self, other):
        if not (True
                and self.type == other.type
                and self.stereo == other.stereo
                and np.array_equal(self.matrix_world, other.matrix_world)
                and np.array_equal(self.shift, other.shift)
        
                and np.array_equal(self.sensor_size, other.sensor_size)
                and self.lens == other.lens

                and self.zoom == other.zoom
                and self.ortho_width == other.ortho_width
                and self.ortho_height == other.ortho_height
                and self.ortho_depth == other.ortho_depth
                ):
            return False

        if self.dof_enable != other.dof_enable:
            return False

        if self.dof_enable:
            if not (True
                    and self.dof_focus_distance == other.dof_focus_distance
                    and self.dof_f_stop == other.dof_f_stop
                    and self.dof_blades == other.dof_blades
                    ):
                return False

        if self.motion_blur_enable != other.motion_blur_enable:
            return False

        if self.motion_blur_enable:
            if not (self.motion_blur_exposure == other.motion_blur_exposure):
                return False

        return True


def get_focus_distance(blender_camera):
    if not blender_camera.data.dof_object:
        return blender_camera.data.dof_distance

    obj_pos = blender_camera.data.dof_object.matrix_world.to_translation()
    camera_pos = blender_camera.matrix_world.to_translation()
    direction = obj_pos - camera_pos
    return direction.length


def get_dof_data(camera, blender_camera, settings, is_preview=False):
    if not blender_camera:
        camera.dof_enable = False
        return

    focus_distance = get_focus_distance(blender_camera)
    camera.dof_enable = settings.dof.enable
    if camera.dof_enable:
        camera.dof_f_stop = blender_camera.data.gpu_dof.fstop
        camera.dof_blades = blender_camera.data.gpu_dof.blades
        camera.dof_focus_distance = focus_distance


@call_logger.logged
def extract_render_border_from_scene(scene):
    if scene.render.use_border:
        return (
            (bpy.context.scene.render.border_min_x, bpy.context.scene.render.border_max_x),
            (bpy.context.scene.render.border_min_y, bpy.context.scene.render.border_max_y),
        )


@call_logger.logged
def get_render_resolution_for_border(border, render_resolution):
    if border:
        return int((border[0][1] - border[0][0]) * render_resolution[0]), \
               int((border[1][1] - border[1][0]) * render_resolution[1])
    return render_resolution


@call_logger.logged
def extract_render_camera_from_blender_camera(active_camera: bpy.types.Camera,
                                              render_camera, render_resolution, zoom, settings, scene,
                                              border, view_offset=(0, 0), camera_offset = (0,0)):
    
    data = active_camera.data  # type: bpy.types.Camera

    # Blender defines sensor size either horizontal or vertical, or dependent on dominating resolution
    sensor_fit_horizontal = 'HORIZONTAL' == data.sensor_fit or ('AUTO' == data.sensor_fit
                                                                and render_resolution[0] > render_resolution[1])
    aspect = render_resolution[0] / render_resolution[1]

    if border is not None:
        #TODO: this is not fully correct algorithm here, created bug RPRBLND-442

        # fixup camera to render border - shifting and zooming in to border position and size
        border = np.array(border, dtype=np.float32)
        border_size = border[:, 1] - border[:, 0]

        render_camera.shift = 0.5*(border[:, 1]+border[:, 0]-1)/border_size
        sensor_side = 0 if sensor_fit_horizontal else 1
        # add the camera shift offset, scaled by the size of the crop window
        render_camera.shift += np.array([camera_offset[0] / border_size[0], 
                                         camera_offset[1] / border_size[1] * aspect], dtype=np.float32)
    else:
        # if a camera shift is on simply use that
        render_camera.shift = np.array([camera_offset[0] / zoom, camera_offset[1] * aspect / zoom], dtype=np.float32)

    render_camera.shift += np.array(view_offset)*2/zoom
    
    render_camera.matrix_world = np.array(active_camera.matrix_world, dtype=np.float32)

    get_dof_data(render_camera, active_camera, settings)

    render_camera.motion_blur_enable = settings.motion_blur and data.rpr_camera.motion_blur
    
    if render_camera.motion_blur_enable:
        render_camera.motion_blur_exposure = data.rpr_camera.motion_blur_exposure
        render_camera.prev_matrix_world = np.array(prev_world_matrices_cache[active_camera], dtype=np.float32)

    if settings.camera.override_camera_settings:
        render_camera.type = settings.camera.panorama_type
        render_camera.stereo = settings.camera.stereo
    else:
        logging.debug("data.type:", data.type, tag='sync')
        if 'PERSP' == data.type:
            render_camera.type = 'PERSP'

            render_camera.lens = data.lens
            sensor_width = data.sensor_width * zoom
            sensor_height = data.sensor_height * zoom
            # NOTE: seems like Core doesn't care what is as 'sensor width', only 'height' makes sense
            # i.e. it derives width from height using aspect
            # so in case something changes - those values for width(render_camera.sensor_size[0]) are not tested!
            if sensor_fit_horizontal:
                render_camera.sensor_size = sensor_width, sensor_width / aspect
            else:
                render_camera.sensor_size = sensor_width * aspect, sensor_width

            if border is not None:
                render_camera.sensor_size = np.array(render_camera.sensor_size) * border_size[sensor_side]

        elif 'ORTHO' == data.type:
            render_camera.type = 'ORTHO'

            # see for example, cycle's blender_camera_init, seems like 32 is the sensor size for viewports
            extent = data.ortho_scale * zoom

            if sensor_fit_horizontal:
                render_camera.ortho_width = extent
                render_camera.ortho_height = extent / aspect
            else:
                render_camera.ortho_width = extent * aspect
                render_camera.ortho_height = extent
            render_camera.ortho_depth = data.ortho_scale * zoom

            if border is not None:
                render_camera.ortho_width *= border_size[sensor_side]
                render_camera.ortho_height *= border_size[sensor_side]

        if 'PANO' == data.type:
            render_camera.type = active_camera.data.rpr_camera.panorama_type
            render_camera.stereo = active_camera.data.rpr_camera.stereo
            render_camera.zoom = zoom


def extract_viewport_render_camera(context: bpy.types.Context, settings):
    render_camera = RenderCamera()

    viewport_render_settings = get_user_settings().viewport_render_settings
    render_resolution = viewport_render_settings.get_viewport_resolution(context)
    width, height = render_resolution
    aspect = float(width) / float(height)

    render_camera.aspect = aspect

    is_camera = 'CAMERA' == context.region_data.view_perspective

    if is_camera:
        # see blender/intern/cycles/blender/blender_camera.cpp:blender_camera_from_view (look for 1.41421f)
        zoom = 2 * 2 / (math.sqrt(2) + context.region_data.view_camera_zoom / 50.0) ** 2
        logging.debug("context.region_data.view_camera_zoom:", context.region_data.view_camera_zoom, zoom, tag='sync')
        extract_render_camera_from_blender_camera(context.scene.camera,
                                                  render_camera,
                                                  render_resolution, zoom, context.scene.rpr.render, context.scene,
                                                  border=None,
                                                  view_offset=tuple(context.region_data.view_camera_offset),
                                                  camera_offset=(context.scene.camera.data.shift_x,
                                                                 context.scene.camera.data.shift_y))
    elif 'PERSP' == context.region_data.view_perspective:
        render_camera.type = 'PERSP'
        render_camera.matrix_world = np.array(context.region_data.view_matrix.inverted(), dtype=np.float32)

        render_camera.lens = context.space_data.lens
        # see for example, cycle's blender_camera_init, seems like 32 is the sensor size for viewports
        zoom = 2.0
        sensor_width = 32 * zoom
        if 1 < aspect:
            render_camera.sensor_size = sensor_width, sensor_width / aspect
        else:
            render_camera.sensor_size = sensor_width, sensor_width

    elif 'ORTHO' == context.region_data.view_perspective:
        render_camera.type = 'ORTHO'
        render_camera.matrix_world = np.array(context.region_data.view_matrix.inverted(), dtype=np.float32)

        # see for example, cycle's blender_camera_init, seems like 32 is the sensor size for viewports
        extent_base = context.space_data.region_3d.view_distance * 32.0 / context.space_data.lens
        zoom = 2.0
        extent = zoom * extent_base * 1

        if 1 < aspect:
            render_camera.ortho_width = extent
            render_camera.ortho_height = extent / aspect
        else:
            render_camera.ortho_width = extent * aspect
            render_camera.ortho_height = extent
        render_camera.ortho_depth = zoom * extent_base / 1
    else:
        assert False

    # override dof data
    get_dof_data(render_camera, context.scene.camera if is_camera else None, settings, is_preview=True)

    return render_camera
