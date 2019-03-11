#!python3
import os
import platform
import shutil
import sys
import threading
import unittest
from pathlib import Path

import pytest
import numpy.testing
import time
import numpy as np
import imageio

import faulthandler
faulthandler.enable()

rprsdk_path = Path(__file__).parents[3] / 'ThirdParty/RadeonProRender SDK'

if "Windows" == platform.system():
    bin_folder = 'Win/bin'
elif "Linux" == platform.system():
    assert 'Ubuntu' in platform.version()
    # assert '16.04' in platform.version()
    bin_folder = 'Linux/lib'
elif "Darwin" == platform.system():
    bin_folder = 'Mac/lib'
else:
    assert False

sys.path.append('.build')
sys.path.append('src')

# NOTE: pyrpr needs to be inited, here it's done at the end - to pass flags to it from args
import pyrpr
import pyrpr_load_store
import pyrprx


log_lock = threading.Lock()

if 'Windows' == platform.system():
    tahoe_name = 'Tahoe64.dll'
elif 'Linux' == platform.system():
    tahoe_name = 'libTahoe64.so'
elif 'Darwin' == platform.system():
    tahoe_name = 'libTahoe64.dylib'
else:
    assert False, platform.system()

tahoe_path = rprsdk_path / bin_folder / tahoe_name

print("tahoe_name", tahoe_name)


def print(*args):
    sys.stdout.write('[%s]' % threading.current_thread().ident)
    sys.stdout.write(' '.join(str(arg) for arg in args))
    sys.stdout.write('\n')
    sys.stdout.flush()


def ensure_core_cache_folder():
    path = str(Path(__file__).parent / '.core_cache' / hex(pyrpr.API_VERSION))

    if not os.path.isdir(path):
        os.makedirs(path)
    return path


class TestCFFI(unittest.TestCase):
    def test(self):
        int_p_p = pyrpr.ffi.new('int**')

        int_p_p[0] = pyrpr.ffi.cast('int*', 123)

        int_p_0 = int_p_p[0]

        int_p_p[0] = pyrpr.ffi.cast('int*', 345)


def add_simple_quad(context, scene):
    mesh = create_simple_quad(context)
    pyrpr.SceneAttachShape(scene, mesh)
    return mesh


def create_simple_quad(context):
    vertices = np.array([[-2.0, 2.0, 0.0, 0.0, 0.0, +1.0, 0.0, 0.0],
                         [2.0, 2.0, 0.0, 0.0, 0.0, +1.0, 1.0, 0.0],
                         [2.0, -2.0, 0.0, 0.0, 0.0, +1.0, 1.0, 1.0],
                         [-2.0, -2.0, 0.0, 0.0, 0.0, +1.0, 0.0, 1.0],
                         ], dtype=np.float32)
    indices = np.array([3, 2, 1, 0], dtype=np.int32)

    mesh = create_mesh_simple(context, vertices, indices)
    return mesh


def create_mesh_simple(context, vertices, indices):
    print("create_mesh_simple:", vertices, indices)
    vertices_ptr = pyrpr.ffi.cast("float *", vertices.ctypes.data)
    # test ptr
    numpy.testing.assert_almost_equal(vertices.flatten(),
                                      np.array([vertices_ptr[i] for i in range(np.product(vertices.shape))]))
    normals_ptr = vertices_ptr + 3
    uvs_ptr = vertices_ptr + 6
    indices_ptr = pyrpr.ffi.cast("rpr_int *", indices.ctypes.data)
    assert 4 == indices[0].nbytes
    numpy.testing.assert_almost_equal(indices, np.array([indices_ptr[i] for i in range(np.product(indices.shape))]))
    num_face_vertices_ptr = pyrpr.ffi.new('rpr_int*', len(indices))

    mesh = pyrpr.Shape()
    pyrpr.ContextCreateMesh(context,
                            vertices_ptr, len(vertices), vertices[0].nbytes,
                            normals_ptr, len(vertices), vertices[0].nbytes,
                            uvs_ptr, len(vertices), vertices[0].nbytes,
                            indices_ptr, indices[0].nbytes,
                            indices_ptr, indices[0].nbytes,
                            indices_ptr, indices[0].nbytes,
                            num_face_vertices_ptr, 1, mesh)
    return mesh


def create_mesh(context,
                _vertices, _normals, _uvs,
                _vertex_indices, _normal_indices, _uv_indices,
                _num_face_vertices):
    vertices = np.array(_vertices, dtype=np.float32)
    normals = np.array(_normals, dtype=np.float32)
    uvs = np.array(_uvs, dtype=np.float32) if _uvs is not None else None

    vertex_indices = np.array(_vertex_indices, dtype=np.int32)
    normal_indices = np.array(_normal_indices, dtype=np.int32)
    uv_indices = np.array(_uv_indices, dtype=np.int32) if _uv_indices is not None else None

    num_face_vertices = np.array(_num_face_vertices, dtype=np.int32)

    vertices_ptr = pyrpr.ffi.cast("float *", vertices.ctypes.data)
    normals_ptr = pyrpr.ffi.cast("float *", normals.ctypes.data)
    uvs_ptr = pyrpr.ffi.cast("float *", uvs.ctypes.data) if uvs is not None else pyrpr.ffi.NULL
    vertex_indices_ptr = pyrpr.ffi.cast("rpr_int *", vertex_indices.ctypes.data)
    normal_indices_ptr = pyrpr.ffi.cast("rpr_int *", normal_indices.ctypes.data)
    uv_indices_ptr = pyrpr.ffi.cast("rpr_int *", uv_indices.ctypes.data) if uv_indices is not None else pyrpr.ffi.NULL
    num_face_vertices_ptr = pyrpr.ffi.cast('rpr_int *', num_face_vertices.ctypes.data)

    mesh = pyrpr.Shape()
    pyrpr.ContextCreateMesh(context,
                            vertices_ptr, len(vertices), vertices[0].nbytes,
                            normals_ptr, len(normals), normals[0].nbytes,
                            uvs_ptr, len(uvs) if uvs is not None else 0, uvs[0].nbytes if uvs is not None else 0,
                            vertex_indices_ptr, vertex_indices[0].nbytes,
                            normal_indices_ptr, normal_indices[0].nbytes,
                            uv_indices_ptr, uv_indices[0].nbytes if uv_indices is not None else 0,
                            num_face_vertices_ptr, len(num_face_vertices), mesh)
    return mesh


def create_simple_frame_buffer_setup(context, resolution=(320, 240)):
    desc = pyrpr.ffi.new("rpr_framebuffer_desc*")
    desc.fb_width = resolution[0]
    desc.fb_height = resolution[1]
    fmt = (4, pyrpr.COMPONENT_TYPE_FLOAT32)
    frame_buffer = pyrpr.FrameBuffer()
    pyrpr.ContextCreateFrameBuffer(context, fmt, desc, frame_buffer)
    pyrpr.ContextSetAOV(context, pyrpr.AOV_COLOR, frame_buffer)
    pyrpr.ContextSetParameter1u(context, b'rendermode', pyrpr.RENDER_MODE_TEXCOORD)
    return frame_buffer


def create_simple_render_setup(context, scene, resolution=(320, 240)):
    camera = pyrpr.Camera()
    pyrpr.ContextCreateCamera(context, camera)
    pyrpr.CameraLookAt(camera, 0, 0, 7, 0, 0, 0, 0, 1, 0)
    pyrpr.SceneSetCamera(scene, camera)

    return create_simple_frame_buffer_setup(context, resolution=resolution), camera


def get_frame_buffer_image(frame_buffer, frame_buffer_size):
    fb_data_size_ptr = pyrpr.ffi.new('size_t*', 0)
    pyrpr.FrameBufferGetInfo(frame_buffer, pyrpr.FRAMEBUFFER_DATA, 0, pyrpr.ffi.NULL, fb_data_size_ptr);

    fb_data_size = fb_data_size_ptr[0]

    arr = np.empty((frame_buffer_size[1], frame_buffer_size[0], 4), dtype=np.float32)
    assert arr.nbytes == fb_data_size, (arr.nbytes, fb_data_size)

    pyrpr.FrameBufferGetInfo(frame_buffer, pyrpr.FRAMEBUFFER_DATA, fb_data_size,
                             pyrpr.ffi.cast('float*', arr.ctypes.data), pyrpr.ffi.NULL)

    return arr


def create_striped_sky_image(size=(256, 256), intensity=(1,) * 3):
    width, height = size
    im = np.ones((height, width, 4), dtype=np.float32)
    # make x-red gradient, y-green gradient, and blue hor. stripes
    im[:, :, 0] = np.linspace(0, 1, height, dtype=np.float32)[:, np.newaxis]
    im[:, :, 1] = np.linspace(0, 1, width, dtype=np.float32)[np.newaxis, :]
    im[:, :, 2] = (np.modf(np.linspace(0, height * 0.5, height, endpoint=False, dtype=np.float32))[0] < 0.5)[:,
                  np.newaxis] * intensity[2]
    im[:, :, 3] = 1
    # with open('im.list', 'w') as f:
    #     f.write(repr(im.tolist()))
    return im


class SimpleRenderFixture:
    def __init__(self, context, scene, name=None, render_resolution=(320, 240)):
        self.iter_count = 10
        self.set_name(name)
        self.context = context
        self.scene = scene
        self.matsys = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(self.context, 0, self.matsys)
        context = self.context
        scene = self.scene
        pyrpr.ContextSetScene(context, scene)
        self.mesh = None

        self.render_resolution = render_resolution

        self.frame_buffer = None

    def destroy(self):
        self.scene = None
        self.mesh = None
        self.camera = None
        self.matsys = None
        self.frame_buffer = None
        self.context = None

    def set_name(self, name):
        self.name = name

    def set_iter_count(self, value):
        self.iter_count = value

    def __enter__(self):
        if not self.frame_buffer:
            self.frame_buffer, self.camera = create_simple_render_setup(self.context, self.scene,
                                                                        self.render_resolution)
            pyrpr.ContextSetParameter1u(self.context, b'rendermode', pyrpr.RENDER_MODE_GLOBAL_ILLUMINATION)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            return False
        pyrpr.FrameBufferClear(self.frame_buffer)

        for i in range(self.iter_count):
            pyrpr.ContextRender(self.context)

        check_framebuffer_agains_baseline(self.frame_buffer, self.name)

    def set_shader(self, shader):
        pyrpr.ShapeSetMaterial(self.mesh, shader)


class SimpleMaterialRenderFixture(SimpleRenderFixture):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mesh = add_simple_quad(self.context, self.scene)


@pytest.fixture(scope='function')
def context_fixture(request):
    self = request.function.__self__

    # print('\n'.join(dir(ffi)))

    # print(dir(__rpr.lib))

    if not os.path.isdir(".rprtrace"):
        os.mkdir(".rprtrace")
    pyrpr.ContextSetParameterString(None, b'tracingfolder', os.path.abspath(".rprtrace").encode('latin1'))
    pyrpr.ContextSetParameter1u(None, b'tracing', True)

    tahoe_plugin_id = pyrpr.RegisterPlugin(str(tahoe_path).encode('ascii'))

    assert -1 != tahoe_plugin_id, tahoe_path

    plugins = [tahoe_plugin_id]
    pluginCount = len(plugins)

    self.context = pyrpr.Context(plugins, get_gpu_creation_flags(), cache_path=ensure_core_cache_folder())
    assert pyrpr.SUCCESS == self.context.create_result
    context = self.context
    basic_render_settings(context)
    yield

    self.context.delete()


def basic_render_settings(context):
    pyrpr.ContextSetParameter1u(context, b"aasamples", 1)
    pyrpr.ContextSetParameter1u(context, b"aacellsize", 1)
    pyrpr.ContextSetParameter1u(context, b"imagefilter.type", pyrpr.FILTER_BOX)
    pyrpr.ContextSetParameter1f(context, b"imagefilter.box.radius", 0.0)


@pytest.fixture(scope='function')
def scene_fixture(context_fixture, request):
    # assert False,str(dir(request))
    # for name in dir(request):
    #     print('!!!!!!!!!!!!!!!', name, getattr(request, name))
    # assert False
    self = request.function.__self__
    self.scene = pyrpr.Scene(self.context)
    yield
    self.scene.delete()


