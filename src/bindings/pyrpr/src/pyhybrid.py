import numpy as np

import pyrpr

from rprblender.utils import logging
log = logging.Log(tag='hybrid')


def log_unsupported(*msg):
    log.debug("Unsupported", *msg)


# will be used in other modules to check if hybrid is enabled
enabled = True

UNSUPPORTED_CONTEXT_PARAMETERS = {
    pyrpr.CONTEXT_MAX_DEPTH_DIFFUSE,
    pyrpr.CONTEXT_MAX_DEPTH_GLOSSY,
    pyrpr.CONTEXT_MAX_DEPTH_REFRACTION,
    pyrpr.CONTEXT_MAX_DEPTH_SHADOW,
    pyrpr.CONTEXT_MAX_DEPTH_GLOSSY_REFRACTION,
    pyrpr.CONTEXT_RADIANCE_CLAMP,
    pyrpr.CONTEXT_RAY_CAST_EPISLON,

    pyrpr.CONTEXT_ADAPTIVE_SAMPLING_TILE_SIZE,
    pyrpr.CONTEXT_ADAPTIVE_SAMPLING_MIN_SPP,
    pyrpr.CONTEXT_ADAPTIVE_SAMPLING_THRESHOLD,
    pyrpr.CONTEXT_FRAMECOUNT,

    pyrpr.CONTEXT_PREVIEW,
    pyrpr.CONTEXT_RENDER_MODE,

    pyrpr.CONTEXT_IMAGE_FILTER_TYPE,
    pyrpr.CONTEXT_IMAGE_FILTER_BOX_RADIUS,
    pyrpr.CONTEXT_IMAGE_FILTER_GAUSSIAN_RADIUS,
    pyrpr.CONTEXT_IMAGE_FILTER_TRIANGLE_RADIUS,
    pyrpr.CONTEXT_IMAGE_FILTER_MITCHELL_RADIUS,
    pyrpr.CONTEXT_IMAGE_FILTER_LANCZOS_RADIUS,
    pyrpr.CONTEXT_IMAGE_FILTER_BLACKMANHARRIS_RADIUS,
}

SUPPORTED_MATERIAL_NODES = {
    pyrpr.MATERIAL_NODE_NORMAL_MAP,
    pyrpr.MATERIAL_NODE_IMAGE_TEXTURE,
    pyrpr.MATERIAL_NODE_BUMP_MAP,
    pyrpr.MATERIAL_NODE_ARITHMETIC,
    pyrpr.MATERIAL_NODE_CONSTANT_TEXTURE,
    pyrpr.MATERIAL_NODE_UBERV2,
    pyrpr.MATERIAL_NODE_EMISSIVE
}

SUPPORTED_AOVS = {
    pyrpr.AOV_COLOR,
    pyrpr.AOV_DEPTH,
    pyrpr.AOV_UV,
    pyrpr.AOV_OBJECT_ID,
    pyrpr.AOV_MATERIAL_IDX,
    pyrpr.AOV_WORLD_COORDINATE,
    pyrpr.AOV_SHADING_NORMAL,
    pyrpr.AOV_DIFFUSE_ALBEDO,
    pyrpr.AOV_BACKGROUND,
}


class Context(pyrpr.Context):
    def set_parameter(self, key, param):
        if key == pyrpr.CONTEXT_ITERATIONS:
            self.parameters[key] = param
            return

        if key in UNSUPPORTED_CONTEXT_PARAMETERS:
            log_unsupported(f"Context.set_parameter({key})")
            return

        super().set_parameter(key, param)

    def render(self):
        iterations = self.parameters.get(pyrpr.CONTEXT_ITERATIONS, 1)
        for _ in range(iterations):
            super().render()

    def attach_aov(self, aov, frame_buffer):
        if aov in self.aovs:
            self.detach_aov(aov)

        self.aovs[aov] = frame_buffer
        frame_buffer.aov = aov
        if aov in SUPPORTED_AOVS:
            pyrpr.ContextSetAOV(self, aov, frame_buffer)
        else:
            log_unsupported(f"Context.attach_aov({aov})")

    def detach_aov(self, aov):
        self.aovs[aov].aov = None
        if aov in SUPPORTED_AOVS:
            pyrpr.ContextSetAOV(self, aov, None)

        del self.aovs[aov]


