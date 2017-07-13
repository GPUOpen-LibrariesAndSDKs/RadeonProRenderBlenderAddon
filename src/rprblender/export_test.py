import cProfile
import os
import functools

import bpy
import pytest

import rprblender.export
import rprblender.properties
from rprblender.core.image import extract_pixels_from_blender_image
from rprblender.testing import SyncFixture, assert_arrays_approx_equal
from rprblender.timing import TimedContext
from rprblender.export import getUnitsToMeters

import numpy as np


def log(*args):
    rprblender.logging.critical(' '.join(str(arg) for arg in args), tag='testing.export')


def get_object_key(obj):
    return rprblender.export.get_object_key(obj)


class Matrix:
    def __init__(self, blender_matrix):
        self.translation = np.transpose(np.array(blender_matrix))[3][:3]

    def __repr__(self):
        return str(self.__class__) + ": translation:" + str(self.translation)


def logged(f):
    @functools.wraps(f)
    def wrapped(*args):
        self = args[0]  # type: SceneSynced
        self.call_log.append((f.__name__, args))
        log(f.__name__, '(' + ', '.join(repr(arg) for arg in args) + ')')
        result = f(*args)
        log(f.__name__, '->' + repr(result))
        return result

    return wrapped


class EnvironmentLight:
    attached = False

    def __init__(self, value, call_log=None):
        self.value = value
        self.call_log = call_log

    @logged
    def attach(self):
        self.attached = True

    @logged
    def detach(self):
        self.attached = False

    def set_intensity(self, value):
        self.intensity = value

    def set_rotation(self, value):
        self.rotation = value


class Background:
    enabled = False

    def __init__(self, call_log=None):
        self.call_log = call_log

    def set_rotation(self, value):
        self.rotation = value


class SceneSynced:
    def __init__(self, scene, settings):
        self.scene = scene
        self.settings = settings
        self.meshes = {}
        self.meshes_added = {}
        self.mesh_instances = {}
        self.instances_for_mesh = {}
        self.lamps = {}
        self.materials = set()
        self.instance_materials = {}
        self.mesh_materials = {}

        self.meshes_shown = set()

        self.lamps_shown = set()

        self.call_log = []

        self.environment_lights = []
        self.backgrounds = []

        self._motion_blur = {}

    def _get_meshes(self):
        return list(self.meshes_added.values())

    def _get_mesh_face_count(self, i):
        return len(self._get_meshes()[i]['faces_counts'])

    def _get_meshes_face_counts(self):
        return [len(mesh['faces_counts']) for mesh in self._get_meshes()]

    # store error flag in case assert happened in a thread and not propagated therefore to test runner
    def assert_true(self, condition):
        if not condition:
            self.error = True
        assert condition

    @logged
    def add_mesh(self, key, mesh, world_matrix):
        self.assert_true(key not in self.meshes)  # make sure remove is always called before re-adding mesh)
        self.meshes[key] = [len(mesh['data']['faces_counts']), Matrix(world_matrix),
                            len(mesh['data']['indices'])]
        self.meshes_added[key] = {
            'matrix': Matrix(world_matrix),
            'faces_counts': mesh['data']['faces_counts'],
            'indices': mesh['data']['indices'],
        }

        self.meshes_shown.add(key)

    @logged
    def show_mesh(self, key):
        self.meshes_shown.add(key)

    @logged
    def hide_mesh(self, key):
        self.meshes_shown.remove(key)

    @logged
    def remove_mesh(self, key):
        del self.meshes[key]
        del self.meshes_added[key]

        self.instances_for_mesh[key] = []

    @logged
    def update_mesh_transform(self, key, world_matrix):
        self.meshes[key][1] = Matrix(world_matrix)
        self.meshes_added[key]['matrix'] = Matrix(world_matrix)

    @logged
    def add_mesh_instance(self, key, dupli):
        self.assert_true(key not in self.mesh_instances)  # make sure remove is always called before re-adding instance
        print("self.meshes", self.meshes)

        self.mesh_instances[key] = [self.meshes[dupli[0]][0], Matrix(dupli[1])]
        self.instances_for_mesh.setdefault(dupli[0], []).append(key)

    @logged
    def remove_mesh_instance(self, key):
        del self.mesh_instances[key]
        for instances in self.instances_for_mesh.values():
            if key in instances:
                instances.remove(key)

    @logged
    def update_instance_transform(self, key, matrix):
        self.mesh_instances[key][1] = Matrix(matrix)

    @logged
    def set_motion_blur(self, obj_key, *params):
        self._motion_blur[obj_key] = params

    @logged
    def reset_motion_blur(self, obj_key):
        self._motion_blur[obj_key] = None

    @logged
    def mesh_set_shadowcatcher(self, key, matrix):
        pass

    @logged
    def mesh_set_shadows(self, key, matrix):
        pass

    @logged
    def mesh_set_subdivision(self, key, factor, boundary, crease_weight):
        pass

    @logged
    def mesh_attach_portallight(self, key):
        pass

    @logged
    def mesh_detach_portallight(self, key):
        pass

    @logged
    def add_lamp(self, key, lamp):
        self.lamps[key] = tuple(lamp.location)
        self.lamps_shown.add(key)

    @logged
    def remove_lamp(self, key):
        del self.lamps[key]

    @logged
    def hide_lamp(self, key):
        self.lamps_shown.remove(key)

    @logged
    def show_lamp(self, key):
        self.lamps_shown.add(key)

    @logged
    def update_lamp(self, key, lamp):
        assert key in self.lamps
        self.lamps[key] = tuple(lamp.location)

    @logged
    def add_material(self, key, blender_mat):
        assert key not in self.materials
        assert key not in self.mesh_materials.values()
        assert key not in self.instance_materials.values()

        assert key and blender_mat
        self.materials.add(key)

    @logged
    def remove_material(self, key):
        assert key not in self.mesh_materials.values()
        assert key not in self.instance_materials.values()
        self.materials.remove(key)

    @logged
    def remove_material_from_mesh(self, obj_key, material_key):
        if obj_key in self.mesh_materials:
            del self.mesh_materials[obj_key]

    @logged
    def assign_material_to_mesh(self, mat_key, obj_key):
        assert mat_key in self.materials
        assert obj_key in self.meshes
        self.mesh_materials[obj_key] = mat_key

    @logged
    def assign_material_to_mesh_instance(self, mat_key, instance_key):
        assert instance_key in self.mesh_instances
        assert mat_key in self.materials
        self.instance_materials[instance_key] = mat_key

    @logged
    def remove_material_from_mesh_instance(self, instance_key):
        if instance_key in self.instance_materials:
            del self.instance_materials[instance_key]

    @logged
    def add_default_environment_light(self):
        pass

    @logged
    def environment_light_create_color(self, color):
        light = EnvironmentLight(color, call_log=self.call_log)
        self.environment_lights.append(light)
        return light

    @logged
    def environment_light_create(self, ibl_map):
        light = EnvironmentLight(ibl_map, call_log=self.call_log)
        self.environment_lights.append(light)
        return light

    @logged
    def background_create(self, map):
        background = Background(self.call_log)
        self.backgrounds.append(background)
        return background

    _background = None

    @logged
    def background_set(self, background):
        if self._background:
            self._background.enabled = False
        self._background = background
        if self._background:
            self._background.enabled = True