@pytest.fixture(scope='function')
def simple_render_fixture(context_fixture, scene_fixture, request):
    self = request.function.__self__
    self.render_fixture = SimpleRenderFixture(self.context, self.scene)
    yield self.render_fixture
    self.render_fixture.destroy()


@pytest.fixture(scope='function')
def simple_material_render_fixture(context_fixture, scene_fixture, request):
    self = request.function.__self__
    self.render_fixture = SimpleMaterialRenderFixture(self.context, self.scene)
    yield self.render_fixture
    self.render_fixture.destroy()


def get_gpu_creation_flags():
    flags = 0
    if pytest.config.option.enable_cpu:
        flags = flags | pyrpr.CREATION_FLAGS_ENABLE_CPU

    for i in pytest.config.option.enable_gpu or []:
        flags = flags | getattr(pyrpr, 'CREATION_FLAGS_ENABLE_GPU' + str(i))

    return flags or pyrpr.CREATION_FLAGS_ENABLE_GPU0


class SimpleRender:
    check_lock = threading.Lock()

    def __init__(self):
        pyrpr.ContextSetParameter1u(None, b'tracing', False)

        plugin_id = pyrpr.RegisterPlugin(str(tahoe_path).encode('ascii'))
        assert -1 != plugin_id
        self.context = pyrpr.Context([plugin_id], get_gpu_creation_flags(), cache_path=ensure_core_cache_folder())
        assert pyrpr.SUCCESS == self.context.create_result
        basic_render_settings(self.context)

        self.scene = pyrpr.Scene(self.context)

        self.success = False

    def render(self):
        context = self.context
        scene = self.scene
        pyrpr.ContextSetScene(context, scene)

        # keep mesh reference so it's not deleted prematurely
        mesh = add_simple_quad(context, scene)

        frame_buffer, camera = create_simple_render_setup(context, scene)

        pyrpr.FrameBufferClear(frame_buffer)
        for i in range(1000):
            pyrpr.ContextRender(context)

        with self.check_lock:
            check_framebuffer_agains_baseline(frame_buffer, 'test_simple')
        self.success = True


class LogThread(threading.Thread):
    done = False

    def run(self):
        while not self.done:
            sys.stdout.flush()
            time.sleep(0)


class TestContext:
    @pytest.mark.skip
    def test_multithreaded(self):

        if not os.path.isdir(".rprtrace"):
            os.mkdir(".rprtrace")
        pyrpr.ContextSetParameterString(None, b'tracingfolder', os.path.abspath(".rprtrace").encode('latin1'))
        pyrpr.ContextSetParameter1u(None, b'tracing', True)

        log_thread = LogThread()
        log_thread.start()

        threads = []

        try:
            for i in range(1):
                renderer = SimpleRender()
                thread = threading.Thread(target=renderer.render)
                thread.start()
                threads.append((thread, renderer))
            print('threads started')

            renderers = []
            for i in range(100):
                print('renderer: ', i)
                renderer = SimpleRender()
                renderers.append(renderer)
                print('renderer: ', i, 'done')
                # thread.start()
            # assert not threads[0][1].success, 'main render thread needs to be running for this test'

            print('threads created')

            # for thread, renderer in threads:
            #     thread.start()
        finally:
            print('joining threads:')
            for thread, renderer in threads:
                if thread.is_alive():
                    thread.join()
            print('joining threads done')
            log_thread.done = True
            if log_thread.is_alive():
                log_thread.join()

        for thread, renderer in threads:
            assert renderer.success


def create_image(colors, context, image_shape):
    desc = pyrpr.ffi.new("rpr_image_desc*")
    desc.image_width = image_shape[
        1];  # shape as in numpy has width in [1], good, not as used to have size=(width, heith) as in PIL
    desc.image_height = image_shape[0];
    desc.image_depth = 0;
    desc.image_row_pitch = desc.image_width * pyrpr.ffi.sizeof('rpr_float') * 4;
    desc.image_slice_pitch = 0;
    img = pyrpr.Image()
    pyrpr.ContextCreateImage(context, (4, pyrpr.COMPONENT_TYPE_FLOAT32), desc,
                             pyrpr.ffi.cast("float *", colors.ctypes.data), img)
    return img


