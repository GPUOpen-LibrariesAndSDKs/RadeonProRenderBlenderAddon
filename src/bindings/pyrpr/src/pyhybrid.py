#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
import numpy as np
import functools

import pyrpr
from rprblender.config import hybrid_unsupported_log_warn

from rprblender.utils import logging
log = logging.Log(tag='hybrid')


def ignore_unsupported(function):
    """Function decorator which ignores UNSUPPORTED and INVALID_PARAMETER core errors"""

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)

        except pyrpr.CoreError as e:
            if e.status not in (pyrpr.ERROR_UNSUPPORTED, pyrpr.ERROR_INVALID_PARAMETER,
                                pyrpr.ERROR_UNIMPLEMENTED):
                raise

            if hybrid_unsupported_log_warn:
                log.warn("Unsupported", function, *args)

    return wrapper


def class_ignore_unsupported(cls):
    """Class decorator which decorates class functions by ignore_unsupported decorator"""

    for attr_name in dir(cls):
        # we are going to decorate all functions in classes with name not started with "__"
        if attr_name.startswith("__"):
            continue

        attr = getattr(cls, attr_name)
        if callable(attr):
            setattr(cls, attr_name, ignore_unsupported(attr))

    return cls


# will be used in other modules to check if hybrid is enabled
enabled = True


@class_ignore_unsupported
class Context(pyrpr.Context):
    def set_parameter(self, key, param):
        if key == pyrpr.CONTEXT_ITERATIONS:
            self.parameters[key] = param
            return

        super().set_parameter(key, param)

    def render(self):
        iterations = self.parameters.get(pyrpr.CONTEXT_ITERATIONS, 1)
        for _ in range(iterations):
            super().render()

    @classmethod
    def register_plugin(cls, lib_path, cache_path):
        super().register_plugin(lib_path, cache_path)

        # trying to create context
        try:
            context = cls(pyrpr.CREATION_FLAGS_ENABLE_GPU0)

        except pyrpr.CoreError as err:
            cls.plugin_id = -1
            raise RuntimeError("Plugin is not registered", lib_path, err.error_message)


@class_ignore_unsupported
class IESLight(pyrpr.PointLight):
    # IESLight is not supported, that's why we change it to PointLight
    def set_image_from_file(self, image_path, nx, ny):
        pass


@class_ignore_unsupported
class PointLight(pyrpr.PointLight):
    pass


@class_ignore_unsupported
class SpotLight(pyrpr.SpotLight):
    pass


@class_ignore_unsupported
class DirectionalLight(pyrpr.DirectionalLight):
    pass


class AreaLight(pyrpr.AreaLight):
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


@class_ignore_unsupported
class EnvironmentLight(pyrpr.EnvironmentLight):
    def set_color(self, r, g, b):
        img = pyrpr.ImageData(self.context,
                              np.full((64, 64, 4), (r, g, b, 1.0), dtype=np.float32))
        self.set_image(img)


@class_ignore_unsupported
class Camera(pyrpr.Camera):
    pass


@class_ignore_unsupported
class ImageData(pyrpr.ImageData):
    pass


@class_ignore_unsupported
class ImageFile(pyrpr.ImageFile):
    pass


@class_ignore_unsupported
class MaterialNode(pyrpr.MaterialNode):
    def set_input(self, name, value):
        if isinstance(value, EmptyMaterialNode):
            if self.type != pyrpr.MATERIAL_NODE_ARITHMETIC:
                return

            value = 0.0

        super().set_input(name, value)

    def delete(self):
        self.inputs.clear()
        super().delete()


class EmptyMaterialNode(MaterialNode):
    def __init__(self, material_type):
        self.type = material_type

    def delete(self):
        pass

    def set_name(self, name):
        pass

    def set_input(self, name, value):
        pass

    def set_id(self, id):
        pass


class Shape(pyrpr.Shape):
    def set_volume_material(self, material):
        if isinstance(material, EmptyMaterialNode):
            material = None

        super().set_volume_material(material)

    def set_displacement_material(self, material):
        if isinstance(material, EmptyMaterialNode):
            material = None

        super().set_displacement_material(material)

    def set_material(self, material):
        if isinstance(material, EmptyMaterialNode):
            material = None

        super().set_material(material)

    def set_material_faces(self, material, face_indices: np.array):
        if not self.materials:
            self.set_material(material)

    def set_hetero_volume(self, hetero_volume):
        pass


@class_ignore_unsupported
class Mesh(pyrpr.Mesh, Shape):
    pass


@class_ignore_unsupported
class Instance(pyrpr.Instance, Shape):
    pass


@class_ignore_unsupported
class Scene(pyrpr.Scene):
    def attach(self, obj):
        if isinstance(obj, (Curve, HeteroVolume)):
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


class PostEffect:
    def __init__(self, context, post_effect_type):
        pass

    def set_parameter(self, name, param):
        pass


class Curve:
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


class HeteroVolume:
    def __init__(self, context):
        pass

    def set_transform(self, transform: np.array, transpose=True):  # Blender needs matrix to be transposed
        pass

    def set_grid(self, grid_type, grid):
        pass

    def set_lookup(self, grid_type, lookup: np.array):
        pass

    def set_name(self, name):
        self.name = name


class Grid(pyrpr.HeteroVolume):
    def __init__(self, context):
        pass

    @staticmethod
    def init_from_3d_array(context, grid_data: np.ndarray):
        pass

    @staticmethod
    def init_from_array_indices(context, x, y, z, grid_data, indices):
        pass