def export_to(scene_synced):
    scene_exporter = rprblender.export.SceneExport(bpy.context.scene, scene_synced, preview=True)
    scene_exporter.sync_environment_settings(bpy.context.scene.world.rpr_data.environment if bpy.context.scene.world else None)
    return scene_exporter


class ExportFixture:
    def start(self):
        self.scene = bpy.context.scene
        self.scene.update()

        self.scene_synced = SceneSynced(self.scene, bpy.context.scene.rpr.render)

        self.export = export_to(self.scene_synced)
        self.export.export()

    def start_iter(self):
        self.scene = bpy.context.scene
        self.scene.update()

        self.scene_synced = SceneSynced(self.scene, bpy.context.scene.rpr.render)
        self.export = export_to(self.scene_synced)
        yield from self.export.export_iter()


@pytest.fixture(scope='function', autouse=True)
def reset_blender():
    bpy.context.scene.render.engine = 'RPR'
    yield
    if not pytest.config.option.keep_blender_running:
        bpy.ops.wm.read_factory_settings()


@pytest.fixture(scope='function')
def export_fixture():
    return ExportFixture()


@pytest.fixture(scope='function')
def sync_fixture():
    return SyncFixture()


def test_mesh(export_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export

    assert 1 == len(scene_synced.meshes)

    print(scene_synced.meshes)
    mesh_added = scene_synced._get_meshes()[0]
    assert_arrays_approx_equal((0, 1, 0), mesh_added['matrix'].translation, 4)

    polygon_count = len(mesh_added['faces_counts'])
    assert 6 == polygon_count

    # check that to_mesh frees data(removes reference from blender's array at very least)
    assert 1 == len(bpy.data.meshes), list(bpy.data.meshes)

    assert 3 == len(export.visible_objects), export.visible_objects


def test_export_iter(export_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.ops.mesh.primitive_ico_sphere_add(size=1)

    for v in export_fixture.start_iter():
        pass


def test_dupli_group_empty_mesh(export_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.ops.mesh.primitive_circle_add(radius=1)

    bpy.ops.group.create()
    bpy.ops.object.group_instance_add(
        group='Group',
        location=(2, 0, 0))
    bpy.context.object.name = 'B'

    export_fixture.start()
    scene_synced = export_fixture.scene_synced

    # check instance
    assert 0 == len(scene_synced.mesh_instances)


def test_meta(export_fixture, sync_fixture):
    bpy.ops.object.delete()

    bpy.ops.object.metaball_add(type='BALL', radius=1)

    print("add second metaball to make sure all works")
    bpy.ops.object.metaball_add(type='BALL', radius=1)
    bpy.context.object.data.materials.append(make_simple_material())
    bpy.context.object.location = (1, 0, 0)
    bpy.context.object.scale = (1, 0.5, 1)

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export

    assert 1 == len(scene_synced.meshes)

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        bpy.context.object.location = (2, 0, 0)
        bpy.context.scene.update()


def test_dupli_group(export_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    bpy.ops.group.create()
    group = bpy.ops.object.group_instance_add(
        group='Group',
        location=(2, 0, 0))
    bpy.context.object.name = 'B'

    cube_twin = bpy.context.object

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export

    # check instance
    assert 1 == len(scene_synced.mesh_instances)

    # assert [get_object_key(cube_twin)]==list(scene_synced.mesh_instances.keys())

    dup = list(scene_synced.mesh_instances.values())[0]
    prototype, matrix = dup

    assert 6 == prototype, (prototype, get_object_key(cube))

    assert_arrays_approx_equal((2, 1, 0), matrix.translation, 4)

    # scene_synced = SceneSynced(scene)
    # visible_objects = rprblender.export.export_scene(bpy.context, scene_synced, ['MESH'])


def test_dupli_group_on_mesh(export_fixture):
    cube = bpy.context.object  # bpy.types.Object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    bpy.ops.group.create()

    bpy.ops.mesh.primitive_plane_add(radius=1)

    bpy.context.object.dupli_type = 'GROUP'
    bpy.context.object.dupli_group = bpy.data.groups["Group"]

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export

    # check instance
    assert 1 == len(scene_synced.mesh_instances)

    # assert [get_object_key(cube_twin)]==list(scene_synced.mesh_instances.keys())

    dup = list(scene_synced.mesh_instances.values())[0]
    prototype, matrix = dup

    assert 6 == prototype, (prototype, get_object_key(cube))


def test_dupli_group_linked_on_mesh(export_fixture, sync_fixture, tmpdir_factory):
    cube = bpy.context.object  # bpy.types.Object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    bpy.ops.group.create()

    libpath = str(tmpdir_factory.mktemp('data').join('lib.blend'))

    bpy.ops.wm.save_mainfile(filepath=libpath)

    bpy.ops.wm.read_factory_settings()
    scene = bpy.context.scene

    bpy.ops.object.delete()

    with bpy.data.libraries.load(libpath) as (data_from, data_to):
        data_to.groups = ['Group']

    for i in range(3):
        bpy.ops.mesh.primitive_plane_add(radius=1)
        bpy.context.object.dupli_type = 'GROUP'
        bpy.context.object.dupli_group = bpy.data.groups["Group"]

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export

    # check instance
    # check that first instance is added as regular mesh(Core api requirement)
    assert 4 == len(scene_synced.meshes)
    assert 2 == len(scene_synced.mesh_instances)

    # assert [get_object_key(cube_twin)]==list(scene_synced.mesh_instances.keys())

    dup = list(scene_synced.mesh_instances.values())[0]
    prototype, matrix = dup

    assert 6 == prototype, (prototype, get_object_key(cube))

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        scene.update()
    assert 4 == len(scene_synced.meshes)
    assert 2 == len(scene_synced.mesh_instances)

    print('add another instance')
    bpy.ops.mesh.primitive_plane_add(radius=1)
    bpy.context.object.dupli_type = 'GROUP'
    bpy.context.object.dupli_group = bpy.data.groups["Group"]
    with sync_fixture:
        scene.update()
    assert 5 == len(scene_synced.meshes)
    assert 3 == len(scene_synced.mesh_instances)


def test_dupli_group_few_meshes_in_group(export_fixture):
    cube = bpy.context.object

    bpy.ops.mesh.primitive_ico_sphere_add(size=1,
                                          location=(0, 0, 2)
                                          )
    sphere = bpy.context.object

    bpy.data.objects['Cube'].select = True

    bpy.ops.group.create()
    bpy.ops.object.group_instance_add(
        group='Group',
        location=(2, 0, 0))

    bpy.context.object.name = 'CubeSphere'

    cube_sphere = bpy.context.object

    scene = bpy.context.scene
    scene.update()

    scene_synced = SceneSynced(scene, scene.rpr.render)
    export = export_to(scene_synced)
    export.export_objects([cube_sphere, cube, sphere])
    # make sure that duplis processed first and code that exports mesh is called there

    assert 2 == len(scene_synced.meshes), scene_synced.meshes

    assert 2 == len(scene_synced.mesh_instances)
    assert 2 == len(list(scene_synced.mesh_instances.values()))

    # assert get_object_key(cube_sphere) == list(scene_synced.mesh_instances.keys())[0]

    duplis = set(dupli[0] for dupli in list(scene_synced.mesh_instances.values()))
    assert {6, len(sphere.data.polygons)} == duplis, duplis


def test_dupli_no_export(export_fixture):
    cube = bpy.context.object

    bpy.context.object.location = (0, 1, 0)

    # EMPTY 
    bpy.ops.object.empty_add(type='PLAIN_AXES')

    # ARMATURE in GROUP
    bpy.ops.object.armature_add(radius=1)
    bpy.ops.group.create()
    bpy.ops.object.group_instance_add(group='Group')

    export_fixture.start()
    scene_synced = export_fixture.scene_synced

    assert 1 == len(scene_synced.meshes), scene_synced.meshes


def test_mesh_sync(export_fixture, sync_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    assert 1 == len(scene_synced.meshes)
    # assert get_object_key(cube) == list(scene_synced.meshes.keys())[0]
    mesh = scene_synced._get_meshes()[0]
    matrix = mesh['matrix']
    assert_arrays_approx_equal((0, 1, 0), matrix.translation, 4)
    polygon_count = len(mesh['faces_counts'])
    assert 6 == polygon_count, polygon_count

    # check that to_mesh frees data(removes reference from blender's array at very least)
    assert 1 == len(bpy.data.meshes), list(bpy.data.meshes)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(smoothness=1)
    bpy.ops.object.mode_set(mode='OBJECT')

    assert bpy.ops.object.is_updated

    # obj.is_updated_data or (obj.data and obj.data.is_updated)
    export.objects_sync.update_object_data(rprblender.export.get_object_key(cube), cube)

    assert 1 == len(scene_synced.meshes)
    polygon_count = len(scene_synced._get_meshes()[0]['faces_counts'])
    assert 24 == polygon_count


def test_sync_layers(export_fixture, sync_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.ops.mesh.primitive_ico_sphere_add()
    # move object to layer #1 first then remove from #0
    bpy.context.object.layers[1] = True
    bpy.context.object.layers[0] = False

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    assert 1 == len(scene_synced.meshes)
    # assert get_object_key(cube) == list(scene_synced.meshes.keys())[0]

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        bpy.context.object.location = (1, 0, 0)
        scene.update()

    assert 1 == len(scene_synced.meshes)


def test_sync_non_mesh(export_fixture, sync_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.ops.mesh.primitive_circle_add(radius=1)
    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.mesh.primitive_circle_add(radius=1)

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    assert 2 == len(scene_synced.meshes)

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        scene.update()
    assert 2 == len(scene_synced.meshes)


@pytest.mark.parametrize('i', range(10))
def test_sync_mesh_readd(i, export_fixture, sync_fixture):
    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    assert 1 == len(scene_synced.meshes)
    assert [6] == scene_synced._get_meshes_face_counts()

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        bpy.ops.object.delete()
        bpy.ops.mesh.primitive_ico_sphere_add()
        scene.update()

    assert [80] == scene_synced._get_meshes_face_counts()


def test_mesh_update_sync_dupli(export_fixture, sync_fixture):
    cube = bpy.context.object
    scene = bpy.context.scene

    bpy.context.object.name = 'A'
    bpy.context.object.location = (0, 1, 0)

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        bpy.ops.group.create()
        group = bpy.ops.object.group_instance_add(
            group='Group',
            location=(2, 0, 0))
        bpy.context.object.name = 'B'
        cube_twin = bpy.context.object

        log('added group instance')
        scene.update()
        assert 1 == len(scene_synced.mesh_instances), scene_synced.mesh_instances
        # assert scene_synced.instances_for_mesh[get_object_key(cube)]
        dup = list(scene_synced.mesh_instances.values())[0]
        prototype, matrix = dup
        assert_arrays_approx_equal((2, 1, 0), matrix.translation, 4)

        bpy.context.scene.objects.active = cube
        log('start edit')
        bpy.ops.object.mode_set(mode='EDIT')

        log('started edit')
        scene.update()

        assert 1 == len(scene_synced.mesh_instances), scene_synced.mesh_instances
        # there's an issue that when edit is started only edited mesh is_updated is tagged
        # but nothing for its duplis, so that code needs to check all duplis for updated mesh
        # assert scene_synced.instances_for_mesh[get_object_key(cube)]

        bpy.ops.mesh.subdivide(smoothness=1)
        bpy.ops.object.mode_set(mode='OBJECT')

        log('finished edit')
        scene.update()

        assert 1 == len(scene_synced.meshes)
        assert 1 == len(scene_synced.mesh_instances)

        polygon_count = list(scene_synced.meshes.values())[0][0]
        assert 24 == polygon_count, polygon_count

        dup = list(scene_synced.mesh_instances.values())[0]
        prototype, matrix = dup
        assert 24 == prototype, prototype
        assert_arrays_approx_equal((2, 1, 0), matrix.translation, 4)

        # try backwards, in case instance is updated first
        bpy.context.scene.objects.active = cube
        log('editt again')
        bpy.ops.object.mode_set(mode='EDIT')

        assert 1 == len(scene_synced.mesh_instances)
        # there's an issue that when edit is started only edited mesh is_updated is tagged
        # but nothing for its duplis, so that code needs to check all duplis for updated mesh
        # assert scene_synced.instances_for_mesh[get_object_key(cube)]

        bpy.ops.mesh.subdivide(smoothness=1)
        log('subdivided')
        scene.update()

        bpy.ops.object.mode_set(mode='OBJECT')
        log('finished edit')
        scene.update()

        assert bpy.ops.object.is_updated
        assert not cube.is_updated_data

    assert 1 == len(scene_synced.meshes)
    assert 1 == len(scene_synced.mesh_instances)

    polygon_count = list(scene_synced.meshes.values())[0][0]
    assert 96 == polygon_count, polygon_count

    dup = list(scene_synced.mesh_instances.values())[0]
    prototype, matrix = dup
    assert 96 == prototype, prototype


def test_mesh_sync_dupli_matrix(export_fixture, sync_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    bpy.ops.group.create()
    group = bpy.ops.object.group_instance_add(
        group='Group',
        location=(2, 0, 0))
    bpy.context.object.name = 'B'

    cube_twin = bpy.context.object

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    dup = list(scene_synced.mesh_instances.values())[0]
    prototype, matrix = dup
    assert_arrays_approx_equal((2, 1, 0), matrix.translation, 4)

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        log("update prototype location")
        bpy.context.scene.objects.active = cube
        bpy.context.object.location = (0, 0, 2)
        scene.update()

    log("check prototype location")
    assert 1 == len(scene_synced._get_meshes())
    mesh = scene_synced._get_meshes()[0]
    assert_arrays_approx_equal((0, 0, 2), mesh['matrix'].translation, 4)

    log("check instance location")
    dup = list(scene_synced.mesh_instances.values())[0]
    prototype, matrix = dup
    assert_arrays_approx_equal((2, 0, 2), matrix.translation, 4)


def test_sync_mesh_add(export_fixture, sync_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        bpy.ops.mesh.primitive_ico_sphere_add(size=1, location=(0, 0, 2))

        scene.update()

        assert bpy.ops.object.is_updated
        assert not cube.is_updated_data

    assert 2 == len(scene_synced.meshes)

    with sync_fixture:
        bpy.ops.object.delete()
        bpy.context.scene.update()

    assert 1 == len(scene_synced.meshes), scene_synced.meshes


def make_simple_material():
    log('make new material')
    material = bpy.data.materials.new(name='Iron')
    log('add rpr node tree to make material accepted')
    override = bpy.context.copy()
    override['material'] = material
    bpy.ops.rpr.op_material_add_nodetree(override)
    print('trigger material update')
    material.update_tag()
    return material


class TestMaterialSync:
    def test_simple_export_material(self, export_fixture, sync_fixture):

        cube = bpy.context.object
        bpy.context.object.name = 'A'

        log('try adding rpr material into slot')
        bpy.context.object.data.materials[0] = make_simple_material()

        log('export')
        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        assert 1 == len(scene_synced.meshes)
        assert 1 == len(scene_synced.materials)
        assert 1 == len(scene_synced.mesh_materials)
        assert scene_synced.mesh_materials

    def test_sync_set_material(self, export_fixture, sync_fixture):
        cube = bpy.context.object
        bpy.context.object.name = 'A'

        log('try object without a material in slot(None)')
        cube.data.materials[0] = None
        # default cube has material on mesh data, not in object material_slots
        assert [(None, 'DATA')] == [(s.material, s.link) for s in cube.material_slots]

        # bpy.ops.object.material_slot_add()
        # bpy.context.object.material_slots[0].material = None
        # assert [(None, 'DATA')] == [(s.material, s.link) for s in bpy.context.object.material_slots]

        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        assert 1 == len(scene_synced.meshes)
        assert not len(scene_synced.mesh_materials)

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            log('try adding rpr material into slot')
            cube.data.materials[0] = make_simple_material()

            scene.update()
            assert 1 == len(scene_synced.meshes)
            assert 1 == len(scene_synced.mesh_materials)

            log('try removing material from slot')
            bpy.context.object.data.materials[0] = None
            print('trigger object update')
            bpy.context.object.update_tag()

            scene.update()
            assert not len(scene_synced.mesh_materials)

        bpy.ops.mesh.primitive_ico_sphere_add(size=1, location=(0, 0, 2))

    def test_export_one_material_on_two_meshes(self, export_fixture, sync_fixture):
        cube = bpy.context.object
        bpy.context.object.name = 'A'

        log('create linked duplicate')
        bpy.ops.object.duplicate(linked=True)

        bpy.context.object.data.materials[0] = make_simple_material()

        log('export')
        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        assert 2 == len(scene_synced.meshes)
        assert 1 == len(scene_synced.materials)  # one materials instance
        assert 2 == len(scene_synced.mesh_materials)  # on both meshes
        assert 1 == len(set(scene_synced.mesh_materials.values()))  # same, again

    def test_sync_add_linked_duplicate(self, export_fixture, sync_fixture):
        cube = bpy.context.object
        bpy.context.object.name = 'A'

        bpy.context.object.data.materials[0] = make_simple_material()

        log('export')
        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        assert 1 == len(scene_synced.meshes)
        assert 1 == len(scene_synced.materials)  # one materials instance
        assert 1 == len(scene_synced.mesh_materials)  # on both meshes

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            log('create linked duplicate')
            bpy.ops.object.duplicate(linked=True)
            scene.update()
            log('create linked duplicate - done')

            assert 2 == len(scene_synced.meshes)
            assert 1 == len(scene_synced.materials)  # one materials instance
            assert 2 == len(scene_synced.mesh_materials)  # on both meshes

            assert 1 == len(set(scene_synced.mesh_materials.values()))  # same, again

    def test_sync_one_material_on_two_meshes(self, export_fixture, sync_fixture):
        cube = bpy.context.object
        bpy.context.object.name = 'A'

        bpy.context.object.data.materials[0] = None

        log('create linked duplicate')
        bpy.ops.object.duplicate(linked=True)

        log('export')
        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        assert 2 == len(scene_synced.meshes)
        assert 0 == len(scene_synced.materials)  # no material assigned yet
        assert 0 == len(scene_synced.mesh_materials)  # on both meshes

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            log('add rpr material into slot')
            material = make_simple_material()

            log('put material to slot')
            bpy.context.object.data.materials[0] = material

            log('ensure sync is called by calling scene update')
            scene.update()
            assert 2 == len(scene_synced.meshes)
            assert 1 == len(scene_synced.materials)  # one materials instance
            assert 2 == len(scene_synced.mesh_materials)  # on both meshes
            assert 1 == len(set(scene_synced.mesh_materials.values()))  # same, again

    def test_sync_material_on_removed_object(self, export_fixture, sync_fixture):
        cube = bpy.context.object
        bpy.context.object.name = 'A'

        bpy.context.object.data.materials[0] = None

        log('export')
        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        assert 1 == len(scene_synced.meshes)
        assert 0 == len(scene_synced.materials)  # no material assigned yet
        assert 0 == len(scene_synced.mesh_materials)  # on both meshes

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            log('add rpr material into slot')
            material = make_simple_material()

            log('put material to slot')
            bpy.context.object.data.materials[0] = material

            scene.update()
            assert 1 == len(scene_synced.meshes)
            assert 1 == len(scene_synced.materials)  # one materials instance
            assert 1 == len(scene_synced.mesh_materials)  # on both meshes

        with sync_fixture:
            bpy.ops.object.delete()

            scene.update()
            assert 0 == len(scene_synced.meshes)
            assert 1 == len(scene_synced.materials)  # one materials instance
            assert 0 == len(scene_synced.mesh_materials)  # on both meshes

    def test_two_meshes_sharing_material_replace_material_on_one_mesh(self, export_fixture, sync_fixture):
        cube = bpy.context.object
        cube.name = 'A'

        cube.data.materials[0] = make_simple_material()

        bpy.ops.mesh.primitive_ico_sphere_add(size=1)
        sphere = bpy.context.object
        sphere.name = 'B'

        assert 0 == len(sphere.data.materials)
        sphere.data.materials.append(cube.data.materials[0])

        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        assert 2 == len(scene_synced.meshes)
        assert 2 == len(scene_synced.mesh_materials)

        assert 1 == len(scene_synced.materials)

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            log("replace material on one mesh")
            sphere.data.materials[0] = make_simple_material()

            scene.update()
            assert 2 == len(scene_synced.meshes)
            assert 2 == len(scene_synced.mesh_materials)

            assert 2 == len(scene_synced.materials)

    def test_two_materials(self, export_fixture, sync_fixture):

        cube = bpy.context.object
        bpy.context.object.name = 'A'

        bpy.context.object.data.materials[0] = make_simple_material()
        bpy.context.object.data.materials.append(make_simple_material())

        cube.data.polygons[0].material_index = 1

        log('export')
        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        assert 2 == len(scene_synced.meshes)
        assert 2 == len(scene_synced.materials)
        materials = list(scene_synced.mesh_materials.values())
        assert materials[0] is not None
        assert materials[1] is not None
        assert 2 == len(scene_synced.mesh_materials)
        assert scene_synced.mesh_materials

        assert {1, 5} == {m[0] for m in scene_synced.meshes.values()}
        assert {4, 20} == {m[2] for m in scene_synced.meshes.values()}

    def test_two_materials_on_instance(self, export_fixture, sync_fixture):

        cube = bpy.context.object
        bpy.context.object.name = 'A'

        bpy.context.object.data.materials[0] = make_simple_material()
        bpy.context.object.data.materials.append(make_simple_material())

        cube.data.polygons[0].material_index = 1

        bpy.ops.group.create()
        bpy.ops.object.group_instance_add()

        log('export')
        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        assert 2 == len(scene_synced.meshes)
        assert 2 == len(scene_synced.materials)
        assert 2 == len(scene_synced.mesh_materials)
        assert None not in set(scene_synced.mesh_materials.values())

        assert {1, 5} == {m[0] for m in scene_synced.meshes.values()}
        assert {4, 20} == {m[2] for m in scene_synced.meshes.values()}

        assert 2 == len(scene_synced.mesh_instances)
        assert 2 == len(scene_synced.instance_materials)
        assert set(scene_synced.mesh_materials.values()) == set(scene_synced.instance_materials.values())

    def test_sync_two_materials_on_instance(self, export_fixture, sync_fixture):

        cube = bpy.context.object
        bpy.context.object.name = 'A'

        materials = (make_simple_material(), make_simple_material())

        bpy.context.object.data.materials[0] = materials[0]
        bpy.context.object.data.materials.append(materials[1])

        cube.data.polygons[0].material_index = 1

        log('export')
        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            log("add instance")
            bpy.ops.group.create()
            bpy.ops.object.group_instance_add()
            scene.update()

        assert 2 == len(scene_synced.mesh_instances)
        assert 2 == len(scene_synced.instance_materials)
        assert set(scene_synced.mesh_materials.values()) == set(scene_synced.instance_materials.values())

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            log("udpate material")
            diffuse = None
            for node in materials[1].node_tree.nodes:
                nt = getattr(node, "bl_idname", None)
                if 'diffuse' in nt:
                    diffuse = node
            diffuse.inputs['Diffuse Color'].default_value = (0.5, 0.25, 0.75, 1)
            materials[0].update_tag()
            scene.update()
        assert set(scene_synced.mesh_materials.values()) == set(scene_synced.instance_materials.values())

    def test_group_instance(self, export_fixture, sync_fixture):
        cube = bpy.context.object
        bpy.context.object.name = 'A'

        cube.data.materials[0] = make_simple_material()

        bpy.ops.group.create()
        bpy.ops.object.group_instance_add()
        bpy.ops.object.group_instance_add()

        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        assert 2 == len(scene_synced.mesh_instances)
        assert 2 == len(scene_synced.instance_materials)

    def test_sync_add_group_instance(self, export_fixture, sync_fixture):
        cube = bpy.context.object
        bpy.context.object.name = 'A'

        cube.data.materials[0] = make_simple_material()

        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            log('try adding group instance')

            bpy.ops.group.create()
            bpy.ops.object.group_instance_add()

            scene.update()
            assert 1 == len(scene_synced.mesh_instances)
            assert 1 == len(scene_synced.instance_materials)

        with sync_fixture:
            log('try removing group instance')

            bpy.ops.object.delete()

            scene.update()
            assert 0 == len(scene_synced.mesh_instances)
            assert 0 == len(scene_synced.instance_materials)

    def test_sync_group_instance_from_invisible_layer_duplicate(self, export_fixture, sync_fixture):
        cube = bpy.context.object
        bpy.context.object.name = 'A'

        cube.data.materials[0] = make_simple_material()
        # hide prototype object in separate layer

        bpy.ops.group.create()

        bpy.context.object.layers[1] = True
        bpy.context.object.layers[0] = False

        bpy.ops.object.group_instance_add()

        duplicate_0 = bpy.context.object

        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export
        scene = export_fixture.scene

        assert 1 == len(scene_synced.meshes)
        assert 0 == len(scene_synced.mesh_instances)
        assert 0 == len(scene_synced.instance_materials)

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            log('move')
            bpy.context.object.location = (1, 2, 0)
            scene.update()

        dup = list(scene_synced.meshes_added.values())[0]
        assert_arrays_approx_equal((1, 2, 0), dup['matrix'].translation, 4)

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            log('duplicate')
            bpy.ops.object.duplicate(linked=False)
            scene.update()

        assert 1 == len(scene_synced.meshes)
        assert 1 == len(scene_synced.meshes_shown)
        assert 1 == len(scene_synced.mesh_instances)
        # assert 1 == len(scene_synced.instance_materials)

        with sync_fixture:
            log('move duplicate')
            bpy.context.object.location = (3, 2, 1)
            scene.update()

        dup = list(scene_synced.mesh_instances.values())[0]
        prototype, matrix = dup
        assert_arrays_approx_equal((3, 2, 1), matrix.translation, 4)

        with sync_fixture:
            log('move duplicate')
            duplicate_0.location = (3, 1, 4)
            scene.update()

        assert 1 == len(scene_synced.meshes)
        assert_arrays_approx_equal((3, 1, 4), scene_synced._get_meshes()[0]['matrix'].translation, 4)

        with sync_fixture:
            log('move prototype to visible layer')
            bpy.context.object.layers[0] = True
            scene.update()

        assert 1 == len(scene_synced.meshes)
        assert 1 == len(scene_synced.meshes_shown)
        assert 1 == len(scene_synced.mesh_instances)

    def test_dupli_group_on_mesh_prototype_invisible(self, export_fixture):
        cube = bpy.context.object  # bpy.types.Object

        bpy.context.object.location = (0, 1, 0)
        bpy.context.object.data.materials[0] = make_simple_material()
        bpy.ops.group.create()

        # hide prototype object in separate layer
        bpy.context.object.layers[1] = True
        bpy.context.object.layers[0] = False

        bpy.ops.mesh.primitive_plane_add(radius=1)

        bpy.context.object.dupli_type = 'GROUP'
        bpy.context.object.dupli_group = bpy.data.groups["Group"]

        bpy.ops.mesh.primitive_plane_add(radius=1)

        bpy.context.object.dupli_type = 'GROUP'
        bpy.context.object.dupli_group = bpy.data.groups["Group"]

        export_fixture.start()
        scene_synced = export_fixture.scene_synced
        export = export_fixture.export

        # check instance
        assert 1 == len(scene_synced.mesh_instances)
        assert 1 == len(scene_synced.materials)  # one materials instance
        assert 1 == len(scene_synced.mesh_materials)
        assert 1 == len(scene_synced.instance_materials)

        assert list(scene_synced.mesh_materials.values())[0] == list(scene_synced.instance_materials.values())[0]


def test_sync_mesh_hide(export_fixture, sync_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    assert 1 == len(scene_synced.meshes_shown)

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        bpy.context.object.hide = True
        scene.update()
        assert 1 == len(scene_synced.meshes)
        assert 0 == len(scene_synced.meshes_shown)

        bpy.context.object.hide = False
        scene.update()
        assert 1 == len(scene_synced.meshes_shown)

        log("move object to disabled scene layer")
        bpy.context.object.layers[1] = True
        bpy.context.object.layers[0] = False
        scene.update()
        assert 0 == len(scene_synced.meshes_shown)

        log("enable scene layer with the object")
        bpy.context.scene.layers[1] = True
        scene.update()
        assert 1 == len(scene_synced.meshes_shown)

        log("disable scene layer with the object")
        bpy.context.scene.layers[1] = False
        scene.update()
        assert 0 == len(scene_synced.meshes_shown)

        log("reenable scene layer with the object")
        bpy.context.scene.layers[1] = True
        scene.update()
        assert 1 == len(scene_synced.meshes_shown)

        log("set layer as excluded")
        bpy.context.scene.render.layers.active.layers_exclude[1] = True
        scene.update()
        assert 0 == len(scene_synced.meshes_shown)


def test_export_mesh_exclude(export_fixture, sync_fixture):
    log("exclude layer and test that it wasn't even exported")
    bpy.context.scene.render.layers.active.layers_exclude[0] = True

    export_fixture.start()
    scene_synced = export_fixture.scene_synced

    assert 0 == len(scene_synced.meshes)


def test_sync_mesh_hide_before_export(export_fixture, sync_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    bpy.context.object.hide = True

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    assert 0 == len(scene_synced.meshes)  # avoid exporting mesh if it's not shown yet
    assert 0 == len(scene_synced.meshes_shown)

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        bpy.context.object.hide = False

        scene.update()

        assert 1 == len(scene_synced.meshes)
        assert 1 == len(scene_synced.meshes_shown)


def test_motion_blur(export_fixture, sync_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    scene = bpy.context.scene
    scene.rpr.render.motion_blur = True
    scene.rpr.render.motion_blur_type = 'GEOMETRY'

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    assert 1 == len(scene_synced.meshes_shown)

    assert list(scene_synced._motion_blur.values())[0]

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        bpy.context.object.location = (0, 2, 0)
        scene.update()

    assert list(scene_synced._motion_blur.values())[0]


def test_dupli_add(export_fixture, sync_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        log('create grounp and add instance')
        bpy.ops.group.create()
        group = bpy.ops.object.group_instance_add(
            group='Group',
            location=(2, 0, 0))
        bpy.context.object.name = 'B'

        cube_twin = bpy.context.object

        scene.update()

        # check instance
        assert 1 == len(scene_synced.mesh_instances)

        # assert [get_object_key(cube_twin)]==list(scene_synced.mesh_instances.keys())

        dup = list(scene_synced.mesh_instances.values())[0]
        prototype, matrix = dup

        assert 6 == prototype, (prototype, get_object_key(cube))

        assert_arrays_approx_equal((2, 1, 0), matrix.translation, 4)


def test_dupli_remove_hide(export_fixture, sync_fixture):
    cube = bpy.context.object
    bpy.context.object.name = 'A'

    bpy.context.object.location = (0, 1, 0)

    bpy.ops.group.create()
    bpy.ops.object.group_instance_add(
        group='Group',
        location=(2, 0, 0))

    cube_twin = bpy.context.object

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    scene.update()
    assert 1 == len(scene_synced.mesh_instances)

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        bpy.ops.object.delete(use_global=False)
        scene.update()

        assert 0 == len(scene_synced.mesh_instances)

        # try re-creating
        bpy.ops.object.group_instance_add(
            group='Group',
            location=(2, 0, 0))
        scene.update()
        assert 1 == len(scene_synced.mesh_instances)

        bpy.context.object.hide = True
        scene.update()
        assert 0 == len(scene_synced.mesh_instances)

        bpy.context.object.hide = False
        scene.update()
        assert 1 == len(scene_synced.mesh_instances)

        # hide prototype object
        cube.hide = True
        scene.update()
        assert 0 == len(scene_synced.mesh_instances)

        cube.hide = False
        scene.update()
        assert 1 == len(scene_synced.mesh_instances)

        # check all fine if we remove object and only after that remove it's duplicator
        cube.hide = True
        scene.update()
        bpy.context.object.hide = True
        scene.update()
        assert 0 == len(scene_synced.mesh_instances)


def test_same_object_in_duplicator_twice(export_fixture):
    bpy.ops.group.create()
    bpy.ops.object.group_instance_add(group='Group')
    part0 = bpy.context.object
    bpy.ops.object.group_instance_add(group='Group')
    part1 = bpy.context.object
    bpy.ops.object.empty_add(type='PLAIN_AXES', radius=1)
    part0.select = True
    part1.select = True

    bpy.ops.group.create(name='SuperGroup')
    bpy.ops.object.parent_set(type='OBJECT')

    bpy.ops.object.group_instance_add(group='SuperGroup')

    scene = bpy.context.scene
    bpy.context.object.dupli_list_create(scene, 'RENDER')
    for dupli in bpy.context.object.dupli_list:
        print(dupli, dupli.object, list(dupli.persistent_id))
    bpy.context.object.dupli_list_clear()

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    scene.update()

    assert 4 == len(scene_synced.mesh_instances)


def test_lamp(export_fixture, sync_fixture):
    cube = bpy.context.object

    lamp = bpy.data.objects['Lamp']
    lamp.location = (3, 5, 7)

    lamp.data.rpr_lamp.intensity = 2

    export_fixture.start()
    scene_synced = export_fixture.scene_synced  # type: SceneSynced
    export = export_fixture.export
    scene = export_fixture.scene

    assert 1 == len(scene_synced.lamps), scene_synced.lamps
    assert_arrays_approx_equal((3, 5, 7), list(scene_synced.lamps.values())[0], 3)

    assert ['add_lamp'] == [r[0] for r in scene_synced.call_log if 'lamp' in r[0]]

    log('update scene once')
    scene.update()

    log('to see that nothing has changed')
    assert ['add_lamp'] == [r[0] for r in scene_synced.call_log if 'lamp' in r[0]]

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        lamp.location = (2, 3, 5)
        scene_synced.call_log.clear()
        scene.update()
        assert ['remove_lamp', 'add_lamp'] == [r[0] for r in scene_synced.call_log if 'lamp' in r[0]]

        assert 1 == len(scene_synced.lamps), scene_synced.lamps

        assert_arrays_approx_equal((2, 3, 5), list(scene_synced.lamps.values())[0], 3)

        lamp.hide = True
        scene_synced.call_log.clear()
        scene.update()
        assert ['hide_lamp'] == [r[0] for r in scene_synced.call_log if 'lamp' in r[0]]

        assert 1 == len(scene_synced.lamps), scene_synced.lamps
        assert not scene_synced.lamps_shown

        lamp.hide = False
        scene_synced.call_log.clear()
        scene.update()
        assert ['remove_lamp', 'add_lamp', 'show_lamp'] == [r[0] for r in scene_synced.call_log if 'lamp' in r[0]]

        assert 1 == len(scene_synced.lamps), scene_synced.lamps
        assert list(scene_synced.lamps.keys())[0] in scene_synced.lamps_shown

        cube.select = False
        lamp.select = True
        scene_synced.call_log.clear()
        bpy.ops.object.delete()
        scene.update()
        assert ['remove_lamp'] == [r[0] for r in scene_synced.call_log if 'lamp' in r[0]]

        assert 0 == len(scene_synced.lamps), scene_synced.lamps

        scene_synced.call_log.clear()
        bpy.ops.object.lamp_add(type='POINT')
        scene.update()
        assert ['add_lamp', 'show_lamp'] == [r[0] for r in scene_synced.call_log if 'lamp' in r[0]]
        assert 1 == len(scene_synced.lamps), scene_synced.lamps
        assert list(scene_synced.lamps.keys())[0] in scene_synced.lamps_shown


def test_lamp_calls(export_fixture, sync_fixture):
    cube = bpy.context.object

    lamp = bpy.data.objects['Lamp']
    lamp.location = (3, 5, 7)
    lamp.data.rpr_lamp.intensity = 2

    export_fixture.start()
    scene_synced = export_fixture.scene_synced  # type: SceneSynced
    export = export_fixture.export
    scene = export_fixture.scene

    calls = scene_synced.call_log
    assert ['add_lamp'] == [r[0] for r in calls if 'lamp' in r[0]]

    log('update scene once')
    scene.update()
    log('to see that nothing has changed')
    assert ['add_lamp'] == [r[0] for r in calls if 'lamp' in r[0]]

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        calls.clear()
        lamp.location = (2, 3, 5)

        scene.update()
        assert ['remove_lamp', 'add_lamp'] == [r[0] for r in calls if 'lamp' in r[0]]

        calls.clear()
        lamp.hide = True

        scene.update()
        assert ['hide_lamp'] == [r[0] for r in calls if 'lamp' in r[0]]

        calls.clear()
        lamp.hide = False

        scene.update()
        assert ['remove_lamp', 'add_lamp', 'show_lamp'] == [r[0] for r in calls if 'lamp' in r[0]]

        calls.clear()
        cube.select = False
        lamp.select = True
        bpy.ops.object.delete()

        scene.update()
        assert ['remove_lamp'] == [r[0] for r in calls if 'lamp' in r[0]]

        calls.clear()
        bpy.ops.object.lamp_add(type='POINT')

        scene.update()
        assert ['add_lamp', 'show_lamp'] == [r[0] for r in calls if 'lamp' in r[0]]


def get_environment_lights_attached(scene_synced):
    return [l.attached for l in scene_synced.environment_lights]


class TestEnvironment:

    def update_scene(self, export_fixture):
        export_fixture.export.sync_environment_settings(
            bpy.context.scene.world.rpr_data.environment if bpy.context.scene.world else None)
        export_fixture.scene.update()

    def test_ibl(self, export_fixture, sync_fixture):
        cube = bpy.context.object

        lamp = bpy.data.objects['Lamp']
        lamp.location = (3, 5, 7)
        lamp.data.rpr_lamp.intensity = 2

        export_fixture.start()
        scene_synced = export_fixture.scene_synced  # type: SceneSynced
        export = export_fixture.export
        scene = export_fixture.scene
        render_settings = scene.rpr.render  # type: rprblender.properties.RenderSettings
        env_settings = scene.world.rpr_data.environment

        calls = scene_synced.call_log
        print('calls: ', calls)
        assert ['environment_light_create_color'] == [r[0] for r in calls if 'env' in r[0]]
        assert [True] == get_environment_lights_attached(scene_synced)
        assert 1.0 == scene_synced.environment_lights[0].intensity

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            log('update intensity')
            env_settings.ibl.intensity = 2.0

            self.update_scene(export_fixture)

            assert ['environment_light_create_color'] == [r[0] for r in calls if 'env' in r[0]]
            assert 2.0 == scene_synced.environment_lights[0].intensity

            calls.clear()
            lamp.location = (2, 7, 8)

            self.update_scene(export_fixture)
            expected = [True]
            assert expected == get_environment_lights_attached(scene_synced)

            calls.clear()
            env_settings.enable = True
            env_settings.type = 'IBL'
            env_settings.ibl.use_ibl_map = True
            env_settings.ibl.ibl_map = 'hello.png'

            self.update_scene(export_fixture)
            assert ['environment_light_create'] == [r[0] for r in calls if 'env' in r[0]]
            assert 2 == len(scene_synced.environment_lights)
            assert [False, True] == get_environment_lights_attached(scene_synced)

            calls.clear()
            env_settings.enable = False

            self.update_scene(export_fixture)
            assert [False, False] == get_environment_lights_attached(scene_synced)

            calls.clear()
            env_settings.enable = True
            env_settings.ibl.use_ibl_map = False

            self.update_scene(export_fixture)
            assert [False, False, True] == get_environment_lights_attached(scene_synced)
            assert (0.5,) * 3 == scene_synced.environment_lights[-1].value, 'default color value'

            log("test re-enable previous map")
            calls.clear()
            env_settings.enable = True
            env_settings.ibl.use_ibl_map = True

            self.update_scene(export_fixture)
            assert [False, False, False, True] == get_environment_lights_attached(scene_synced)

            log("test re-enable color")
            env_settings.enable = True
            env_settings.ibl.use_ibl_map = False
            self.update_scene(export_fixture)
            assert [False, False, False, False, True] == get_environment_lights_attached(scene_synced)

            env_settings.enable = False
            self.update_scene(export_fixture)
            assert [False, False, False, False, False] == get_environment_lights_attached(scene_synced)

            log("test re-enable environment with default color")
            env_settings.enable = True
            env_settings.ibl.use_ibl_map = False
            self.update_scene(export_fixture)
            assert [False, False, False, False, True] == get_environment_lights_attached(scene_synced)

    def test_background(self, export_fixture, sync_fixture):
        cube = bpy.context.object

        lamp = bpy.data.objects['Lamp']
        lamp.location = (3, 5, 7)
        lamp.data.rpr_lamp.intensity = 2

        export_fixture.start()
        scene_synced = export_fixture.scene_synced  # type: SceneSynced
        export = export_fixture.export
        scene = export_fixture.scene
        render_settings = scene.rpr.render  # type: rprblender.properties.RenderSettings
        env_settings = scene.world.rpr_data.environment

        calls = scene_synced.call_log
        assert [] == [r[0] for r in calls if 'back' in r[0]]

        sync_fixture.set_sync(export.sync)
        with sync_fixture:
            calls.clear()
            env_settings.enable = True
            env_settings.ibl.maps.override_background = True
            env_settings.ibl.maps.background_map = 'hello'

            self.update_scene(export_fixture)
            # assert ['background_create'] == [r[0] for r in calls if 'back' in r[0]]
            assert [True] == [b.enabled for b in scene_synced.backgrounds]

            calls.clear()
            env_settings.ibl.maps.override_background = False

            self.update_scene(export_fixture)
            assert [False] == [b.enabled for b in scene_synced.backgrounds]

            calls.clear()
            env_settings.ibl.maps.override_background = True

            self.update_scene(export_fixture)
            assert [True] == [b.enabled for b in scene_synced.backgrounds]

            calls.clear()
            env_settings.enable = False

            self.update_scene(export_fixture)
            assert [False] == [b.enabled for b in scene_synced.backgrounds]

            calls.clear()
            env_settings.enable = True

            self.update_scene(export_fixture)
            assert [True] == [b.enabled for b in scene_synced.backgrounds]


def test_lamp_area(export_fixture, sync_fixture):
    cube = bpy.context.object

    lamp = bpy.data.objects['Lamp']
    lamp.location = (3, 5, 7)

    lamp.data.type = 'AREA'
    lamp.data.shape = 'SQUARE'
    lamp.data.size = 1
    lamp.data.rpr_lamp.intensity = 2

    export_fixture.start()
    scene_synced = export_fixture.scene_synced
    export = export_fixture.export
    scene = export_fixture.scene

    assert 1 == len(scene_synced.lamps), scene_synced.lamps
    assert_arrays_approx_equal((3, 5, 7), list(scene_synced.lamps.values())[0], 3)

    scene.update()

    sync_fixture.set_sync(export.sync)
    with sync_fixture:
        lamp.location = (2, 3, 5)
        scene.update()

        assert 1 == len(scene_synced.lamps), scene_synced.lamps

        assert_arrays_approx_equal((2, 3, 5), list(scene_synced.lamps.values())[0], 3)

        lamp.hide = True
        scene.update()

        assert 1 == len(scene_synced.lamps), scene_synced.lamps
        assert list(scene_synced.lamps.keys())[0] not in scene_synced.lamps_shown

        lamp.hide = False
        scene.update()

        assert 1 == len(scene_synced.lamps), scene_synced.lamps
        assert list(scene_synced.lamps.keys())[0] in scene_synced.lamps_shown

        cube.select = False
        lamp.select = True
        bpy.ops.object.delete()
        scene.update()

        assert 0 == len(scene_synced.lamps), scene_synced.lamps

        bpy.ops.object.lamp_add(type='AREA')
        scene.update()
        assert 1 == len(scene_synced.lamps), scene_synced.lamps
        assert list(scene_synced.lamps.keys())[0] in scene_synced.lamps_shown


def generate_uv():
    # generate simple uvs
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.unwrap()
    bpy.ops.object.mode_set(mode='OBJECT')


class TestExtractMesh:
    def test_simple(self):
        scale = getUnitsToMeters(bpy.context.scene)
        blender_mesh = rprblender.export.get_blender_mesh(bpy.context.scene, bpy.context.object)
        assert 6 == len(blender_mesh.polygons)
        mesh = rprblender.export.extract_mesh(blender_mesh, scale)
        assert 24 == len(mesh['data']['indices'])

    def test_simple_triangles(self):
        mod = bpy.context.object.modifiers.new("triangulate", 'TRIANGULATE')

        # assert 1 == len(bpy.context.object.data.polygons)
        scale = getUnitsToMeters(bpy.context.scene)
        blender_mesh = rprblender.export.get_blender_mesh(bpy.context.scene, bpy.context.object)
        assert 12 == len(blender_mesh.polygons)
        mesh = rprblender.export.extract_mesh(blender_mesh, scale)
        assert 48 == len(mesh['data']['indices'])

    def test_material_index(self):
        scale = getUnitsToMeters(bpy.context.scene)
        bpy.context.object.data.polygons[2].material_index = 1
        blender_mesh = rprblender.export.get_blender_mesh(bpy.context.scene, bpy.context.object)
        mesh = rprblender.export.extract_mesh(blender_mesh, scale)
        assert 1 == list(mesh['data']['faces_materials']).count(1)
        assert 5 == list(mesh['data']['faces_materials']).count(0)

    def test_curve(self):
        scale = getUnitsToMeters(bpy.context.scene)
        bpy.ops.curve.primitive_bezier_circle_add(radius=1)
        bpy.context.object.data.dimensions = '2D'
        bpy.context.object.data.fill_mode = 'BOTH'
        blender_mesh = rprblender.export.get_blender_mesh(bpy.context.scene, bpy.context.object)  # type: bpy.types.Mesh
        assert 46 == len(blender_mesh.polygons)
        mesh = rprblender.export.extract_mesh(blender_mesh, scale)
        assert 184 == len(mesh['data']['indices'])

    @pytest.mark.skipif(condition=not pytest.config.option.perf, reason='this is for simple profiling of export code')
    def test_big(self):
        generate_uv()

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=2, smoothness=0)
        bpy.ops.mesh.subdivide(number_cuts=100, smoothness=1)
        bpy.ops.object.mode_set(mode='OBJECT')

        scale = getUnitsToMeters(bpy.context.scene)

        with TimedContext("get_blender_mesh"):
            blender_mesh = rprblender.export.get_blender_mesh(bpy.context.scene, bpy.context.object)
        with TimedContext("extract_mesh"):
            # s = cProfile.runctx("rprblender.export.extract_mesh(blender_mesh)", globals(), locals(), sort='cumulative')
            mesh = rprblender.export.extract_mesh(blender_mesh, scale)
        assert 3305124 == len(mesh['data']['indices'])


class TestExtractTexture:
    @pytest.mark.skipif(condition=not pytest.config.option.perf, reason='this is for simple profiling of export code')
    def test_load_core_image_from_blender_image(self):
        width, height = 2048, 1024
        image = bpy.data.images.new("test_load_core_image_from_blender_image", width=width, height=height)
        im = np.ones((height, width, 4), dtype=np.float32)
        image.pixels = im.flatten()

        for i in range(10):
            extract_pixels_from_blender_image(image)