@pytest.mark.usefixtures('scene_fixture')
class Test:
    def get_context_handle(self):
        return self.context._get_handle()

    def test_wrapper(self):

        # make sure non-inited node works
        pyrpr.MaterialNode()

    def test_simple(self):
        context = self.context

        contextParameterCountPtr = pyrpr.ffi.new('size_t *', 0)
        pyrpr.ContextGetInfo(self.context, pyrpr.CONTEXT_PARAMETER_COUNT, pyrpr.ffi.sizeof('size_t'),
                             contextParameterCountPtr, pyrpr.ffi.NULL)

        contextParameterCount = contextParameterCountPtr[0]
        assert 46 == contextParameterCount

        types = set()
        for i in range(contextParameterCount):
            sizePtr = pyrpr.ffi.new('size_t *', 0)
            pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_NAME_STRING, 0, pyrpr.ffi.NULL, sizePtr)
            size = sizePtr[0]

            namePtr = pyrpr.ffi.new('char[]', size)
            pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_NAME_STRING, size, namePtr, pyrpr.ffi.NULL)
            name = pyrpr.ffi.string(namePtr)

            sizePtr = pyrpr.ffi.new('size_t *', 0)
            pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_DESCRIPTION, 0, pyrpr.ffi.NULL, sizePtr)
            size = sizePtr[0]

            descPtr = pyrpr.ffi.new('char[]', size)
            pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_DESCRIPTION, size, descPtr, pyrpr.ffi.NULL)
            desc = pyrpr.ffi.string(descPtr)

            typePtr = pyrpr.ffi.new('rpr_int*')
            pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_TYPE, pyrpr.ffi.sizeof('rpr_int'), typePtr,
                                          pyrpr.ffi.NULL)
            type = typePtr[0]
            types.add(type)

            # UINT: 8 FLOAT: 1 FLOAT4: 4 STRING: 6

            xxx = {
                pyrpr.PARAMETER_TYPE_UINT: ('rpr_uint', 1),
                pyrpr.PARAMETER_TYPE_FLOAT: ('rpr_float', 1),
                pyrpr.PARAMETER_TYPE_FLOAT4: ('rpr_float', 4),
                pyrpr.PARAMETER_TYPE_STRING: ('char', None)
            }

            core_type_name, core_type_count = xxx[type]

            valuePtr = pyrpr.ffi.new(core_type_name + '*', core_type_count)
            try:
                pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_VALUE, pyrpr.ffi.sizeof(core_type_name),
                                              valuePtr, pyrpr.ffi.NULL)
                value = valuePtr[0]
            except pyrpr.CoreError:
                value = '<UNSUPPORTED>'

            print(name, value, desc)

        type2name = {getattr(pyrpr, name): name.replace('PARAMETER_TYPE_', '') for name in dir(pyrpr)
                     if name.startswith('PARAMETER_TYPE_')}

        print('types:', ' '.join("%s: %s" % (type2name[t], t) for t in types))

        scene = self.scene

        scene_shape_count_ptr = pyrpr.ffi.new('size_t *', 0)
        pyrpr.SceneGetInfo(scene, pyrpr.SCENE_SHAPE_COUNT, pyrpr.ffi.sizeof('size_t'), scene_shape_count_ptr,
                           pyrpr.ffi.NULL)
        scene_shape_count = scene_shape_count_ptr[0]

        pyrpr.ContextSetScene(context, scene)

        # make simple quad scene for the test
        mesh = add_simple_quad(context, scene)

        # test that name is set
        pyrpr.ObjectSetName(mesh._get_handle(), b'hello')

        sizePtr = pyrpr.ffi.new('size_t *', 0)
        pyrpr.ShapeGetInfo(mesh, pyrpr.OBJECT_NAME, 0, pyrpr.ffi.NULL, sizePtr)
        size = sizePtr[0]

        namePtr = pyrpr.ffi.new('char[]', size)
        pyrpr.ShapeGetInfo(mesh, pyrpr.OBJECT_NAME, size, namePtr, pyrpr.ffi.NULL)
        name = pyrpr.ffi.string(namePtr)
        assert name == b'hello', name

        mesh_polygon_count = pyrpr.ffi.new('size_t*', 0)
        # print(pyrpr.ffi.typeof(pyrpr.lib.frMeshGetInfo).args)
        pyrpr.MeshGetInfo(mesh, pyrpr.MESH_POLYGON_COUNT, pyrpr.ffi.sizeof('size_t'), mesh_polygon_count,
                          pyrpr.ffi.NULL)
        assert 1 == mesh_polygon_count[0], mesh_polygon_count[0]

        frame_buffer, camera = create_simple_render_setup(context, scene)

        # checking our wrapper
        with pytest.raises(pyrpr.CoreError):
            pyrpr.ContextSetParameter1u(context, b'rendermodadudadu', pyrpr.RENDER_MODE_TEXCOORD)

        pyrpr.FrameBufferClear(frame_buffer)

        pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_simple')

    def test_simple_api(self):
        context = self.context

        contextParameterCountPtr = pyrpr.ffi.new('size_t *', 0)
        pyrpr.ContextGetInfo(self.context, pyrpr.CONTEXT_PARAMETER_COUNT, pyrpr.ffi.sizeof('size_t'),
                             contextParameterCountPtr, pyrpr.ffi.NULL)

        contextParameterCount = contextParameterCountPtr[0]
        assert 46 == contextParameterCount

        for i in range(contextParameterCount):
            sizePtr = pyrpr.ffi.new('size_t *', 0)
            pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_NAME_STRING, 0, pyrpr.ffi.NULL, sizePtr)
            size = sizePtr[0]

            namePtr = pyrpr.ffi.new('char[]', size)
            pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_NAME_STRING, size, namePtr, pyrpr.ffi.NULL)
            name = pyrpr.ffi.string(namePtr)

        scene = self.scene

        scene_shape_count_ptr = pyrpr.ffi.new('size_t *', 0)
        pyrpr.SceneGetInfo(scene, pyrpr.SCENE_SHAPE_COUNT, pyrpr.ffi.sizeof('size_t'), scene_shape_count_ptr,
                           pyrpr.ffi.NULL)
        scene_shape_count = scene_shape_count_ptr[0]

        # make simple quad scene for the test
        mesh = add_simple_quad(context, scene)

        # test that name is set
        pyrpr.ObjectSetName(mesh._get_handle(), b'hello')

        sizePtr = pyrpr.ffi.new('size_t *', 0)
        pyrpr.ShapeGetInfo(mesh, pyrpr.OBJECT_NAME, 0, pyrpr.ffi.NULL, sizePtr)
        size = sizePtr[0]

        namePtr = pyrpr.ffi.new('char[]', size)
        pyrpr.ShapeGetInfo(mesh, pyrpr.OBJECT_NAME, size, namePtr, pyrpr.ffi.NULL)
        name = pyrpr.ffi.string(namePtr)
        assert name == b'hello', name

        mesh_polygon_count = pyrpr.ffi.new('size_t*', 0)
        # print(pyrpr.ffi.typeof(pyrpr.lib.frMeshGetInfo).args)
        pyrpr.MeshGetInfo(mesh, pyrpr.MESH_POLYGON_COUNT, pyrpr.ffi.sizeof('size_t'), mesh_polygon_count,
                          pyrpr.ffi.NULL)
        assert 1 == mesh_polygon_count[0], mesh_polygon_count[0]

        frame_buffer, camera = create_simple_render_setup(context, scene)

        # checking our wrapper
        with pytest.raises(pyrpr.CoreError):
            pyrpr.ContextSetParameter1u(context, b'rendermodadudadu', pyrpr.RENDER_MODE_TEXCOORD)

        pyrpr.FrameBufferClear(frame_buffer)
        pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_simple')

    def test_simplest(self):
        context = self.context

        scene = self.scene

        # make simple quad scene for the test
        mesh = add_simple_quad(context, scene)

        frame_buffer, camera = create_simple_render_setup(context, scene)

        pyrpr.FrameBufferClear(frame_buffer)
        pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_simple')

    def test_instance(self):
        context = self.context

        scene = self.scene

        # make simple quad scene for the test
        mesh = create_simple_quad(context)
        pyrpr.SceneAttachShape(scene, mesh)
        transform = np.array([
            [0.25, 0, 0, 0],
            [0, 1.0, 0, 0],
            [0, 0, 1.0, 0],
            [1.0, 0.0, 0, 1],
        ], dtype=np.float32)
        pyrpr.ShapeSetTransform(mesh, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

        instance = pyrpr.Shape()
        pyrpr.ContextCreateInstance(context, mesh, instance)
        pyrpr.SceneAttachShape(scene, instance)
        transform = np.array([
            [0.25, 0, 0, 0],
            [0, 1.0, 0, 0],
            [0, 0, 1.0, 0],
            [-1.0, 0.0, 0, 1],
        ], dtype=np.float32)
        pyrpr.ShapeSetTransform(instance, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

        frame_buffer, camera = create_simple_render_setup(context, scene)

        pyrpr.FrameBufferClear(frame_buffer)
        pyrpr.ContextRender(context)
        check_framebuffer_agains_baseline(frame_buffer, 'test_instance_with_proto')

        print("check visilbility flags on prototype affect prototype shape only")
        pyrpr.ShapeSetVisibilityPrimaryOnly(mesh, False)
        pyrpr.FrameBufferClear(frame_buffer)
        pyrpr.ContextRender(context)
        check_framebuffer_agains_baseline(frame_buffer, 'test_instance_proto_hidden')

        print("check visilbility flags on instance")
        pyrpr.ShapeSetVisibilityPrimaryOnly(mesh, True)
        pyrpr.ShapeSetVisibilityPrimaryOnly(instance, False)
        pyrpr.FrameBufferClear(frame_buffer)
        pyrpr.ContextRender(context)
        check_framebuffer_agains_baseline(frame_buffer, 'test_instance_hidden')

    def test_tile(self):
        context = self.context

        scene = self.scene

        # make simple quad scene for the test
        mesh = add_simple_quad(context, scene)

        frame_buffer, camera = create_simple_render_setup(context, scene, resolution=(640, 480))

        ibl, img = self.create_environment_light_simpe(context, [0.5, 0.5, 0.5, 1.0], (2, 2))

        pyrpr.EnvironmentLightSetIntensityScale(ibl, 1.0)

        pyrpr.SceneAttachLight(scene, ibl)

        pyrpr.FrameBufferClear(frame_buffer)

        pyrpr.ContextRenderTile(context, 160, 480, 120, 360)
        pyrpr.ContextRenderTile(context, 0, 320, 0, 240)

        check_framebuffer_agains_baseline(frame_buffer, 'test_tile')

    def test_load_store(self, tmpdir_factory):

        context = self.context
        scene = self.scene

        # make simple quad scene for the test
        pyrpr.SceneClear(scene)
        mesh = add_simple_quad(context, scene)
        matsys = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(context, 0, matsys)

        # create_simple_render_setup(context, scene)

        rprs_fpath = str(Path(str(tmpdir_factory.mktemp('data').join('test.rpr'))))

        try:
            result = pyrpr_load_store.export(rprs_fpath, context, scene)
            assert result == 0
        except:
            assert False

    def test_motion_blur(self, simple_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_motion_blur')

        context = fixture.context

        scene = fixture.scene

        # make simple quad scene for the test
        mesh = add_simple_quad(context, scene)
        transform = np.array([
            [0.5, 0, 0, 0],
            [0, 1.0, 0, 0],
            [0, 0, 1.0, 0],
            [0, 0, 0, 1],
        ], dtype=np.float32)
        pyrpr.ShapeSetTransform(mesh, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

        # motion blur setup
        pyrpr.ShapeSetAngularMotion(mesh, 0, 0, 1, 0.1)
        # pyrpr.ShapeSetLinearMotion(mesh, 1, 0, 0)

        fixture.mesh = mesh
        fixture.set_iter_count(200)

        ibl, img = self.create_environment_light_simpe(context, [0.5, 0.5, 0.5, 1.0], (2, 2))

        pyrpr.EnvironmentLightSetIntensityScale(ibl, 1.0)

        pyrpr.SceneAttachLight(scene, ibl)

        with fixture:
            pyrpr.CameraSetExposure(fixture.camera, 10)
            pass

    def test_camera_cubemap_stereo(self):
        context = self.context

        scene = self.scene

        # make simple quad scene for the test
        mesh = add_simple_quad(context, scene)

        frame_buffer, camera = create_simple_render_setup(context, scene)

        pyrpr.CameraSetMode(camera, pyrpr.CAMERA_MODE_CUBEMAP_STEREO)

        pyrpr.FrameBufferClear(frame_buffer)
        pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_camera_cubemap_stereo')

    def test_aa(self):
        context = self.context

        scene = self.scene

        # make simple triangle
        vertices = np.array([[-2.0, 2.0, 0.0, 0.0, 0.0, +1.0, 0.0, 1.0],
                             [2.0, 2.0, 0.0, 0.0, 0.0, +1.0, 1.0, 0.0],
                             [2.0, -2.0, 0.0, 0.0, 0.0, +1.0, 1.0, 1.0],
                             ], dtype=np.float32)
        indices = np.array([2, 1, 0], dtype=np.int32)

        meshes = []
        for x in range(10):
            for y in range(10):
                mesh = create_mesh_simple(context, vertices, indices)
                meshes.append(mesh)
                pyrpr.SceneAttachShape(scene, mesh)
                transform = np.array([
                    [0.1, 0, 0, 0],
                    [0, 0.1, 0, 0],
                    [0, 0, 0.1, 0],
                    [0.5 * x - 0.5 * 4.5, 0.5 * y - 0.5 * 4.5, 0, 1],
                ], dtype=np.float32)
                pyrpr.ShapeSetTransform(mesh, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

        frame_buffer, camera = create_simple_render_setup(context, scene, resolution=(128, 128))

        def check_fb(expected):
            check_framebuffer_agains_baseline(frame_buffer, expected,
                                              max_average_deviation=0.002,
                                              max_std_dev=0.005)

        def check(iterations, expected):
            pyrpr.FrameBufferClear(frame_buffer)
            for i in range(iterations):
                pyrpr.ContextRender(context)

            check_fb(expected)

        check(10, 'test_aa_default_i10')

        pyrpr.ContextSetParameter1u(context, b'aacellsize', 1)
        pyrpr.ContextSetParameter1u(context, b'imagefilter.type', pyrpr.FILTER_BOX)
        pyrpr.ContextSetParameter1f(context, b'imagefilter.box.radius', 1.0)

        pyrpr.ContextSetParameter1u(context, b'aasamples', 16)
        check(50, 'test_aa_box_r1_samples16_i50')

        # check that aasamples is same(converges) as iterations multiplied
        pyrpr.ContextSetParameter1u(context, b'aasamples', 1)
        check(400, 'test_aa_box_r1_samples16_i50')

        pyrpr.ContextSetParameter1f(context, b'imagefilter.box.radius', 0.5)
        check(10, 'test_aa_box_r05')

        pyrpr.ContextSetParameter1f(context, b'imagefilter.box.radius', 0.0)
        check(10, 'test_aa_box_r0')

        pyrpr.ContextSetParameter1f(context, b'imagefilter.box.radius', 1.5)
        check(10, 'test_aa_box_r15')

        pyrpr.ContextSetParameter1u(context, b'imagefilter.type', pyrpr.FILTER_MITCHELL)
        pyrpr.ContextSetParameter1f(context, b'imagefilter.mitchell.radius', 1.5)
        check(100, 'test_aa_mitchell_r15')

        pyrpr.ContextSetParameter1f(context, b'imagefilter.mitchell.radius', 2.0)
        check(200, 'test_aa_mitchell_r2')

        if 0x010000255 < pyrpr.API_VERSION:
            # test setting radius to 0 turns off aa
            pyrpr.ContextSetParameter1f(context, b'imagefilter.mitchell.radius', 0.0)
            check(10, 'test_aa_default_i10')

    def test_posteffect_simple_tonemap(self):
        context = self.context

        scene = self.scene

        # make simple quad scene for the test
        mesh = add_simple_quad(context, scene)

        matsys = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(context, 0, matsys)

        shader = pyrpr.MaterialNode()
        pyrpr.MaterialSystemCreateNode(matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)
        pyrpr.MaterialNodeSetInputF(shader, b'color', 0.5, 1.0, 0.25, 1.0)
        pyrpr.ShapeSetMaterial(mesh, shader)

        resolution = (320, 240)

        camera = pyrpr.Camera()
        pyrpr.ContextCreateCamera(context, camera)
        pyrpr.CameraLookAt(camera, 0, 0, 7, 0, 0, 0, 0, 1, 0)
        pyrpr.SceneSetCamera(scene, camera)

        desc = pyrpr.ffi.new("rpr_framebuffer_desc*")
        desc.fb_width = resolution[0]
        desc.fb_height = resolution[1]
        fmt = (4, pyrpr.COMPONENT_TYPE_FLOAT32)
        frame_buffer = pyrpr.FrameBuffer()
        pyrpr.ContextCreateFrameBuffer(context, fmt, desc, frame_buffer)
        pyrpr.ContextSetAOV(context, pyrpr.AOV_COLOR, frame_buffer)

        desc = pyrpr.ffi.new("rpr_framebuffer_desc*")
        desc.fb_width = resolution[0]
        desc.fb_height = resolution[1]
        fmt = (4, pyrpr.COMPONENT_TYPE_FLOAT32)
        frame_buffer_posteffect = pyrpr.FrameBuffer()
        pyrpr.ContextCreateFrameBuffer(context, fmt, desc, frame_buffer_posteffect)

        normalization = pyrpr.PostEffect()
        pyrpr.ContextCreatePostEffect(context, pyrpr.POST_EFFECT_NORMALIZATION,
                                      normalization)
        pyrpr.ContextAttachPostEffect(context, normalization)

        simple_tonemap = pyrpr.PostEffect()
        pyrpr.ContextCreatePostEffect(context, pyrpr.POST_EFFECT_SIMPLE_TONEMAP,
                                      simple_tonemap)
        pyrpr.ContextAttachPostEffect(context, simple_tonemap)

        white_balance = pyrpr.PostEffect()
        pyrpr.ContextCreatePostEffect(context, pyrpr.POST_EFFECT_WHITE_BALANCE,
                                      white_balance)
        pyrpr.ContextAttachPostEffect(context, white_balance)

        pyrpr.FrameBufferClear(frame_buffer)
        for i in range(10):
            pyrpr.ContextRender(context)

        pyrpr.FrameBufferClear(frame_buffer_posteffect)
        pyrpr.ContextResolveFrameBuffer(context, frame_buffer, frame_buffer_posteffect)

        im = get_frame_buffer_image(frame_buffer_posteffect, resolution)

        try:
            check_image_agains_baseline(im[..., :3], 'test_posteffect_simple_tonemap', )
        finally:

            # pyrpr.ContextDetachPostEffect(context, white_balance)
            pyrpr.ContextDetachPostEffect(context, simple_tonemap)
            del simple_tonemap
            pyrpr.ContextDetachPostEffect(context, normalization)
            del normalization
            pyrpr.ContextDetachPostEffect(context, white_balance)
            del white_balance

    aov_names = [name for name in dir(pyrpr) if name.startswith('AOV_')
                 if name not in ('AOV_COLOR', 'AOV_MAX')]
    assert 13 == len(aov_names), "Make sure aovs are actually collected, please adjust number to expected aov count"

    @pytest.mark.parametrize('aov_name', aov_names)
    def test_aov(self, aov_name):
        context = self.context

        matsys = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(context, 0, matsys)

        scene = self.scene

        # RPR 1.256 requires a light in the scene for AOV to work
        ibl, img = self.create_environment_light_simpe(context, (1,) * 4, (2, 2))
        pyrpr.SceneAttachLight(scene, ibl)

        meshes = []
        shaders = []

        for i in range(2):
            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(matsys,
                                           pyrpr.MATERIAL_NODE_DIFFUSE
                                           if i % 2 else pyrpr.MATERIAL_NODE_EMISSIVE, shader)
            pyrpr.MaterialNodeSetInputF(shader, b'color', 1.0, 1.0, 1.0, 1.0)
            shaders.append(shader)

        size = 2
        idx = 0
        for xi in range(size):
            for yi in range(size):
                # make simple quad scene for the test
                mesh = add_simple_quad(context, scene)

                x, y = (np.array([xi, yi])/(size-1)*0.2-0.1)

                transform = np.array([
                    [0.075/((size-1)*2), 0, 0, 0],
                    [0, 0.075/((size-1)*2), 0, 0],
                    [0, 0, 1, 0],
                    [x, y, -((x+y)+0.2)*0.2, 1],
                ], dtype=np.float32)

                pyrpr.ShapeSetTransform(mesh, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

                pyrpr.ShapeSetMaterial(mesh, shaders[xi % len(shaders)])

                pyrpr.ShapeSetObjectGroupID(mesh, 250-idx*50) # invert indices for groups just to make it different from object id

                #pyrpr.ShapeSetAngularMotion(mesh, 0, 0, 1, 0.0001)
                pyrpr.ShapeSetLinearMotion(mesh, 0, 0, 1.0)

                idx += 1

                meshes.append(mesh)

        resolution = (320, 240)

        camera = pyrpr.Camera()
        pyrpr.ContextCreateCamera(context, camera)
        pyrpr.CameraLookAt(camera, 0, 0, 0.25, 0, 0, 0, 0, 1, 0)
        pyrpr.CameraSetFocalLength(camera, 16)
        pyrpr.SceneSetCamera(scene, camera)

        # on CPU AOV not created without a light in the scene
        # so we make a dark light
        if pytest.config.option.enable_cpu and 0x010000255 >= pyrpr.API_VERSION:
            light = pyrpr.Light()
            pyrpr.ContextCreatePointLight(self.context, light)
            pyrpr.PointLightSetRadiantPower3f(light, 0, 0, 0)
            pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                                  0, 1, 0, 0,
                                                  0, 0, 1, 1,
                                                  0, 0, 0, 1])
            pyrpr.SceneAttachLight(self.scene, light)

        desc = pyrpr.ffi.new("rpr_framebuffer_desc*")
        desc.fb_width = resolution[0]
        desc.fb_height = resolution[1]
        fmt = (4, pyrpr.COMPONENT_TYPE_FLOAT32)
        frame_buffer = pyrpr.FrameBuffer()
        pyrpr.ContextCreateFrameBuffer(context, fmt, desc, frame_buffer)
        pyrpr.ContextSetAOV(context, pyrpr.AOV_COLOR, frame_buffer)

        desc = pyrpr.ffi.new("rpr_framebuffer_desc*")
        desc.fb_width = resolution[0]
        desc.fb_height = resolution[1]
        fmt = (4, pyrpr.COMPONENT_TYPE_FLOAT32)
        frame_buffer_aov = pyrpr.FrameBuffer()
        pyrpr.ContextCreateFrameBuffer(context, fmt, desc, frame_buffer_aov)
        pyrpr.ContextSetAOV(context, getattr(pyrpr, aov_name), frame_buffer_aov)

        pyrpr.ContextSetParameter1u(context, b'rendermode', pyrpr.RENDER_MODE_GLOBAL_ILLUMINATION)
        pyrpr.FrameBufferClear(frame_buffer)
        pyrpr.FrameBufferClear(frame_buffer_aov)

        for i in range(10):
            pyrpr.ContextRender(context)

        frame_buffer_normalize = pyrpr.FrameBuffer()
        pyrpr.ContextCreateFrameBuffer(context, fmt, desc, frame_buffer_normalize)

        normalize = pyrpr.PostEffect()
        pyrpr.ContextCreatePostEffect(context, pyrpr.POST_EFFECT_NORMALIZATION, normalize)
        pyrpr.ContextAttachPostEffect(context, normalize)

        pyrpr.ContextResolveFrameBuffer(context, frame_buffer_aov, frame_buffer_normalize)

        im = get_frame_buffer_image(frame_buffer_normalize, resolution)

        # RPR 1.273 has issue with index-type aovs being divided by 255, i.e. instead of 1, 2, 3
        # it has 0.00392, 0.00784 ... which is fine but 1, 2, 3 feels more 'right' for indices
        # "group_id" is not included here because it's already big values set above
        aov_idx_type = any(name in aov_name.lower() for name in ['material_idx', 'object_id'])
        if aov_idx_type:
            im *= 255/5

        if 'velocity' in aov_name.lower():
            im = im*0.2+0.5

        if 'world' in aov_name.lower():
            im = im*2+0.5

        check_image_agains_baseline2(
            im[..., :3], 'test_aov_' + aov_name.replace('AOV_', '').lower())

    def test_pentagonal(self):
        context = self.context

        scene = self.scene

        # make simple quad scene for the test
        vertices = np.array([[-2.0, 2.0, 0.0, 0.0, 0.0, +1.0, 0.0, 0.0],
                             [2.0, 2.0, 0.0, 0.0, 0.0, +1.0, 1.0, 0.0],
                             [2.0, -2.0, 0.0, 0.0, 0.0, +1.0, 1.0, 1.0],
                             [-2.0, -2.0, 0.0, 0.0, 0.0, +1.0, 0.0, 1.0],
                             [-3.0, -0.0, 0.0, 0.0, 0.0, +1.0, 0.0, 1.0],
                             ], dtype=np.float32)
        indices = np.array([3, 2, 1, 0, 4], dtype=np.int32)

        with pytest.raises(pyrpr.CoreError):
            mesh = create_mesh_simple(context, vertices, indices)

    def test_set_scene(self, simple_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_emissive')
        scene = fixture.scene
        mesh0 = add_simple_quad(self.context, scene)
        with fixture:
            shader0 = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader0)
            pyrpr.MaterialNodeSetInputF(shader0, b'color', 0.5, 1.0, 0.25, 1.0)
            pyrpr.ShapeSetMaterial(mesh0, shader0)

        old_scene = fixture.scene

        scene = pyrpr.Scene(fixture.context)
        camera = pyrpr.Camera()
        pyrpr.ContextCreateCamera(self.context, camera)
        pyrpr.CameraLookAt(camera, 0, 0, 7, 0, 0, 0, 0, 1, 0)
        pyrpr.SceneSetCamera(scene, camera)

        mesh1 = add_simple_quad(self.context, scene)

        fixture.scene = scene
        pyrpr.ContextSetScene(fixture.context, scene)
        fixture.set_name('test_set_scene_second')
        with fixture:
            shader1 = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader1)
            pyrpr.MaterialNodeSetInputF(shader1, b'color', 1.0, 0.5, 1.0, 1.0)
            pyrpr.ShapeSetMaterial(mesh1, shader1)

        fixture.scene = old_scene
        pyrpr.ContextSetScene(fixture.context, old_scene)
        fixture.set_name('test_set_scene_first')
        with fixture:
            pass

    def test_camera(self):
        context = self.context

        scene = self.scene

        pyrpr.ContextSetScene(context, scene)

        mesh = add_simple_quad(context, scene)

        camera = pyrpr.Camera()
        pyrpr.ContextCreateCamera(context, camera)
        pyrpr.CameraLookAt(camera, 0, 0, 7, 0, 0, 6, 0, 1, 0)
        pyrpr.SceneSetCamera(scene, camera)

        frame_buffer = create_simple_frame_buffer_setup(context)

        pyrpr.FrameBufferClear(frame_buffer)
        pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_camera')

        # AMDBLENDER-96
        # test setting same transform with SetTransform
        camera = pyrpr.Camera()
        pyrpr.ContextCreateCamera(context, camera)
        matrix = np.array(
            [[1, 0, 0, 0],
             [0, 1, 0, 0],
             [0, 0, 1, 0],
             [0, 0, 7, 1]], dtype=np.float32)
        # pyrpr.CameraSetTransform(camera, False, pyrpr.ffi.cast('float*', matrix.ctypes.data))
        pyrpr.CameraLookAt(camera, 0, 0, 7, 0, 0, 0, 0, 1, 0)
        pyrpr.SceneSetCamera(scene, camera)

        pyrpr.FrameBufferClear(frame_buffer)
        pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_camera')

    def test_envlight(self):
        context = self.context

        scene = self.scene

        pyrpr.ContextSetScene(context, scene)

        ibl_shape = (32, 32)
        ibl_color = [1.0, 0.5, 0.5, 1.0]

        ibl, img = self.create_environment_light_simpe(context, ibl_color, ibl_shape)

        pyrpr.EnvironmentLightSetIntensityScale(ibl, 1.0)

        pyrpr.SceneAttachLight(scene, ibl)

        pyrpr.ContextSetScene(context, scene)

        mesh = add_simple_quad(context, scene)

        matsys = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(context, 0, matsys)

        shader = pyrpr.MaterialNode()
        pyrpr.MaterialSystemCreateNode(matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)

        pyrpr.MaterialNodeSetInputF(shader, b'color', 0.25, 1.0, 1.0, 1.0)

        pyrpr.ShapeSetMaterial(mesh, shader)

        frame_buffer, camera = create_simple_render_setup(context, scene, resolution=(80, 60))

        pyrpr.ContextSetParameter1u(context, b'rendermode', pyrpr.RENDER_MODE_GLOBAL_ILLUMINATION)

        pyrpr.FrameBufferClear(frame_buffer)

        for i in range(100):
            pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_envlight')

        # test regression in RPR 1.257 that attaching a new light in CLEARED scene uses color of IBL was set before
        pyrpr.SceneClear(scene)

        light = pyrpr.Light()
        pyrpr.ContextCreatePointLight(self.context, light)
        pyrpr.PointLightSetRadiantPower3f(light, 1, 1, 1)
        pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                              0, 1, 0, 0,
                                              0, 0, 1, 1,
                                              0, 0, 0, 1])
        pyrpr.SceneAttachLight(scene, light)

        mesh = add_simple_quad(context, scene)

        frame_buffer, camera = create_simple_render_setup(context, scene, resolution=(80, 60))

        pyrpr.ContextSetParameter1u(context, b'rendermode', pyrpr.RENDER_MODE_GLOBAL_ILLUMINATION)

        pyrpr.FrameBufferClear(frame_buffer)

        for i in range(100):
            pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_envlight_replaced_with_point')

    def create_environment_light_simpe(self, context, ibl_color, ibl_shape):
        desc = pyrpr.ffi.new("rpr_image_desc*")
        desc.image_width = ibl_shape[
            1];  # shape as in numpy has width in [1], good, not as used to have size=(width, heith) as in PIL
        desc.image_height = ibl_shape[0];
        desc.image_depth = 0;
        desc.image_row_pitch = desc.image_width * pyrpr.ffi.sizeof('rpr_float') * 4;
        desc.image_slice_pitch = 0;
        img = pyrpr.Image()
        colors = np.full(ibl_shape + (4,), ibl_color, dtype=np.float32)
        pyrpr.ContextCreateImage(context, (4, pyrpr.COMPONENT_TYPE_FLOAT32), desc,
                                 pyrpr.ffi.cast("float *", colors.ctypes.data), img)
        ibl = pyrpr.Light()
        pyrpr.ContextCreateEnvironmentLight(context, ibl)
        pyrpr.EnvironmentLightSetImage(ibl, img)
        return ibl, img

    def test_ward_degenerate_uv(self):
        context = self.context

        scene = self.scene

        pyrpr.ContextSetScene(context, scene)

        ibl_shape = (2, 2)

        ibl, img = self.create_environment_light_simpe(context, [1.0, 0.5, 0.5, 1.0], ibl_shape)

        pyrpr.EnvironmentLightSetIntensityScale(ibl, 1.0)

        pyrpr.SceneAttachLight(scene, ibl)

        pyrpr.ContextSetScene(context, scene)

        vertices = np.array([[-2.0, 2.0, 0.0, 0.0, 0.0, +1.0, 0.0, 0.0],
                             [2.0, 2.0, 0.0, 0.0, 0.0, +1.0, 0.0, 0.0],
                             [2.0, -2.0, 0.0, 0.0, 0.0, +1.0, 0.0, 0.0],
                             [-2.0, -2.0, 0.0, 0.0, 0.0, +1.0, 0.0, 0.0],
                             ], dtype=np.float32)
        indices = np.array([3, 2, 1, 0], dtype=np.int32)

        mesh = create_mesh_simple(context, vertices, indices)

        pyrpr.SceneAttachShape(scene, mesh)

        mesh2 = add_simple_quad(context, scene)

        transform = np.array([
            [0.5, 0, 0, 0],
            [0, 0.5 * 0.707, -0.707, 0],
            [0, 0.707, 0.5 * 0.707, 0],
            [0, 0, 2, 1],
        ], dtype=np.float32)
        pyrpr.ShapeSetTransform(mesh2, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

        matsys = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(context, 0, matsys)

        shader = pyrpr.MaterialNode()
        pyrpr.MaterialSystemCreateNode(matsys, pyrpr.MATERIAL_NODE_WARD, shader)
        pyrpr.MaterialNodeSetInputF(shader, b'color', 1.0, 1.0, 1.0, 1.0)
        pyrpr.MaterialNodeSetInputF(shader, b'roughness_x', 0.5, 0.5, 0.5, 0.5)
        pyrpr.MaterialNodeSetInputF(shader, b'roughness_y', 0.5, 0.5, 0.5, 0.5)
        pyrpr.MaterialNodeSetInputF(shader, b'rotation', 0, 0, 0, 0)

        pyrpr.ShapeSetMaterial(mesh, shader)

        frame_buffer, camera = create_simple_render_setup(context, scene, resolution=(80, 60))

        pyrpr.ContextSetParameter1u(context, b'rendermode', pyrpr.RENDER_MODE_GLOBAL_ILLUMINATION)

        pyrpr.FrameBufferClear(frame_buffer)

        for i in range(100):
            pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_ward_degenerate_uv')

    @pytest.mark.skipif(pyrpr.API_VERSION <= 0x010000257, reason="need softer image comparison for this")
    def test_envlight_empty_scene(self):
        context = self.context

        scene = self.scene

        pyrpr.ContextSetScene(context, scene)

        ibl_shape = (32, 32)

        ibl, img = self.create_environment_light_simpe(context, [1.0, 0.5, 0.5, 1.0], ibl_shape)

        pyrpr.EnvironmentLightSetIntensityScale(ibl, 1.0)

        pyrpr.SceneAttachLight(scene, ibl)

        pyrpr.ContextSetScene(context, scene)

        # mesh = add_simple_quad(context, scene)
        #
        # # move object outside of camera
        # transform = np.array([
        #     [1, 0, 0, 0],
        #     [0, 1, 0, 0],
        #     [0, 0, 1, 0],
        #     [0, 0, 10, 1],
        # ], dtype=np.float32)
        # pyrpr.ShapeSetTransform(mesh, False, pyrpr.ffi.cast('float*', transform.ctypes.data))
        #
        # matsys = pyrpr.MaterialSystem()
        # pyrpr.ContextCreateMaterialSystem(context, 0, matsys)
        #
        # shader = pyrpr.MaterialNode()
        # pyrpr.MaterialSystemCreateNode(matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)
        #
        # pyrpr.MaterialNodeSetInputF(shader, b'color', 0.25, 1.0, 1.0, 1.0)
        #
        # pyrpr.ShapeSetMaterial(mesh, shader)

        frame_buffer, camera = create_simple_render_setup(context, scene, resolution=(80, 60))

        pyrpr.ContextSetParameter1u(context, b'rendermode', pyrpr.RENDER_MODE_GLOBAL_ILLUMINATION)

        pyrpr.FrameBufferClear(frame_buffer)

        for i in range(1):
            pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_envlight_empty_scene')

    def test_background(self):
        context = self.context

        scene = self.scene

        pyrpr.ContextSetScene(context, scene)

        ibl_shape = (32, 32)

        ibl, img = self.create_environment_light_simpe(context, [1.0, 0.0, 0.0, 1.0], ibl_shape)

        pyrpr.EnvironmentLightSetIntensityScale(ibl, 1.0)

        pyrpr.EnvironmentLightSetImage(ibl, img)

        pyrpr.SceneAttachLight(scene, ibl)

        pyrpr.ContextSetScene(context, scene)

        ibl_shape = (32, 32)

        background, background_img = self.create_environment_light_simpe(context, [0.0, 1.0, 1.0, 1.0], ibl_shape)

        pyrpr.EnvironmentLightSetIntensityScale(background, 1.0)

        pyrpr.SceneSetEnvironmentOverride(scene, pyrpr.SCENE_ENVIRONMENT_OVERRIDE_BACKGROUND, background)

        pyrpr.ContextSetScene(context, scene)

        mesh = add_simple_quad(context, scene)

        matsys = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(context, 0, matsys)

        shader = pyrpr.MaterialNode()
        pyrpr.MaterialSystemCreateNode(matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)

        pyrpr.MaterialNodeSetInputF(shader, b'color', 0.5, 0.5, 0.5, 1.0)

        pyrpr.ShapeSetMaterial(mesh, shader)

        frame_buffer, camera = create_simple_render_setup(context, scene, resolution=(80, 60))

        pyrpr.ContextSetParameter1u(context, b'rendermode', pyrpr.RENDER_MODE_GLOBAL_ILLUMINATION)

        pyrpr.FrameBufferClear(frame_buffer)

        for i in range(100):
            pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_background')

        pyrpr.SceneSetEnvironmentOverride(scene, pyrpr.SCENE_ENVIRONMENT_OVERRIDE_BACKGROUND, pyrpr.ffi.NULL)

        pyrpr.FrameBufferClear(frame_buffer)

        for i in range(100):
            pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_background_off')

    def test_background_image(self):
        context = self.context

        scene = self.scene

        pyrpr.ContextSetScene(context, scene)

        ibl_shape = (32, 32)

        ibl, img = self.create_environment_light_simpe(context, [1.0, 0.0, 0.0, 1.0], ibl_shape)

        pyrpr.EnvironmentLightSetIntensityScale(ibl, 1.0)

        pyrpr.SceneAttachLight(scene, ibl)

        pyrpr.ContextSetScene(context, scene)

        ibl_shape = (8, 8)

        desc = pyrpr.ffi.new("rpr_image_desc*")
        desc.image_width = ibl_shape[
            1];  # shape as in numpy has width in [1], good, not as used to have size=(width, heith) as in PIL
        desc.image_height = ibl_shape[0];
        desc.image_depth = 0;
        desc.image_row_pitch = desc.image_width * pyrpr.ffi.sizeof('rpr_float') * 4;
        desc.image_slice_pitch = 0;

        background_img = pyrpr.Image()

        colors = np.full(ibl_shape + (4,), [0.0, 0.0, 0.0, 1.0], dtype=np.float32)
        colors[:, :, 0] = np.linspace(0, 1, colors.shape[0], dtype=np.float32)[:, np.newaxis]
        colors[:, :, 1] = np.linspace(0, 1, colors.shape[1], dtype=np.float32)[np.newaxis, :]

        pyrpr.ContextCreateImage(context, (4, pyrpr.COMPONENT_TYPE_FLOAT32), desc,
                                 pyrpr.ffi.cast("float *", colors.ctypes.data), background_img)

        pyrpr.ImageSetWrap(background_img, pyrpr.IMAGE_WRAP_TYPE_CLAMP_TO_EDGE)

        pyrpr.SceneSetBackgroundImage(scene, background_img)

        pyrpr.ContextSetScene(context, scene)

        mesh = add_simple_quad(context, scene)

        matsys = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(context, 0, matsys)

        shader = pyrpr.MaterialNode()
        pyrpr.MaterialSystemCreateNode(matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)

        pyrpr.MaterialNodeSetInputF(shader, b'color', 0.5, 0.5, 0.5, 1.0)

        pyrpr.ShapeSetMaterial(mesh, shader)

        frame_buffer, camera = create_simple_render_setup(context, scene, resolution=(80, 60))

        pyrpr.ContextSetParameter1u(context, b'rendermode', pyrpr.RENDER_MODE_GLOBAL_ILLUMINATION)

        pyrpr.FrameBufferClear(frame_buffer)

        for i in range(100):
            pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_background_image')

        pyrpr.SceneSetBackgroundImage(scene, pyrpr.ffi.NULL)

        pyrpr.FrameBufferClear(frame_buffer)

        for i in range(100):
            pyrpr.ContextRender(context)

        check_framebuffer_agains_baseline(frame_buffer, 'test_background_image_off')

    def test_emissive(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_emissive')
        with fixture:
            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)
            pyrpr.MaterialNodeSetInputF(shader, b'color', 0.5, 1.0, 0.25, 1.0)

            fixture.set_shader(shader)

    def test_ward(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_ward')
        with fixture:
            light = pyrpr.Light()
            pyrpr.ContextCreatePointLight(self.context, light)
            pyrpr.PointLightSetRadiantPower3f(light, 10, 2, 5)
            pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                                  0, 1, 0, 0,
                                                  0, 0, 1, 1,
                                                  0, 0, 0, 1])
            pyrpr.SceneAttachLight(fixture.scene, light)

            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_WARD, shader)
            pyrpr.MaterialNodeSetInputF(shader, b'color', 1.0, 1.0, 1.0, 1.0)
            pyrpr.MaterialNodeSetInputF(shader, b'normal', 0.0, 0.0, 1.0, 0.0)
            pyrpr.MaterialNodeSetInputF(shader, b'roughness_x', 0.5, 1.0, 1.0, 1.0)
            pyrpr.MaterialNodeSetInputF(shader, b'roughness_y', 0.25, 1.0, 1.0, 1.0)
            pyrpr.MaterialNodeSetInputF(shader, b'rotation', 3.1416 / 4, 1.0, 1.0, 1.0)

            fixture.set_shader(shader)

    def test_checker(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_checker')
        with fixture:
            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)

            testee = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_CHECKER_TEXTURE, testee)
            pyrpr.MaterialNodeSetInputN(shader, b'color', testee)

            lookup = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_INPUT_LOOKUP, lookup)
            pyrpr.MaterialNodeSetInputU(lookup, b'value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

            mapping_scale = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_ARITHMETIC, mapping_scale)
            pyrpr.MaterialNodeSetInputU(mapping_scale, b'op', pyrpr.MATERIAL_NODE_OP_MUL)
            pyrpr.MaterialNodeSetInputN(mapping_scale, b'color0', lookup)
            pyrpr.MaterialNodeSetInputF(mapping_scale, b'color1', 1, 1, 1, 1)

            uv = mapping_scale
            pyrpr.MaterialNodeSetInputN(testee, b'uv', uv)

            fixture.set_shader(shader)

    # @pytest.mark.skip(reason="need softer image comparison for this")
    def test_diffuse_refraction(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_diffuse_refraction')

        pyrpr.ContextSetScene(self.context, self.scene)

        mesh_to_refract = add_simple_quad(self.context, self.scene)
        self.mesh_to_refract = mesh_to_refract

        transform = np.array([
            [0.5, 0, 0, 0],
            [0, 0.5, 0, 0],
            [0, 0, 0.1, 0],
            [0, 0, -0.25, 1],
        ], dtype=np.float32)

        pyrpr.ShapeSetTransform(mesh_to_refract, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

        shader = pyrpr.MaterialNode()
        self.mesh_to_refract_shader = shader
        pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)
        pyrpr.MaterialNodeSetInputF(shader, b'color', 1.0, 1.0, 1.0, 1.0)
        pyrpr.ShapeSetMaterial(mesh_to_refract, shader)

        fixture.set_iter_count(1000)

        with fixture:
            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DIFFUSE_REFRACTION, shader)
            pyrpr.MaterialNodeSetInputF(shader, b'color', 1.0, 1.0, 1.0, 1.0)
            pyrpr.MaterialNodeSetInputF(shader, b'roughness', 0.01, 0.01, 0.01, 1.0)

            fixture.set_shader(shader)

    def test_emissive_visibility(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_emissive_visibility')

        pyrpr.ContextSetScene(self.context, self.scene)

        mesh_to_refract = add_simple_quad(self.context, self.scene)
        self.mesh_to_refract = mesh_to_refract

        transform = np.array([
            [0.1, 0, 0, 0],
            [0, 0.1, 0, 0],
            [0, 0, -1, 0],
            [0, 0, 4, 1],
        ], dtype=np.float32)

        pyrpr.ShapeSetTransform(mesh_to_refract, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

        shader = pyrpr.MaterialNode()
        self.mesh_to_refract_shader = shader
        pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)
        pyrpr.MaterialNodeSetInputF(shader, b'color', *(200.0,) * 4)
        pyrpr.ShapeSetMaterial(mesh_to_refract, shader)
        pyrpr.ShapeSetVisibility(mesh_to_refract, False)

        fixture.set_iter_count(100)

        with fixture:
            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)
            pyrpr.MaterialNodeSetInputF(shader, b'color', 0.5, 1.0, 0.75, 1.0)

            fixture.set_shader(shader)

    def test_gradient(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_gradient')
        with fixture:
            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)

            lookup = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_INPUT_LOOKUP, lookup)
            pyrpr.MaterialNodeSetInputU(lookup, b'value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

            mapping_scale = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_ARITHMETIC, mapping_scale)
            pyrpr.MaterialNodeSetInputU(mapping_scale, b'op', pyrpr.MATERIAL_NODE_OP_LENGTH3)
            pyrpr.MaterialNodeSetInputN(mapping_scale, b'color0', lookup)
            uv = mapping_scale

            testee = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_GRADIENT_TEXTURE, testee)
            pyrpr.MaterialNodeSetInputF(testee, b'color0', 1, 1, 0, 1)
            pyrpr.MaterialNodeSetInputF(testee, b'color1', 0, 0, 1, 1)
            pyrpr.MaterialNodeSetInputN(testee, b'uv', uv)

            pyrpr.MaterialNodeSetInputN(shader, b'color', testee)
            fixture.set_shader(shader)

    def test_noise2d(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_noise2d')
        with fixture:
            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)

            testee = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_NOISE2D_TEXTURE, testee)
            pyrpr.MaterialNodeSetInputN(shader, b'color', testee)

            lookup = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_INPUT_LOOKUP, lookup)
            pyrpr.MaterialNodeSetInputU(lookup, b'value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

            mapping_scale = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_ARITHMETIC, mapping_scale)
            pyrpr.MaterialNodeSetInputU(mapping_scale, b'op', pyrpr.MATERIAL_NODE_OP_MUL)
            pyrpr.MaterialNodeSetInputN(mapping_scale, b'color0', lookup)
            pyrpr.MaterialNodeSetInputF(mapping_scale, b'color1', 1, 1, 1, 1)

            uv = mapping_scale
            pyrpr.MaterialNodeSetInputN(testee, b'uv', uv)

            fixture.set_shader(shader)

    def test_dot(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_dot')
        with fixture:
            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)

            testee = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DOT_TEXTURE, testee)
            pyrpr.MaterialNodeSetInputN(shader, b'color', testee)

            lookup = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_INPUT_LOOKUP, lookup)
            pyrpr.MaterialNodeSetInputU(lookup, b'value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

            fixture.set_shader(shader)

    def test_op_dot4(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_op_dot4')
        with fixture:
            context = fixture.context

            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)

            image_shape = (32, 32)
            colors = np.full(image_shape + (4,), [0.0, 0.0, 0.0, 1.0], dtype=np.float32)
            colors[1 * image_shape[0] // 4:3 * image_shape[0] // 4, 1 * image_shape[1] // 4:3 * image_shape[1] // 4,
            ...] = 0.5
            img = create_image(colors, context, image_shape)

            image_texture = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, image_texture)
            pyrpr.MaterialNodeSetInputImageData(image_texture, b'data', img)

            dot4 = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_ARITHMETIC, dot4)
            pyrpr.MaterialNodeSetInputU(dot4, b'op', pyrpr.MATERIAL_NODE_OP_DOT4)
            pyrpr.MaterialNodeSetInputN(dot4, b'color0', image_texture)
            pyrpr.MaterialNodeSetInputF(dot4, b'color1', 0, 0, 0, 1)

            pyrpr.MaterialNodeSetInputN(shader, b'color', dot4)

            fixture.set_shader(shader)

    def test_noise2d_diffuse(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_noise2d_diffuse')
        with fixture:
            light = pyrpr.Light()
            pyrpr.ContextCreatePointLight(self.context, light)
            pyrpr.PointLightSetRadiantPower3f(light, 10, 10, 10)
            pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                                  0, 1, 0, 0,
                                                  0, 0, 1, 1,
                                                  0, 0, 0, 1])
            pyrpr.SceneAttachLight(fixture.scene, light)

            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)

            testee = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_NOISE2D_TEXTURE, testee)
            pyrpr.MaterialNodeSetInputN(shader, b'color', testee)

            lookup = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_INPUT_LOOKUP, lookup)
            pyrpr.MaterialNodeSetInputU(lookup, b'value', pyrpr.MATERIAL_NODE_LOOKUP_UV)

            mapping_scale = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_ARITHMETIC, mapping_scale)
            pyrpr.MaterialNodeSetInputU(mapping_scale, b'op', pyrpr.MATERIAL_NODE_OP_MUL)
            pyrpr.MaterialNodeSetInputN(mapping_scale, b'color0', lookup)
            pyrpr.MaterialNodeSetInputF(mapping_scale, b'color1', 1, 1, 1, 1)

            uv = mapping_scale
            pyrpr.MaterialNodeSetInputN(testee, b'uv', uv)

            fixture.set_shader(shader)

        # following was fixed in 1.252
        im = get_frame_buffer_image(fixture.frame_buffer, fixture.render_resolution)

        below_zero = np.amin(im, axis=2) < 0
        if np.any(below_zero):
            imageio.imwrite(fixture.name + '_BELOW_ZERO.png',
                            np.repeat(below_zero[:, :, np.newaxis], 3, axis=2) * [1, 0, 0])

        assert 0 <= np.min(im), np.min(im)

    def test_noise2d_bump(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_noise2d_bump')

        with fixture:
            light = pyrpr.Light()
            pyrpr.ContextCreatePointLight(self.context, light)
            pyrpr.PointLightSetRadiantPower3f(light, 10, 10, 10)
            pyrpr.LightSetTransform(light, False, [1, 0, 0, 0,
                                                   0, 1, 0, 0,
                                                   0, 0, 1, 0,
                                                   0, 0, 2, 1])
            pyrpr.SceneAttachLight(fixture.scene, light)

            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)

            noise = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_NOISE2D_TEXTURE, noise)

            bump = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_BUMP_MAP, bump)

            pyrpr.MaterialNodeSetInputN(bump, b'color', noise)
            pyrpr.MaterialNodeSetInputF(bump, b'bumpscale', *(20,) * 4)

            pyrpr.MaterialNodeSetInputF(shader, b'color', 1, 1, 1, 1)
            pyrpr.MaterialNodeSetInputN(shader, b'normal', bump)

            fixture.set_shader(shader)
        fixture.set_shader(None)
        fixture.mesh = None
        shader = None
        bump = None
        noise = None

    def test_bumpmap_image(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_bumpmap_image')
        with fixture:

            light = pyrpr.Light()
            pyrpr.ContextCreatePointLight(self.context, light)
            pyrpr.PointLightSetRadiantPower3f(light, 10, 10, 10)
            pyrpr.LightSetTransform(light, False, [1, 0, 0, 0,
                                                   0, 1, 0, 0,
                                                   0, 0, 1, 0,
                                                   0, 0, 2, 1])
            pyrpr.SceneAttachLight(fixture.scene, light)

            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)

            size = 256
            image_shape = (size, size)

            sphere_size = size / 8
            a = np.linspace(0, 1, sphere_size)
            x, y = np.meshgrid(a, a)
            sphere = np.sqrt(1.0 - np.clip((np.power(x * 2.0 - 1, 2.0) + np.power(y * 2 - 1, 2.0)), 0, 1))

            sphere = sphere[:, :, np.newaxis]
            sphere = np.repeat(sphere, 4, axis=2)
            sphere[:, :, 3] = 1.0

            def paste_image(dst, src, pos):
                dst[pos[1]:pos[1] + src.shape[1], pos[0]:pos[0] + src.shape[0]:, :] = src

            im = np.full(image_shape + (4,), 0, dtype=np.float32)

            paste_image(im, sphere, (im.shape[0] - sphere.shape[0], int((im.shape[1] - sphere.shape[1]) * 0.75)))

            for x in range(sphere.shape[1] * 2, im.shape[1], sphere.shape[1]):
                for y in range(sphere.shape[1], im.shape[0], sphere.shape[0]):
                    paste_image(im, sphere, (x, y))

            assert im.shape == (256, 256, 4)

            img = create_image(im.astype(np.float32), self.context, image_shape)

            texture = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, texture)
            pyrpr.MaterialNodeSetInputImageData(texture, b'data', img)

            bump = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_BUMP_MAP, bump)

            pyrpr.MaterialNodeSetInputN(bump, b'color', texture)
            pyrpr.MaterialNodeSetInputF(bump, b'bumpscale', *(2,) * 4)

            pyrpr.MaterialNodeSetInputF(shader, b'color', 1, 1, 1, 1)
            pyrpr.MaterialNodeSetInputN(shader, b'normal', bump)

            # color = pyrpr.MaterialNode()
            # pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, color)
            # pyrpr.MaterialNodeSetInputN(color, b'data', img)
            # pyrpr.MaterialNodeSetInputN(shader, b'color', color)

            fixture.set_shader(shader)

    @pytest.mark.skipif(pyrpr.API_VERSION == 0x010000260, reason="crashes in 1.260 ")
    def test_subdivision(self, simple_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_subdivision')
        context = fixture.context
        scene = fixture.scene
        vertices = [[-2.0, 2.0, 0.0],
                    [2.0, 2.0, 0.0],
                    [2.0, -2.0, 0.0],
                    [-2.0, -2.0, 0.0],
                    ]
        normals = [[0.0, 0.0, +1.0],
                   [0.0, 0.0, +1.0],
                   [0.0, 0.0, +1.0],
                   [0.0, 0.0, +1.0],
                   ]
        indices = [3, 2, 1, 1, 3, 0]

        mesh = create_mesh(context,
                           # np.array(vertices)[indices],
                           vertices,
                           np.array(normals)[indices],
                           # normals,
                           [(0, 0)],

                           # range(6),
                           indices,
                           range(6),
                           # indices,
                           [0] * 6, [3, 3])

        pyrpr.SceneAttachShape(scene, mesh)

        fixture.mesh = mesh
        fixture.set_iter_count(50)
        with fixture:
            scene = fixture.scene
            context = fixture.context

            light = pyrpr.Light()
            pyrpr.ContextCreatePointLight(self.context, light)
            pyrpr.PointLightSetRadiantPower3f(light, 10, 10, 10)
            pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                                  0, 1, 0, 0,
                                                  0, 0, 1, 1,
                                                  0, 0, 0, 1])
            pyrpr.SceneAttachLight(fixture.scene, light)

            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)

            fixture.set_shader(shader)

            shape = fixture.mesh
            pyrpr.ShapeSetSubdivisionFactor(shape, 4)
            # pyrpr.ShapeSetSubdivisionBoundaryInterop(shape, pyrpr.SUBDIV_BOUNDARY_INTERFOP_TYPE_EDGE_AND_CORNER)
            # pyrpr.ShapeSetSubdivisionCreaseWeight(shape, 0.1)

    @pytest.mark.skipif(pyrpr.API_VERSION == 0x010000260, reason="crashes in 1.260 ")
    def test_subdivision_stress(self, simple_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_subdivision_stress')
        context = fixture.context
        scene = fixture.scene

        width = 8
        height = 8

        x, y = np.meshgrid(np.linspace(-2, 2, width + 1),
                           np.linspace(-2, 2, height + 1))
        vertices_grid = np.empty((height + 1, width + 1, 3), dtype=np.float32)
        vertices_grid[..., 0] = x
        vertices_grid[..., 1] = y
        vertices_grid[..., 2] = 0

        xi, yi = np.meshgrid(np.arange(0, width), np.arange(0, height))

        quad = [(xi, yi), (xi, yi + 1),
                (xi + 1, yi + 1), (xi + 1, yi)]

        indices_grid = np.empty((height, width, 4), dtype=np.int32)

        for i, v in enumerate(quad):
            x, y = v
            index = x + y * (width + 1)
            indices_grid[:, :, i] = index

        indices = indices_grid.flatten()

        vertices = vertices_grid.reshape(-1, 3)

        mesh = create_mesh(context,
                           # np.array(vertices)[indices],
                           vertices,
                           [[0.0, 0.0, +1.0]],
                           [(0, 0)],

                           indices,
                           [0] * len(indices),

                           [0] * len(indices), [4] * width * height)

        pyrpr.SceneAttachShape(scene, mesh)

        fixture.mesh = mesh
        fixture.set_iter_count(50)

        scene = fixture.scene
        context = fixture.context

        light = pyrpr.Light()
        pyrpr.ContextCreatePointLight(self.context, light)
        pyrpr.PointLightSetRadiantPower3f(light, 10, 10, 10)
        pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                              0, 1, 0, 0,
                                              0, 0, 1, 1,
                                              0, 0, 0, 1])
        pyrpr.SceneAttachLight(fixture.scene, light)

        shader = pyrpr.MaterialNode()
        pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)

        fixture.set_shader(shader)

        shape = fixture.mesh

        with fixture:
            pyrpr.ShapeSetSubdivisionFactor(shape, 2)

        for i in range(10):
            print('test:', i)

            pyrpr.ShapeSetSubdivisionFactor(shape, 8)
            pyrpr.FrameBufferClear(fixture.frame_buffer)
            pyrpr.ContextRender(context)

            pyrpr.ShapeSetSubdivisionFactor(shape, 6)
            pyrpr.FrameBufferClear(fixture.frame_buffer)
            pyrpr.ContextRender(context)

    def test_point_light(self):

        light = pyrpr.Light()
        pyrpr.ContextCreatePointLight(self.context, light)
        pyrpr.PointLightSetRadiantPower3f(light, 10, 2, 5)
        pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                              0, 1, 0, 0,
                                              0, 0, 1, 1,
                                              0, 0, 0, 1])

        self.render_simple_light('test_point_light', light, 100)

    def test_spot_light(self):

        light = pyrpr.Light()
        pyrpr.ContextCreateSpotLight(self.context, light)
        pyrpr.SpotLightSetRadiantPower3f(light, 1, 3, 5)
        pyrpr.SpotLightSetConeShape(light, 0.5, 2)
        pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                              0, 1, 0, 0,
                                              0, 0, 1, 1,
                                              0, 0, 0, 1])

        self.render_simple_light('test_spot_light', light, 100)

    def test_direct_light(self):

        light = pyrpr.Light()
        pyrpr.ContextCreateDirectionalLight(self.context, light)
        pyrpr.DirectionalLightSetRadiantPower3f(light, 4, 6, 1)
        pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                              0, 1, 0, 0,
                                              0, 0, 1, 1,
                                              0, 0, 0, 1])

        self.render_simple_light('test_direct_light', light, 100)

    def test_sky_light(self):

        light = pyrpr.Light()
        pyrpr.ContextCreateSkyLight(self.context, light)
        pyrpr.SkyLightSetScale(light, 0.05)
        pyrpr.SkyLightSetAlbedo(light, 2)
        pyrpr.SkyLightSetTurbidity(light, 2)
        pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                              0, 1, 0, 0,
                                              0, 0, 1, 0,
                                              0, 0, 0, 1])

        self.render_simple_light('test_sky_light', light, 100)

    def render_simple_light(self, name, light, iter_count):
        context = self.context
        scene = self.scene
        pyrpr.ContextSetScene(context, scene)
        pyrpr.SceneAttachLight(scene, light)
        mesh = add_simple_quad(context, scene)
        matsys = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(context, 0, matsys)
        shader = pyrpr.MaterialNode()
        pyrpr.MaterialSystemCreateNode(matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)
        pyrpr.MaterialNodeSetInputF(shader, b'color', 1, 1.0, 1.0, 1.0)
        pyrpr.ShapeSetMaterial(mesh, shader)
        frame_buffer, camera = create_simple_render_setup(context, scene, resolution=(80, 60))
        pyrpr.ContextSetParameter1u(context, b'rendermode', pyrpr.RENDER_MODE_GLOBAL_ILLUMINATION)
        pyrpr.FrameBufferClear(frame_buffer)
        for i in range(iter_count):
            pyrpr.ContextRender(context)
        check_framebuffer_agains_baseline(frame_buffer, name)

    @pytest.mark.skip(reason="shadowcatcher was disabled since 1.257")
    @pytest.mark.parametrize('catcher_color', [['black', (0, 0, 0)], ['white', (1, 1, 1)]])
    def test_shadowcatcher(self, catcher_color, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_shadowcatcher_' + catcher_color[0])
        fixture.render_resolution = (160, 120)

        pyrpr.ShapeSetShadowCatcher(fixture.mesh, True)

        pyrpr.ContextSetScene(self.context, self.scene)

        light = pyrpr.Light()
        pyrpr.ContextCreatePointLight(self.context, light)
        pyrpr.PointLightSetRadiantPower3f(light, 5, 5, 5)
        pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                              0, 1, 0, 0,
                                              0, 0, 1, 1,
                                              0, 0, 0, 1])
        pyrpr.SceneAttachLight(self.scene, light)

        ibl_shape = (53, 26)

        desc = pyrpr.ffi.new("rpr_image_desc*")
        desc.image_width = ibl_shape[
            1];  # shape as in numpy has width in [1], good, not as used to have size=(width, heith) as in PIL
        desc.image_height = ibl_shape[0];
        desc.image_depth = 0
        desc.image_row_pitch = desc.image_width * pyrpr.ffi.sizeof('rpr_float') * 4
        desc.image_slice_pitch = 0

        img = pyrpr.Image()

        colors = np.full(ibl_shape + (4,), [1.0, 0.0, 0.0, 1.0], dtype=np.float32)
        pyrpr.ContextCreateImage(self.context, (4, pyrpr.COMPONENT_TYPE_FLOAT32), desc,
                                 pyrpr.ffi.cast("float *", colors.ctypes.data), img)

        ibl = pyrpr.Light()
        pyrpr.ContextCreateEnvironmentLight(self.context, ibl)

        pyrpr.EnvironmentLightSetIntensityScale(ibl, 1.0)

        pyrpr.EnvironmentLightSetImage(ibl, img)

        pyrpr.SceneAttachLight(self.scene, ibl)

        caster = add_simple_quad(self.context, self.scene)
        self.mesh_to_refract = caster

        transform = np.array([
            [0.25, 0, 0, 0],
            [0, 0.25, 0, 0],
            [0, 0, 1.0, 0],
            [0, 0, 0.5, 1],
        ], dtype=np.float32)

        pyrpr.ShapeSetTransform(caster, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

        shader = pyrpr.MaterialNode()
        self.caster_shader = shader
        pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)
        pyrpr.MaterialNodeSetInputF(shader, b'color', 1.0, 1.0, 1.0, 1.0)
        pyrpr.ShapeSetMaterial(caster, shader)

        fixture.set_iter_count(500)

        with fixture:
            shader = pyrpr.MaterialNode()
            self.catcher_shader = shader
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)
            pyrpr.MaterialNodeSetInputF(shader, b'color', *catcher_color[1], 1.0)

            fixture.set_shader(shader)

    @pytest.mark.skip(reason="shadowcatcher was disabled since 1.257")
    def test_shadowcatcher_with_background_override(self, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_shadowcatcher_with_background_override')
        fixture.render_resolution = (160, 120)

        pyrpr.ShapeSetShadowCatcher(fixture.mesh, True)

        pyrpr.ContextSetScene(self.context, self.scene)

        light = pyrpr.Light()
        pyrpr.ContextCreatePointLight(self.context, light)
        pyrpr.PointLightSetRadiantPower3f(light, 5, 5, 5)
        pyrpr.LightSetTransform(light, True, [1, 0, 0, 0,
                                              0, 1, 0, 0,
                                              0, 0, 1, 1,
                                              0, 0, 0, 1])
        pyrpr.SceneAttachLight(self.scene, light)

        ibl_shape = (1, 1)

        desc = pyrpr.ffi.new("rpr_image_desc*")
        desc.image_width = ibl_shape[
            1];  # shape as in numpy has width in [1], good, not as used to have size=(width, heith) as in PIL
        desc.image_height = ibl_shape[0];
        desc.image_depth = 0
        desc.image_row_pitch = desc.image_width * pyrpr.ffi.sizeof('rpr_float') * 4
        desc.image_slice_pitch = 0

        img = pyrpr.Image()

        colors = np.full(ibl_shape + (4,), [1.0, 0.0, 0.0, 1.0], dtype=np.float32)
        pyrpr.ContextCreateImage(self.context, (4, pyrpr.COMPONENT_TYPE_FLOAT32), desc,
                                 pyrpr.ffi.cast("float *", colors.ctypes.data), img)

        ibl = pyrpr.Light()
        pyrpr.ContextCreateEnvironmentLight(self.context, ibl)

        pyrpr.EnvironmentLightSetIntensityScale(ibl, 1.0)

        pyrpr.EnvironmentLightSetImage(ibl, img)

        pyrpr.SceneAttachLight(self.scene, ibl)

        ibl_shape = (1, 1)

        desc = pyrpr.ffi.new("rpr_image_desc*")
        desc.image_width = ibl_shape[
            1]  # shape as in numpy has width in [1], good, not as used to have size=(width, heith) as in PIL
        desc.image_height = ibl_shape[0]
        desc.image_depth = 0
        desc.image_row_pitch = desc.image_width * pyrpr.ffi.sizeof('rpr_float') * 4
        desc.image_slice_pitch = 0

        background_img = pyrpr.Image()

        colors = np.full(ibl_shape + (4,), [0.0, 1.0, 1.0, 1.0], dtype=np.float32)
        pyrpr.ContextCreateImage(self.context, (4, pyrpr.COMPONENT_TYPE_FLOAT32), desc,
                                 pyrpr.ffi.cast("float *", colors.ctypes.data), background_img)

        background = pyrpr.Light()
        pyrpr.ContextCreateEnvironmentLight(self.context, background)

        pyrpr.EnvironmentLightSetIntensityScale(background, 1.0)
        pyrpr.EnvironmentLightSetImage(background, background_img)

        pyrpr.SceneSetEnvironmentOverride(self.scene, pyrpr.SCENE_ENVIRONMENT_OVERRIDE_BACKGROUND, background)

        caster = add_simple_quad(self.context, self.scene)
        self.mesh_to_refract = caster

        transform = np.array([
            [0.25, 0, 0, 0],
            [0, 0.25, 0, 0],
            [0, 0, 1.0, 0],
            [0, 0, 0.5, 1],
        ], dtype=np.float32)

        pyrpr.ShapeSetTransform(caster, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

        shader = pyrpr.MaterialNode()
        self.caster_shader = shader
        pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)
        pyrpr.MaterialNodeSetInputF(shader, b'color', 1.0, 1.0, 1.0, 1.0)
        pyrpr.ShapeSetMaterial(caster, shader)

        fixture.set_iter_count(500)

        with fixture:
            shader = pyrpr.MaterialNode()
            self.catcher_shader = shader
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_DIFFUSE, shader)
            pyrpr.MaterialNodeSetInputF(shader, b'color', 0, 0, 0, 1.0)

            fixture.set_shader(shader)

    def test_image_from_memory(self, tmpdir_factory, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_image_from_file')

        fpath = str(tmpdir_factory.mktemp('data').join('image.png'))

        colors = np.array([
            [[1, 0, 0, 1], [0, 1, 0, 1]],
            [[0, 0, 1, 1], [1, 1, 1, 1]], ], dtype=np.float32)

        # upscale
        # colors = np.repeat(np.repeat(colors, 2, axis=0), 2, axis=1)
        colors = np.tile(colors, (2, 2, 1))

        imageio.imwrite(fpath, colors)

        with fixture:
            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)

            # image = pyrpr.Image()
            # pyrpr.ContextCreateImageFromFile(fixture.context, fpath.encode('latin1'), image)
            image = create_image(colors, self.context, colors.shape[:2])

            texture = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, texture)
            pyrpr.MaterialNodeSetInputImageData(texture, b'data', image)

            pyrpr.MaterialNodeSetInputN(shader, b'color', texture)

            fixture.set_shader(shader)

    def test_image_from_file(self, tmpdir_factory, simple_material_render_fixture):
        fixture = self.render_fixture
        fixture.set_name('test_image_from_file')

        fpath = str(tmpdir_factory.mktemp('data').join('image.png'))

        colors = np.array([
            [[1, 0, 0, 1], [0, 1, 0, 1]],
            [[0, 0, 1, 1], [1, 1, 1, 1]], ], dtype=np.float32)

        # upscale
        # colors = np.repeat(np.repeat(colors, 2, axis=0), 2, axis=1)
        colors = np.tile(colors, (2, 2, 1))

        imageio.imwrite(fpath, colors)

        with fixture:
            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)

            image = pyrpr.Image()
            pyrpr.ContextCreateImageFromFile(fixture.context, fpath.encode('latin1'), image)

            texture = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, texture)
            pyrpr.MaterialNodeSetInputImageData(texture, b'data', image)

            pyrpr.MaterialNodeSetInputN(shader, b'color', texture)

            fixture.set_shader(shader)

    @pytest.mark.skipif(pyrpr.API_VERSION <= 0x010027300, reason="issue found in this version, see AMDBLENDER-789")
    def test_image_from_file_memory(self, tmpdir_factory):

        fpath = str(tmpdir_factory.mktemp('data').join('image.png'))

        colors = np.array([
            [[1, 0, 0, 1], [0, 1, 0, 1]],
            [[0, 0, 1, 1], [1, 1, 1, 1]], ], dtype=np.float32)

        # upscale
        scale = 4096
        colors = np.repeat(np.repeat(colors, scale, axis=0), scale, axis=1)

        imageio.imwrite(fpath, colors)

        class Fixture:
            pass

        fixture = Fixture()
        fixture.name = 'test_image_from_file_memory'

        fixture.render_resolution = (320, 240)

        fixture.context = self.context

        for i in range(10):
            print('render:', i)

            image_fpath = str(tmpdir_factory.mktemp('textures').join('image_texture%d.png'%i))
            shutil.copy(fpath, image_fpath)

            image = pyrpr.Image()
            pyrpr.ContextCreateImageFromFile(fixture.context, image_fpath.encode('latin1'), image)
            del image
            continue

            fixture.matsys = pyrpr.MaterialSystem()
            pyrpr.ContextCreateMaterialSystem(fixture.context, 0, fixture.matsys)

            fixture.scene = pyrpr.Scene(fixture.context)
            pyrpr.ContextSetScene(fixture.context, fixture.scene)
            fixture.mesh = add_simple_quad(fixture.context, fixture.scene)
            fixture.frame_buffer = None

            fixture.frame_buffer, fixture.camera = create_simple_render_setup(
                fixture.context, fixture.scene, fixture.render_resolution)
            pyrpr.ContextSetParameter1u(fixture.context, b'rendermode', pyrpr.RENDER_MODE_GLOBAL_ILLUMINATION)

            shader = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_EMISSIVE, shader)

            texture = pyrpr.MaterialNode()
            pyrpr.MaterialSystemCreateNode(fixture.matsys, pyrpr.MATERIAL_NODE_IMAGE_TEXTURE, texture)
            pyrpr.MaterialNodeSetInputImageData(texture, b'data', image)

            pyrpr.MaterialNodeSetInputN(shader, b'color', texture)

            pyrpr.ShapeSetMaterial(fixture.mesh, shader)

            pyrpr.FrameBufferClear(fixture.frame_buffer)

            for j in range(1):
                pyrpr.ContextRender(self.context)

            check_framebuffer_agains_baseline(fixture.frame_buffer, fixture.name)

            pyrpr.ShapeSetMaterial(fixture.mesh, None)
            del shader
            del texture
            del image

            pyrpr.SceneDetachShape(fixture.scene, fixture.mesh)
            pyrpr.ContextSetScene(fixture.context, None)
            pyrpr.ContextSetAOV(fixture.context, pyrpr.AOV_COLOR, None)

            del fixture.mesh
            del fixture.frame_buffer
            del fixture.scene
            del fixture.camera
            del fixture.matsys

    def test_shape_set_transform_validity_check(self, simple_material_render_fixture):
        fixture = self.render_fixture

        mesh = add_simple_quad(self.context, self.scene)

        print('check nan raises error')
        transform = np.full((4, 4), float('nan'), dtype=np.float32)
        assert not pyrpr.is_transform_matrix_valid(transform)

        pytest.raises(pyrpr.CoreError,
                      pyrpr.ShapeSetTransform, mesh, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

        print('check degenerate raises error')
        transform = np.full((4, 4), 0, dtype=np.float32)
        assert pyrpr.is_transform_matrix_valid(transform)

        pytest.raises(pyrpr.CoreError,
                      pyrpr.ShapeSetTransform, mesh, False, pyrpr.ffi.cast('float*', transform.ctypes.data))

        print('check degenerate raises error, so shouldnt we?')
        transform = np.eye(4, dtype=np.float32)
        transform[3, 3] = float('nan')
        assert not pyrpr.is_transform_matrix_valid(transform)

        pytest.raises(pyrpr.CoreError,
                       pyrpr.ShapeSetTransform, mesh, False, pyrpr.ffi.cast('float*', transform.ctypes.data))



def assert_images_similar(a, b, max_average_deviation=0.005, max_std_dev=0.02):
    deviations_flat = (a - b).ravel()
    variance = np.dot(deviations_flat, deviations_flat) / len(deviations_flat)
    std_dev = np.sqrt(variance)
    avg_dev = sum(np.abs(deviations_flat)) / len(deviations_flat)
    print("avg_dev: {avg_dev}, std_dev: {std_dev}".format(**locals()))
    assert avg_dev <= max_average_deviation, (avg_dev, max_average_deviation)
    assert std_dev <= max_std_dev, (std_dev, max_std_dev)


def check_framebuffer_agains_baseline(frame_buffer, name, max_average_deviation=0.005, max_std_dev=0.02, scale=1.0):
    fname = name + ".png"
    pyrpr.FrameBufferSaveToFile(frame_buffer, fname.encode('latin1'))

    if not os.path.isdir('baseline'):
        os.mkdir('baseline')

    expected_path = os.path.join('baseline', fname)
    actual_path = fname

    if not os.path.isfile(expected_path):
        shutil.copy(actual_path, expected_path)

    actual = imageio.imread(actual_path)[..., 0:3].astype(np.float32) * (1 / 255) * scale

    expected = imageio.imread(expected_path)[..., 0:3].astype(np.float32) * (1 / 255)

    diff = expected - actual
    # sum differences from all channels
    diff_channels = np.abs(diff[..., 0]), np.abs(diff[..., 1]), np.abs(diff[..., 2])
    # make red dots where there's any difference
    diff_max = np.concatenate([a[..., np.newaxis] for a in diff_channels], axis=2).max(axis=2)

    diff_display = (diff_max != 0)[:, :, np.newaxis] * [1, 0, 0]

    try:
        assert_images_similar(expected, actual, max_average_deviation=max_average_deviation, max_std_dev=max_std_dev)
    except AssertionError:
        imageio.imwrite(name + '_baseline.png', expected)
        imageio.imwrite(name + '_diff.png', diff_display)
        imageio.imwrite(name + '_diff_module.png', diff_max)
        raise
    else:
        os.remove(actual_path)


def check_image_agains_baseline2(im, name):

    assert 0 <= np.min(im) and np.max(im) <= 1

    fname = name + ".png"

    if not os.path.isdir('baseline'):
        os.mkdir('baseline')

    expected_path = os.path.join('baseline', fname)
    actual_path = fname

    imageio.imwrite(actual_path, im)

    if not os.path.isfile(expected_path):
        shutil.copy(actual_path, expected_path)

    actual = imageio.imread(actual_path)[..., 0:3].astype(np.float32) * (1 / 255)

    expected = imageio.imread(expected_path)[..., 0:3].astype(np.float32) * (1 / 255)

    diff = expected - actual
    # sum differences from all channels
    diff_channels = np.abs(diff[..., 0]), np.abs(diff[..., 1]), np.abs(diff[..., 2])
    # make red dots where there's any difference
    diff_max = np.concatenate([a[..., np.newaxis] for a in diff_channels], axis=2).max(axis=2)

    diff_display = (diff_max != 0)[:, :, np.newaxis] * [1, 0, 0]

    try:
        assert_images_similar(expected, actual)
    except AssertionError:
        imageio.imwrite(name + '_baseline.png', expected)
        imageio.imwrite(name + '_diff.png', diff_display)
        imageio.imwrite(name + '_diff_module.png', diff_max)
        raise
    else:
        os.remove(actual_path)

def check_image_agains_baseline(im, name):
    fname = name + ".png"

    if not os.path.isdir('baseline'):
        os.mkdir('baseline')

    expected_path = os.path.join('baseline', fname)
    actual_path = fname

    imageio.imwrite(actual_path, im)

    if not os.path.isfile(expected_path):
        shutil.copy(actual_path, expected_path)

    actual = imageio.imread(actual_path)[..., 0:3].astype(np.float32) * (1 / 255)

    expected = imageio.imread(expected_path)[..., 0:3].astype(np.float32) * (1 / 255)

    diff = expected - actual
    # sum differences from all channels
    diff_channels = np.abs(diff[..., 0]), np.abs(diff[..., 1]), np.abs(diff[..., 2])
    # make red dots where there's any difference
    diff_max = np.concatenate([a[..., np.newaxis] for a in diff_channels], axis=2).max(axis=2)

    diff_display = (diff_max != 0)[:, :, np.newaxis] * [1, 0, 0]

    try:
        assert_images_similar(expected, actual)
    except AssertionError:
        imageio.imwrite(name + '_baseline.png', expected)
        imageio.imwrite(name + '_diff.png', diff_display)
        imageio.imwrite(name + '_diff_module.png', diff_max)
        raise
    else:
        os.remove(actual_path)


class TestRprx(unittest.TestCase):
    
    def test_simple(self):
        tahoe_plugin_id = pyrpr.RegisterPlugin(str(tahoe_path).encode('ascii'))
    
        assert -1 != tahoe_plugin_id, tahoe_path
    
        plugins = [tahoe_plugin_id]
    
        self.context = pyrpr.Context(plugins, get_gpu_creation_flags(), cache_path=ensure_core_cache_folder())
        assert pyrpr.SUCCESS == self.context.create_result

        self.matsys = pyrpr.MaterialSystem()
        pyrpr.ContextCreateMaterialSystem(self.context, 0, self.matsys)

        uber_context = pyrprx.Object('rprx_context')
        pyrprx.CreateContext(self.matsys, 0, uber_context)

        uber_material = pyrprx.Object('rprx_material')
        pyrprx.CreateMaterial(uber_context, pyrprx.MATERIAL_UBER, uber_material)

        pytest.raises(pyrpr.CoreError,
            pyrprx.MaterialSetParameterF, uber_context, uber_material,
                                           pyrprx.UBER_MATERIAL_REFLECTION_MODE, 1, 1, 1, 1)

        pyrprx.MaterialSetParameterF(uber_context, uber_material,
                                           pyrprx.UBER_MATERIAL_DIFFUSE_COLOR, 1, 1, 1, 1)

        pyrprx.MaterialCommit(uber_context, uber_material)


        pyrprx.MaterialDelete(uber_context, uber_material)

        pyrprx.DeleteContext(uber_context)



def init_modules():
    pyrpr.init(print, rprsdk_bin_path=rprsdk_path / bin_folder)
    pyrpr_load_store.init(rprsdk_path / bin_folder)
    pyrprx.init(print, rprsdk_bin_path=rprsdk_path / bin_folder)

if __name__ == '__main__':
    pyrpr_log_flag = '--pyrpr-log'
    if pyrpr_log_flag in sys.argv:
        pyrpr.lib_wrapped_log_calls = True
        sys.argv.remove(pyrpr_log_flag)

    init_modules()

    pytest.main([__file__, '-s'])
else:
    # pyrpr.lib_wrapped_log_calls = True
    if pytest.config.option.pyrpr_log:
        pyrpr.lib_wrapped_log_calls = True

    init_modules()