class Light(pyrpr.Light):
    def set_group_id(self, group_id):
        log_unsupported("Light.set_group_id()")


class IESLight(pyrpr.PointLight, Light):
    # IESLight is not supported, that's why we change it to PointLight
    def set_image_from_file(self, image_path, nx, ny):
        pass


class PointLight(pyrpr.PointLight, Light):
    pass


class SpotLight(pyrpr.SpotLight, Light):
    pass


class DirectionalLight(pyrpr.DirectionalLight, Light):
    def set_shadow_softness_angle(self, angle):
        log_unsupported("DirectionalLight.set_shadow_softness_angle()")
        pass


class AreaLight(pyrpr.AreaLight, Light):
    def __init__(self, mesh, material_system):
        self.mesh = mesh
        self.material_system = material_system

        self.color_node = MaterialNode(self.material_system, pyrpr.MATERIAL_NODE_EMISSIVE)
        self.color_node.set_input(pyrpr.MATERIAL_INPUT_COLOR, 1.0)

        self.mesh.set_material(self.color_node)

    def set_radiant_power(self, r, g, b):
        self.color_node.set_input(pyrpr.MATERIAL_INPUT_COLOR, (r, g, b))

    def set_image(self, image):
        if image:
            image_node = MaterialNode(self.material_system, pyrpr.MATERIAL_NODE_IMAGE_TEXTURE)
            image_node.set_input(pyrpr.MATERIAL_INPUT_DATA, image)
            self.color_node.set_input(pyrpr.MATERIAL_INPUT_COLOR, image_node)
        else:
            self.color_node.set_input(pyrpr.MATERIAL_INPUT_COLOR, 1.0)


class EnvironmentLight(pyrpr.EnvironmentLight, Light):
    def set_color(self, r, g, b):
        img = pyrpr.ImageData(self.context,
                              np.full((64, 64, 4), (r, g, b, 1.0), dtype=np.float32))
        self.set_image(img)


class Camera(pyrpr.Camera):
    def set_lens_shift(self, shiftx, shifty):
        log_unsupported("Camera.set_lens_shift()")
        pass

    def set_aperture_blades(self, num_blades):
        log_unsupported("Camera.set_aperture_blades()")
        pass

    def set_angular_motion(self, x, y, z, w):
        log_unsupported("Camera.set_angular_motion()")
        pass

    def set_linear_motion(self, x, y, z):
        log_unsupported("Camera.set_linear_motion()")
        pass

    def set_exposure(self, exposure):
        log_unsupported("Camera.set_exposure()")
        pass


class MaterialNode(pyrpr.MaterialNode):
    def set_input(self, name, value):
        if isinstance(value, EmptyMaterialNode):
            if self.type != pyrpr.MATERIAL_NODE_ARITHMETIC:
                return

            value = 0.0

        if self.type == pyrpr.MATERIAL_NODE_UBERV2 \
            and name in (
                pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_WEIGHT,
                pyrpr.MATERIAL_INPUT_UBER_BACKSCATTER_COLOR,
                pyrpr.MATERIAL_INPUT_UBER_REFLECTION_NORMAL,
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_CAUSTICS,
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_NORMAL,
                pyrpr.MATERIAL_INPUT_UBER_SHEEN,
                pyrpr.MATERIAL_INPUT_UBER_SHEEN_TINT,
                pyrpr.MATERIAL_INPUT_UBER_SHEEN_WEIGHT,
                pyrpr.MATERIAL_INPUT_UBER_COATING_TRANSMISSION_COLOR,
                pyrpr.MATERIAL_INPUT_UBER_COATING_THICKNESS,
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_ABSORPTION_DISTANCE,
                pyrpr.MATERIAL_INPUT_UBER_REFRACTION_ABSORPTION_COLOR,
                pyrpr.MATERIAL_INPUT_UBER_EMISSION_MODE,
        ):
            log_unsupported(f"MaterialNode.set_input({name})", self.type)
            return

        if self.type == pyrpr.MATERIAL_NODE_IMAGE_TEXTURE and name == pyrpr.MATERIAL_INPUT_UV:
            log_unsupported(f"MaterialNode.set_input({name})", self.type)
            return

        try:
            super().set_input(name, value)

        except pyrpr.CoreError as e:
            if e.status in (pyrpr.ERROR_UNSUPPORTED, pyrpr.ERROR_INVALID_PARAMETER):
                log.warn(e, self.type)
                return

            raise


class EmptyMaterialNode(MaterialNode):
    def __init__(self, material_type):
        self.type = material_type

    def delete(self):
        pass

    def set_name(self, name):
        pass

    def set_input(self, name, value):
        pass


class Shape(pyrpr.Shape):
    def set_light_group_id(self, group_id):
        log_unsupported("Shape.set_light_group_id()")
        pass

    def set_visibility_primary_only(self, visible):
        log_unsupported("Shape.set_visibility_primary_only()")
        pass

    def set_visibility_ex(self, visibility_type, visible):
        log_unsupported("Shape.set_visibility_ex()")
        pass

    def set_visibility(self, visible):
        log_unsupported("Shape.set_visibility()")
        pass

    def set_shadow_catcher(self, shadow_catcher):
        log_unsupported("Shape.set_shadow_catcher()")
        pass

    def set_reflection_catcher(self, reflection_catcher):
        log_unsupported("Shape.set_reflection_catcher()")
        pass

    def set_volume_material(self, node):
        log_unsupported("Shape.set_volume_material()")
        pass

    def set_displacement_material(self, node):
        log_unsupported("Shape.set_displacement_material()")
        pass

    def set_hetero_volume(self, hetero_volume):
        log_unsupported("Shape.set_hetero_volume()")
        pass

    def set_material(self, material):
        if isinstance(material, EmptyMaterialNode):
            material = None

        super().set_material(material)

    def set_material_faces(self, material, face_indices: np.array):
        log_unsupported("Shape.set_material_faces()")
        self.set_material(material)

    def set_vertex_value(self, index: int, indices, values):
        log_unsupported("Shape.set_vertex_value()")
        pass

    def set_linear_motion(self, x, y, z):
        log_unsupported("Shape.set_linear_motion()")
        pass

    def set_angular_motion(self, x, y, z, w):
        log_unsupported("Shape.set_angular_motion()")
        pass

    def set_scale_motion(self, x, y, z):
        log_unsupported("Shape.set_scale_motion()")
        pass

    def set_id(self, id):
        log_unsupported("Shape.set_object_id()")


class Mesh(pyrpr.Mesh, Shape):
    pass


class Instance(pyrpr.Instance, Shape):
    pass


class Scene(pyrpr.Scene):
    def attach(self, obj):
        if isinstance(obj, (pyrpr.Curve, pyrpr.HeteroVolume)):
            return

        super().attach(obj)

    def add_environment_light(self, light):
        pyrpr.SceneSetEnvironmentLight(self, light)
        self.environment_light = light

    def remove_environment_light(self):
        pyrpr.SceneSetEnvironmentLight(self, None)
        self.environment_light = None

    def clear(self):
        if self.environment_light:
            self.remove_environment_light()

        super().clear()

    def add_environment_override(self, core_id, light):
        log_unsupported("Scene.add_environment_override()")
        pass

    def remove_environment_override(self, core_id):
        log_unsupported("Scene.remove_environment_override()")
        pass

    def set_background_image(self, image):
        log_unsupported("Scene.set_background_image()")
        pass

class PostEffect:
    def __init__(self, context, post_effect_type):
        pass

    def set_parameter(self, name, param):
        pass


class Curve(pyrpr.Curve):
    def __init__(self, context, control_points, uvs, root_radius, tip_radius):
        pass

    def delete(self):
        pass

    def set_material(self, material):
        pass

    def set_transform(self, transform: np.array, transpose=True):
        pass

    def set_name(self, name):
        self.name = name


class HeteroVolume(pyrpr.HeteroVolume):
    def __init__(self, context):
        pass

    def set_transform(self, transform: np.array, transpose=True):  # Blender needs matrix to be transposed
        pass

    def set_emission_grid(self, grid_data: np.array, lookup: np.array):
        pass

    def set_albedo_grid(self, grid_data: np.array, lookup: np.array):
        pass

    def set_density_grid(self, grid_data: np.array, lookup: np.array):
        pass

    def set_name(self, name):
        self.name = name
