import ast
import itertools
import os
import shutil
import sys
import tempfile
import time
import traceback
import typing
import math
import contextlib
from pathlib import Path
from typing import List

import bpy
import bpy_extras.image_utils
import material_import
import numpy as np
import pyrpr
import pytest
import rprtesting

import rprblender.core.nodes
import rprblender.logging
import rprblender.render
import rprblender.render.viewport
import rprblender.render.render_layers
import rprblender.sync
import rprblender.testing
import rprblender.ui
import rprblender.images
import rprblender.core.image
from rprblender import config, versions
from rprblender import helpers
from rprblender import material_editor
from rprblender import node_editor
from rprblender.material_editor import OutputNode, MaterialEditor
from rprblender.timing import TimedContext
from rprblender.versions import get_render_passes_aov, is_blender_support_new_image_node


print = rprblender.logging.warn


def log(*args):
    rprblender.logging.info(' '.join(str(arg) for arg in args), tag='testing.render')


np.seterr(divide='raise', under='warn', over='raise', invalid='raise')

tracing_folder = b'.rprtrace_render_test'
if not os.path.isdir(tracing_folder):
    os.mkdir(tracing_folder)

enable_trace = pytest.config.getoption("--enable-trace")
enable_cpu = pytest.config.getoption("--enable-cpu")

notquick = pytest.mark.skipif(pytest.config.option.render_quickest, reason="slow")

class TestSimple:
    def test_simple(self): pass


class ViewportFixture:
    viewport_renderer = None  # type: import rprblender.renderviewport.ViewportRenderer

    render_resolution = (320, 240)
    render_region = None

    def __del__(self):
        pass

    def destroy(self):
        if self.viewport_renderer:  # if render even started
            self.viewport_renderer.scene_synced.destroy()
            self.stop()
            self.viewport_renderer = None

    def start(self):
        self.viewport_renderer = rprblender.render.viewport.ViewportRenderer()
        self.set_render_camera_and_resolution_and_xxx(update=False)
        self.viewport_renderer.start(bpy.context.scene, is_production=True)
        self.viewport_renderer.scene_renderer.production_render = True
        self.viewport_renderer.scene_renderer_threaded.sleep_delay = 0.0

    def reset(self, scene):
        self.set_render_camera_and_resolution_and_xxx(update=True)
        self.viewport_renderer.scene_reset(scene)

    def set_render_camera_and_resolution_and_xxx(self, update):
        render_camera = rprblender.sync.RenderCamera()

        scene = bpy.context.scene

        border = rprblender.sync.extract_render_border_from_scene(scene)
        render_border_resolution = rprblender.sync.get_render_resolution_for_border(border, self.render_resolution)

        rprblender.sync.extract_render_camera_from_blender_camera(
            bpy.context.scene.camera, render_camera,
            self.render_resolution, 1, bpy.context.scene.rpr.render,
            scene, border=border)

        if not update:
            self.viewport_renderer.set_render_camera(render_camera)
            self.viewport_renderer.set_render_aov(get_render_passes_aov(bpy.context))
            self.viewport_renderer.set_render_resolution(render_border_resolution)
            self.viewport_renderer.set_render_region(self.render_region)
        else:
            self.viewport_renderer.update_render_camera(render_camera)
            self.viewport_renderer.update_render_aov(get_render_passes_aov(bpy.context))
            self.viewport_renderer.update_render_resolution(render_border_resolution)
            self.viewport_renderer.update_render_region(self.render_region)

    def stop(self):
        self.viewport_renderer.stop()

    def update(self):
        list(self.viewport_renderer.update_iter(bpy.context.scene))

    def wait_for_render_complete(self, shortest_expected_render_time_seconds=0.001, timeout_seconds=100):
        print('wait_for_render_complete:')
        completed_successfully = False
        for i in range(int(timeout_seconds / shortest_expected_render_time_seconds)):
            if self.viewport_renderer.scene_renderer_threaded.render_completed_event.wait(
                timeout=shortest_expected_render_time_seconds):
                completed_successfully = True
                break
            # check if thread is crashed
            assert (not self.viewport_renderer.scene_renderer_threaded.is_render_completed()
                    or self.viewport_renderer.scene_renderer_threaded.render_completed_event.is_set())
        assert completed_successfully
        print('render compeleted')

    def __enter__(self):
        try:
            self.start()
        except:
            self.stop()
            raise

    def __exit__(self, *args):
        self.stop()


class FailureReport:
    actual = None  # type: np.ndarray
    expected = None  # type: np.ndarray


class ExpectedImage:
    data = None

    def get_actual_for_comparison(self, rgb):
        return rgb

    def get_expected_hdr(self, value):
        return value


class ExpectedImageNormalizedOnDisk(ExpectedImage):
    def __init__(self, path):
        self.path = path

    @property
    def data(self):
        if not os.path.isfile(self.path + '.png'):
            return None
        image = bpy.data.images.load(self.path + '.png')
        return np.flipud(np.array(image.pixels).reshape(image.size[1], image.size[0], 4))

    def __str__(self):
        return "<%s: '%s'>" % (self.__class__, self.path)

    def create(self, rgb):
        assert self.path, "in order to save actual image when expected is missing - path must be provided in set_expected"
        import imageio
        Path(self.path + '.png').parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(self.path + '.png', rgb)  # without alpha channel, save as in offline convert

        l, u = np.min(rgb), np.max(rgb)

        # use transform only if needed(pixel values outside of 0..1)
        transform_path = Path(self.path + '.transform')
        if l < 0 or u > 1:
            scale = 1 / (u - l)
            offset = -l * scale

            transform_path.open('w').write(repr((scale, offset)))
        else:
            if transform_path.is_file():
                os.remove(str(transform_path))

        # with open(str(Path(self.expected_fpath).with_suffix('.list')), 'w') as f:
        #     f.write(repr(rgb.tolist()))

        print("Expected image {} not found, actual render saved in its place".format(self.path))

    def get_actual_for_comparison(self, rgb):
        if Path(self.path + '.transform').is_file():
            scale, offset = eval(open(self.path + '.transform').read())
            return rgb * scale + offset
        else:
            return rgb

    def get_expected_hdr(self, expected_hdr):
        if Path(self.path + '.transform').is_file():
            scale, offset = eval(open(self.path + '.transform').read())
            return (expected_hdr - offset) / scale
        else:
            return expected_hdr


class ExpectedImageOnDisk(ExpectedImage):
    def __init__(self, path, scale, offset):
        self.path = path
        self.scale = scale if scale is not None else 1.0
        self.offset = offset if offset is not None else 0.0

    @property
    def data(self):
        if not os.path.isfile(self.path):
            return None
        image = bpy.data.images.load(self.path)
        return np.flipud(np.array(image.pixels).reshape(image.size[1], image.size[0], 4))

    def __str__(self):
        return "<%s: '%s'>" % (self.__class__, self.path)

    def create(self, rgb):
        assert self.path, "in order to save actual image when expected is missing - path must be provided in set_expected"
        import imageio
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(self.path, rgb)  # without alpha channel, save as in offline convert

        print("Expected image {} not found, actual render saved in its place".format(self.path))

    def get_actual_for_comparison(self, rgb):
        # rgb = self.downsample_image(rgb)
        return rgb * self.scale + self.offset

    def get_expected_hdr(self, expected_hdr):
        return (expected_hdr - self.offset) / self.scale


class ExpectedImageData(ExpectedImage):
    def __init__(self, data):
        self.data = data


class RenderImageCheck:
    expected = None  # type:np.ndarray
    expected_fpath = None

    def __init__(self, expected, scale=1.0, offset=0.0, max_avg_dev=None, max_std_dev=None):
        self.set_expected(expected, scale=scale, offset=offset, max_avg_dev=max_avg_dev, max_std_dev=max_std_dev)
        self.started = False
        basic_render_settings()

        self.viewport_fixture = None  # type: ViewportFixture

        self.failures = None  # type: List[FailureReport]

        # used to softly skip tests in case they render something wrong like when we have a new Core with issues
        # but to keep code executing anyway
        self.skip_image_comparison = False

        self.failure_encountered = False

    def set_expected(self, expected, scale=None, offset=None, gamma=None, clamp=None, max_avg_dev=None,
                     max_std_dev=None, aov='default', use_alpha=False):
        """ Context that checks image on exit by performing full re-export and render of the current scene

        :param gamma: displaygamma(rendered pixels a taken to power of 1/gamma)
        :param expected: expected image(string for image file path or just numpy array)
        :param scale: apply `scale` and `offset` to rendered image before comparison(allowing use of PNG as an expected image for HRD render)
        :param offset: see `scale`
        :param max_std_dev: `max standard deviation` from expected image allowed for similarity check to pass
        :param max_avg_dev: `max average deviation` from expected image allowed for similarity check to pass
        """
        if expected is None:
            self.expected = None
            return self

        self.use_alpha = use_alpha

        self.gamma = gamma
        self.clamp = clamp
        self.aov = aov
        self.max_avg_dev = 0.005 if max_avg_dev is None else max_avg_dev
        self.max_std_dev = 0.01 if max_std_dev is None else max_std_dev
        if isinstance(expected, str) or isinstance(expected, Path):

            image_path = testdata.get_path(expected)
            if Path(image_path).suffix in ['.png', '.bmp']:
                self.expected = ExpectedImageOnDisk(image_path, scale, offset)
            else:
                assert scale is None and offset is None
                self.expected = ExpectedImageNormalizedOnDisk(image_path)
        else:
            assert scale is None and offset is None
            self.expected = ExpectedImageData(expected)
        return self

    @contextlib.contextmanager
    def set_expected_synced(self, expected, scale=None, offset=None, max_avg_dev=None, max_std_dev=None, aov='default'):
        ''' Context that checks image on exit by performing 'sync'(i.e. updating, not re-exporting) and render of the current scene

        :param expected:
        param sync_fixture:
        :param scale:
        :param offset:
        :param max_avg_dev:
        :param max_std_dev:
        :return:
        '''
        self.set_expected(expected, scale=scale, offset=offset, max_avg_dev=max_avg_dev, max_std_dev=max_std_dev,
                          aov=aov)
        self.sync_fixture.set_sync(self.viewport_fixture.update)

        with self.sync_fixture:
            yield
            if self.quick:
                rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
                rpr_settings.rendering_limits.enable = True
                rpr_settings.rendering_limits.type = 'ITER'
                rpr_settings.rendering_limits.iterations = 1
            bpy.context.scene.update()
            self.viewport_fixture.set_render_camera_and_resolution_and_xxx(update=True)
        self.check()

    def __enter__(self):
        pass

    quick = pytest.config.option.render_quickest

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            return
        bpy.context.scene.update()

        if self.quick:
            rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
            rpr_settings.rendering_limits.enable = True
            rpr_settings.rendering_limits.type = 'ITER'
            rpr_settings.rendering_limits.iterations = 1

        if not self.started:
            self.started = True
            self.viewport_fixture.start()
        else:
            # self.viewport_fixture.stop()
            # self.viewport_fixture.start()

            self.viewport_fixture.reset(bpy.context.scene)

        self.check()

    def check(self):
        self.viewport_fixture.wait_for_render_complete()

        if self.quick:
            return

        # just rendering, without checking
        if self.expected is None:
            return
        print('checking:', self.expected)

        render_image = self.viewport_fixture.viewport_renderer.get_image(self.aov)
        assert render_image is not None

        im = np.flipud(render_image)  # type: np.ndarray
        assert im is not None

        try:

            # donwsample image to emulate AA for better error tolerance
            im_dowsampled = self.downsample_image(im[..., :4 if self.use_alpha else 3])
            actual_for_comparison = self.expected.get_actual_for_comparison(im_dowsampled)
            if self.clamp:
                actual_for_comparison = np.clip(actual_for_comparison, a_min=self.clamp[0], a_max=self.clamp[1])
            if self.gamma:
                actual_for_comparison = np.power(actual_for_comparison, 1 / self.gamma)

            if self.expected.data is not None and not pytest.config.option.render_check_regenerate_expected_image:
                # actual_for_comparison = self.downsample_image(actual_for_comparison)

                if not self.skip_image_comparison:
                    rprtesting.assert_images_similar(self.expected.data[..., :4 if self.use_alpha else 3],
                                                     actual_for_comparison, max_average_deviation=self.max_avg_dev,
                                                     max_std_dev=self.max_std_dev)
            else:
                if (pytest.config.option.render_check_generate_missing_expected_image
                    or pytest.config.option.render_check_regenerate_expected_image):
                    self.expected.create(actual_for_comparison)
                else:
                    assert False, 'Expected image {} not found'.format(self.expected)
        except:
            failure_report = FailureReport()
            if self.expected is not None:
                failure_report.expected = self.expected.data.copy()
                expected_hdr = failure_report.expected
                if self.gamma:
                    expected_hdr = np.power(expected_hdr, self.gamma)

                failure_report.expected_hdr = self.expected.get_expected_hdr(expected_hdr)

            failure_report.actual = actual_for_comparison.copy()
            failure_report.actual_hdr = im.copy()
            failure_report.exception = traceback.format_exc(chain=True)
            failure_report.stack = traceback.format_stack()

            self.failures.append(failure_report)

            # stop test only when something bad happened, let assertions pass
            if AssertionError == sys.exc_info()[0]:
                self.failure_encountered = True
            else:
                raise

    def downsample_image(self, rgb):
        # wrap around
        _rgb = np.column_stack((rgb, rgb[:, 0:1, :]))
        _rgb = np.row_stack((_rgb, _rgb[0:1, :, :]))

        a = _rgb
        rgb = (a[1:rgb.shape[0]:2, :rgb.shape[1]:2]
               + a[:rgb.shape[0]:2, 1:rgb.shape[1]:2]
               + a[1::2, 1::2]
               + a[:rgb.shape[0]:2, :rgb.shape[1]:2]
               # +a[2::2, 1::2]+a[1::2, 2::2]
               ) / 4.0
        return rgb


def set_light_intensity(lamp_object, intensity):
    lamp_object.data.rpr_lamp.intensity = intensity


def basic_render_settings():
    """
    just some simple render settings for tests
    """
    # set renderer settings
    rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
    rpr_settings.tone_mapping.enable = False
    rpr_settings.aa.filter = 'BOX'
    rpr_settings.aa.radius = 0.0
    rpr_settings.global_illumination.max_ray_depth = 10

    rpr_settings.rendering_limits.enable = True
    rpr_settings.rendering_limits.type = 'ITER'
    rpr_settings.rendering_limits.iterations = 50

    bpy.context.scene.world.rpr_data.environment.ibl.color = (0, 0, 0)

    # setup camera
    bpy.context.scene.camera.location = (0, 0, 4)
    bpy.context.scene.camera.rotation_euler.zero()

    bpy.context.scene.objects.active.location = (0, 0, 0)
    bpy.context.scene.objects.active.scale = (1, 1, 1)
    bpy.context.scene.objects.active.rotation_euler.zero()

    lamp_object = bpy.context.scene.objects['Lamp']
    lamp_object.location = (6, 2, 4)
    set_light_intensity(lamp_object, 100 * 4 * math.pi)
    lamp_object.rotation_euler.zero()

    if enable_trace:
        bpy.context.scene.rpr.dev.trace_dump = True
        bpy.context.scene.rpr.dev.trace_dump_folder = tracing_folder

    if enable_cpu:
        helpers.get_device_settings().use_cpu = True
        helpers.get_device_settings().use_gpu = False
    else:
        helpers.get_device_settings().use_gpu = True
        helpers.get_device_settings().use_cpu = False
    helpers.get_device_settings().samples = 1


@pytest.fixture(scope='function', autouse=True)
def reset_blender():
    print("fixture: reset_blender")
    bpy.context.scene.render.engine = 'RPR'
    yield
    if not pytest.config.option.keep_blender_running:
        bpy.ops.wm.read_factory_settings()


@pytest.fixture
def sync_fixture(reset_blender):
    print("fixture: sync_fixture")
    fixture = rprblender.testing.SyncFixture()
    return fixture


@pytest.fixture(scope='function')
def viewport_fixture(reset_blender):
    print("fixture: viewport_fixture")
    fixture = ViewportFixture()
    yield fixture
    fixture.destroy()
    print('viewport_fixture done!')


@pytest.fixture(scope='session')
def render_image_check_failure_collect_fixture():
    failures_dir_root = Path() / 'failures'

    if failures_dir_root.is_dir():
        dirs = [p for p in failures_dir_root.iterdir() if p.is_dir()]

        def get_dir_values():
            for d in dirs:
                try:
                    yield int(ast.literal_eval('0x' + d.name))
                except Exception:
                    pass

        n = 1 + max(get_dir_values(), default=0)
    else:
        n = 0

    failures_dir = failures_dir_root / ('%08x' % n)

    failures = {}  # type: Dict[List[FailureReport]]
    yield failures
    if not failures: return

    failures_dir.mkdir(parents=True)
    import imageio
    for name in failures:
        print('failure name:', name)
        for i, failure in enumerate(failures[name]):
            d = failures_dir / name / str(i)
            d.mkdir(parents=True)
            if failure.expected is not None:
                imageio.imsave(str(d / 'expected.png'), failure.expected)
                with open(str(d / 'expected.list'), 'w') as f:
                    f.write(str(failure.expected_hdr.tolist()))

            if failure.actual is not None:
                imageio.imsave(str(d / 'actual.png'), failure.actual)

                with open(str(d / 'actual.list'), 'w') as f:
                    f.write(str(failure.actual_hdr.tolist()))

            with open(str(d / 'exception.txt'), 'w') as f:
                f.write(str(failure.exception))
                # f.write('\n'.join(failure.stack))
                for line in failure.stack:
                    f.write(line)

    failures_last_dir = Path() / 'failures_last'

    if failures_last_dir.is_dir():
        log(failures_last_dir, 'is a directory, trying to remove')

        try:
            shutil.rmtree(str(failures_last_dir))
            log('removed:', repr(failures_last_dir))
            cant_remove = not failures_last_dir.is_dir()
            if cant_remove:
                log("Can't remove - still a dir after rmtree.")
        except OSError:
            cant_remove = True
            log("Can't remove dues to OSError.")

        if cant_remove:
            for i in itertools.count():
                d = failures_last_dir.with_suffix('.' + str(i))
                log('try:', d)
                if not d.exists():
                    failures_last_dir = d
                    break

    log(repr(failures_dir), repr(failures_last_dir))
    shutil.copytree(str(failures_dir), str(failures_last_dir))


@pytest.fixture()
def render_image_check_fixture(request, render_image_check_failure_collect_fixture, viewport_fixture, sync_fixture,
                               reset_blender):
    test_name = request.node.name
    print("fixture: render_image_check_fixture")
    result = RenderImageCheck(None)
    result.failures = []
    result.viewport_fixture = viewport_fixture
    result.sync_fixture = sync_fixture
    yield result

    if result.failures:
        render_image_check_failure_collect_fixture[test_name] = result.failures
    assert not result.failure_encountered


def test_render_simple(tmpdir_factory):
    bpy.context.scene.objects.active = bpy.context.object

    fpath = Path(str(tmpdir_factory.mktemp('data').join('image.png')))
    try:
        bpy.context.scene.render.filepath = str(fpath)
        bpy.ops.render.render(write_still=True)
        assert fpath.is_file(), tempfile
        # TODO:check resulting image here
    finally:
        fpath.unlink()


def test_render_uv(tmpdir_factory):
    bpy.context.scene.objects.active = bpy.context.object

    # for uv
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.unwrap()
    bpy.ops.object.mode_set(mode='OBJECT')

    fpath = Path(str(tmpdir_factory.mktemp('data').join('image.png')))
    try:
        bpy.context.scene.render.engine = 'RPR'
        bpy.context.scene.render.filepath = str(fpath)
        bpy.ops.render.render(write_still=True)
        assert fpath.is_file(), tempfile
        # TODO:check resulting image here
    finally:
        pass


def test_viewport_simple(viewport_fixture):
    with viewport_fixture:
        viewport_fixture.update()

        viewport_fixture.wait_for_render_complete()

        im = viewport_fixture.viewport_renderer.get_image()
        assert im is not None
        assert im.shape == tuple(reversed(viewport_fixture.render_resolution)) + (4,)


@pytest.mark.skip(reason="don't know how to inject a crash yet")
def test_viewport_simple_crash(viewport_fixture):
    with viewport_fixture:
        viewport_renderer = viewport_fixture.viewport_renderer
        list(viewport_renderer.update_iter(bpy.context.scene))

        viewport_fixture.wait_for_render_complete()

        assert not viewport_renderer.scene_renderer_threaded.render_completed_event.wait(
            timeout=0.1)
        assert (viewport_renderer.scene_renderer_threaded.is_render_completed()
                and not viewport_renderer.scene_renderer_threaded.render_completed_event.is_set())


def test_viewport_sync(viewport_fixture, sync_fixture):
    with viewport_fixture:
        sync_fixture.set_sync(viewport_fixture.update)

        with sync_fixture:
            bpy.context.object.location = (0, 1, 0)

            bpy.ops.group.create()
            bpy.ops.object.group_instance_add(
                group='Group',
                location=(2, 0, 0))
            bpy.context.object.name = 'B'

            bpy.context.scene.update()

            viewport_fixture.wait_for_render_complete()

        im = viewport_fixture.viewport_renderer.get_image()
        assert im is not None
        tuple(reversed(viewport_fixture.render_resolution)) + (4,)


def test_viewport_sync_resolution_change(viewport_fixture, sync_fixture):
    with viewport_fixture:
        viewport_fixture.wait_for_render_complete()

        im = viewport_fixture.viewport_renderer.get_image()
        assert im is not None
        assert im.shape == tuple(reversed(viewport_fixture.render_resolution)) + (4,)

        viewport_fixture.viewport_renderer.update_render_resolution((240, 320))
        time.sleep(0.1)
        viewport_fixture.wait_for_render_complete()

        print('getting image:')
        im = viewport_fixture.viewport_renderer.get_image()
        assert im is not None
        assert im.shape == (320, 240, 4)


@pytest.mark.skipif(condition=not pytest.config.option.perf, reason="perf")
def test_viewport_image_perf(viewport_fixture, sync_fixture):
    bpy.context.scene.rpr.render.rendering_limits.iterations = 1
    viewport_fixture.render_resolution = (2048, 2048)
    passes_aov = get_render_passes_aov(bpy.context)
    passes_aov.enable = True
    for i in range(len(passes_aov.passesStates)):
        passes_aov.passesStates[i] = True

    passes_aov.transparent = True

    def get_images(passes_aov, scene_renderer):
        images = scene_renderer.get_images()
        # get every aov image
        for item in passes_aov.render_passes_items:
            aov_name = item[0]

            im = images.get_image(aov_name)
            assert im is not None, aov_name

    with viewport_fixture:
        viewport_fixture.wait_for_render_complete()

        get_images(passes_aov, viewport_fixture.viewport_renderer.scene_renderer)



@notquick
def test_viewport_sync_resolution_change_stress(viewport_fixture, sync_fixture):
    with viewport_fixture:

        viewport_fixture.wait_for_render_complete()

        im = viewport_fixture.viewport_renderer.get_image()
        assert im is not None
        assert im.shape == tuple(reversed(viewport_fixture.render_resolution)) + (4,)

        viewport_renderer = viewport_fixture.viewport_renderer

        render_resolution = (320, 240)
        for x in range(100):
            for y in range(100):
                r = (render_resolution[0] - x, render_resolution[1] - y)
                print('change resolution:', r)
                viewport_renderer.update_render_aov(get_render_passes_aov(bpy.context))
                viewport_renderer.update_render_resolution(r)

                render_camera = rprblender.sync.RenderCamera()
                rprblender.sync.extract_render_camera_from_blender_camera(
                    bpy.context.scene.camera, render_camera,
                    r, 1, bpy.context.scene.rpr.render,
                    bpy.context.scene, border=None)
                viewport_renderer.update_render_camera(render_camera)
                time.sleep(0.001)

        viewport_fixture.wait_for_render_complete()

        print('getting image:')
        im = viewport_fixture.viewport_renderer.get_image()
        assert im is not None
        assert im.shape == (141, 221, 4)


class TestData:
    def get_path(self, name):
        return str(Path(__file__).resolve().parent / 'testdata/render' / name)


testdata = TestData()

import pytest


class MaterialSetupFixture:
    def create_default_node_tree(self, material=None):
        if not material:
            material = self.get_active_material()
        self.material = material

        # create material nodetree and retrieve it
        override = bpy.context.copy()
        override['material'] = material
        bpy.ops.rpr.op_material_add_nodetree(override)
        return material.node_tree

    def get_active_material(self):
        return bpy.context.object.active_material

    def get_node_tree_output(self, tree):
        return node_editor.find_node_in_nodetree(tree, node_editor.shader_node_output_name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture()
def material_setup():
    print("fixture: material_setup")
    return MaterialSetupFixture()


########################################################################################################################
# Helpers
########################################################################################################################


def create_gradients_image(tmpdir_factory):
    width, height = 256, 256
    image = bpy.data.images.new("rpr_striped_gradients", width=width, height=height)
    im = np.ones((height, width, 4), dtype=np.float32)
    # make x-red gradient, y-green gradient, and blue hor. stripes
    im[:, :, 0] = np.linspace(0, 1, height, dtype=np.float32)[:, np.newaxis]
    im[:, :, 1] = np.linspace(0, 1, width, dtype=np.float32)[np.newaxis, :]

    x, y = np.meshgrid(np.linspace(0, 1, width), np.linspace(0, 1, height))
    # im[:, :, 2] = np.abs(((x+y)*32) % 2-1)
    im[:, :, 2] = np.cos(((x + y) * 64) * np.pi) * 0.5 + 0.5
    im[:, :, 3] = 1
    import imageio
    imageio.imwrite('test.png', im)
    image.pixels = im.flatten()
    image.filepath_raw = str(tmpdir_factory.mktemp('textures').join('image_texture.png'))
    image.file_format = 'PNG'
    image.save()
    return image


def create_striped_gradients_image(tmpdir_factory):
    fpath = str(tmpdir_factory.mktemp('textures').join('image_texture.png'))

    width, height = 256, 256
    im = np.flipud(create_striped_gradients_image_data(height, width))
    import imageio
    imageio.imwrite(fpath, im)

    return bpy.data.images.load(fpath)


def create_striped_gradients_image_packed(width, height):
    image = bpy.data.images.new("rpr_striped_gradients", width=width, height=height, alpha=True)
    im = create_striped_gradients_image_data(height, width)
    image.pixels = im.flatten()
    return image


def create_striped_gradients_image_data(height, width):
    im = np.ones((height, width, 4), dtype=np.float32)
    # make x-red gradient, y-green gradient, and blue hor. stripes
    x, y = np.meshgrid(np.linspace(0, 1, width), np.linspace(0, 1, height))
    im[:, :, 0] = np.linspace(0, 1, height, dtype=np.float32)[:, np.newaxis]
    im[:, :, 1] = np.linspace(0, 1, width, dtype=np.float32)[np.newaxis, :]
    im[:, :, 2] = (np.modf(np.linspace(0, 8, height, endpoint=False, dtype=np.float32))[0] < 0.5)[:, np.newaxis]
    im[:, :, 3] = np.modf((x + y) * 0.5 * 2)[0]
    return im


def create_striped_gradients_map(tree, request, tmpdir_factory):
    editor = MaterialEditor(tree)
    image_texture = editor.create_image_texture_node()
    image_texture.set_image(create_striped_gradients_image(tmpdir_factory))
    return image_texture.node


def create_striped_sky_image(path):
    width, height = 256, 256
    image = bpy.data.images.new("rpr_striped_sky", width=width, height=height)
    im = np.ones((height, width, 4), dtype=np.float32)
    # make x-red gradient, y-green gradient, and blue hor. stripes
    im[:, :, 0] = np.linspace(0, 1, height, dtype=np.float32)[:, np.newaxis]
    im[:, :, 1] = np.linspace(0, 1, width, dtype=np.float32)[np.newaxis, :]
    im[:, :, 2] = (np.modf(np.linspace(0, height * 0.5, height, endpoint=False, dtype=np.float32))[0] < 0.5)[:,
                  np.newaxis]
    im[:, :, 3] = 1
    # with open('im.list', 'w') as f:
    #     f.write(repr(im.tolist()))
    image.pixels = im.flatten()

    image.filepath_raw = path
    image.file_format = 'PNG'
    image.save()
    return image


def create_color_fill_image(path, color, size=(256, 256)):
    width, height = size
    image = create_color_fill_image_packed(color, (height, width))

    image.filepath_raw = path
    image.file_format = 'PNG'
    image.save()
    return image


def create_color_fill_image_packed(color, size):
    height, width = size
    image = bpy.data.images.new("rpr_striped_sky", width=width, height=height)
    im = np.full((height, width, 4), tuple(color) + (1,), dtype=np.float32)
    image.pixels = im.flatten()
    return image


def add_ibl(tmpdir_factory):
    path = str(tmpdir_factory.mktemp('data').join('ibl.png'))
    image = create_striped_sky_image(path)
    bpy.context.scene.world.rpr_data.environment.enable = True
    bpy.context.scene.world.rpr_data.environment.type = 'IBL'
    bpy.context.scene.world.rpr_data.environment.ibl.use_ibl_map = True
    set_ibl_image(bpy.context.scene.world.rpr_data.environment.ibl, path)


def create_hemisphere_image_data(size):
    a = np.linspace(0, 1, size, dtype=np.float32)
    x, y = np.meshgrid(a, a)
    return np.sqrt(1.0 - np.clip((np.power(x * 2.0 - 1, 2.0) + np.power(y * 2 - 1, 2.0)), 0, 1)).copy()


def create_hemisphere_image_map(name, tree, tmpdir_factory):
    node = tree.nodes.new(type='rpr_texture_node_image_map')
    width, height = 256, 256

    im = create_hemisphere_image_data(256)

    # make rgba
    im = im[:, :, np.newaxis]
    im = np.repeat(im, 4, axis=2)
    im[:, :, 3] = 1.0

    image = bpy.data.images.new(name, width=width, height=height)
    image.pixels = im.flatten()
    image.filepath_raw = str(tmpdir_factory.mktemp('textures').join(name + '.png'))
    image.file_format = 'PNG'
    image.save()

    if is_blender_support_new_image_node():
        node.image = image
    else:
        node.image_name = image.name

    return node


def generate_uv():
    # generate simple uvs
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.unwrap()
    bpy.ops.object.mode_set(mode='OBJECT')


def create_node_tree():
    mesh = bpy.context.object.data  # type: bpy.types.Mesh
    material = mesh.materials[0]
    # create material nodetree and retrieve it
    override = bpy.context.copy()
    override['material'] = material
    bpy.ops.rpr.op_material_add_nodetree(override)
    return material.node_tree


def get_surface_material(tree):
    output = node_editor.find_node_in_nodetree(tree, node_editor.shader_node_output_name)
    # this should be diffuse
    return output.inputs[output.shader_in].links[0].from_node


def add_normal_map(tree, node):
    node_normalmap = create_normalmap(tree)
    tree.links.new(node_normalmap.outputs[node_normalmap.value_out], node.inputs[node.normal_in])
    return node_normalmap


def create_normalmap(tree, scale=0.9):
    # add normal map node
    node_normalmap = tree.nodes.new(type='rpr_input_node_normalmap')
    node_normalmap.inputs[node_normalmap.scale_in].default_value = scale
    # add image map node
    node_imagemap = tree.nodes.new(type='rpr_texture_node_image_map')
    image = bpy_extras.image_utils.load_image(testdata.get_path('../data/material_normalmap_normals.png'))

    if is_blender_support_new_image_node():
        node_imagemap.image = image
    else:
        node_imagemap.image_name = image.name

    tree.links.new(node_imagemap.outputs[node_imagemap.value_out], node_normalmap.inputs[node_normalmap.map_in])
    return node_normalmap


def add_emissive_object(material_setup):
    # make an emissive mesh to show through our main cube with refraction material
    main_cube = bpy.context.object

    bpy.ops.mesh.primitive_cube_add()
    bpy.context.object.location = (0, 0, -0.75)
    bpy.context.object.scale = (0.5,) * 3

    material = bpy.data.materials.new('Material 2')
    mesh = bpy.context.object.data
    mesh.materials.append(material)

    tree = material_setup.create_default_node_tree()
    output = material_setup.get_node_tree_output(tree)

    emissive = tree.nodes.new(type='rpr_shader_node_emissive')
    emissive.inputs[emissive.color_in].default_value = (1, 1, 1, 1)
    tree.links.new(emissive.outputs[emissive.shader_out], output.inputs[output.shader_in])
    emissive.inputs[emissive.intensity_in].default_value = 1

    res = bpy.context.scene.objects.active
    bpy.context.scene.objects.active = main_cube
    return res


########################################################################################################################
# Nodes tests
########################################################################################################################

def material_from_testlib(name, expected):
    return name, ('../data/material_import/material_library_test/{0}/{0}.xml'.format(name), expected)


def material_from_reallib(name, expected):
    lib_path = r'C:\Program Files\AMD\RadeonProRenderPlugins\Maya\MaterialLibrary'
    return name, (lib_path + '/' + '{0}/{0}.xml'.format(name), expected)


class TestMaterialImport:
    tests = dict([
        material_from_testlib('Simple_Diffuse', 'material_diffuse_color_expected'),
        material_from_testlib('Simple_Diffuse_Textured', 'material_diffuse_image_map_expected'),
        material_from_testlib('Simple_Emissive', 'emissive/expected'),
        material_from_testlib('Simple_Diffuse_Bumpmap_Textured', 'diffuse_bumpmap_textures_expected'),
        material_from_testlib('Simple_Math_Mul', 'node_math/' + 'mul' + '_expected'),
        material_from_testlib('Simple_Microfacet', 'microfacet/microfacet_expected'),
        material_from_testlib('Simple_MicrofacetRefraction',
                              'microfacet_refraction/microfacet_refraction_normal_expected'),
        material_from_testlib('Simple_Reflection_Normalmap', 'reflection/reflection_normal_expected'),
        material_from_testlib('Simple_Refraction_Normalmap', 'refraction/refraction_normal_expected'),
        material_from_testlib('Simple_Blend', 'blend_expected'),
        material_from_testlib('Simple_Transparent', 'transparent/transparent_expected'),
        material_from_testlib('Simple_BlendValue', 'node_value_blend_expected'),

        material_from_testlib('Simple_Noise2d', 'material_noise2d_expected'),

        material_from_testlib('Simple_Fresnel', 'fresnel_node_expected'),
        material_from_testlib('Simple_FresnelSchlick', 'fresnel_schlick_node_expected'),
        material_from_testlib('Simple_OrenNayar', 'oren_nayar/oren_nayar_normal_expected'),

        # material_from_reallib('Emissive_CoolLight', 'Emissive_CoolLight.png'),
    ])

    @pytest.mark.parametrize("material_name", [k for k in tests.keys() if k is not None])
    def test_material_from_test_library(self, material_name, render_image_check_fixture, material_setup,
                                        tmpdir_factory):
        material_xml, expected = self.tests[material_name]

        if 'Simple_Reflection_Normalmap' in material_xml:
            add_ibl(tmpdir_factory)
        if 'Simple_Transparent' in material_xml:
            obj = add_emissive_object(material_setup)
            obj.scale = (2.0, 0.5, 0.5)

        if any(name in material_xml for name in ['Simple_MicrofacetRefraction', 'Simple_Refraction_Normalmap']):
            # make an emissive mesh to show through our main cube with refraction material
            add_emissive_object(material_setup)
            # reffraction with emissive needs a bit more iterations to converge(a lot) and for faster testing
            # we are we use bigger tolerance for image comparison
            bpy.context.scene.rpr.render.rendering_limits.iterations = 200

        expected_kwargs = {}
        if type(expected) == tuple:
            expected, expected_kwargs = expected
        with render_image_check_fixture.set_expected(expected, **expected_kwargs):
            generate_uv()

            tree = material_setup.create_default_node_tree()
            editor = MaterialEditor(tree)
            output = OutputNode(material_setup.get_node_tree_output(tree), editor)

            material_xml_path = testdata.get_path(material_xml)

            xml = open(testdata.get_path(material_xml_path)).read()

            image_loader = material_import.MaterialImageLoader(
                editor.load_image,
                root_folder=str(Path(material_xml_path).parent.parent),
                material_folder=str(Path(material_xml_path).parent))
            testee = material_import.compile_material_from_xml(xml, editor, image_loader)
            editor.link_nodes(testee, output.get_input_shader_socket())

    def iter_materials(self, material_library_path, editors: typing.Iterable[MaterialEditor]):
        editor_iter = iter(editors)
        for path in Path(material_library_path).iterdir():
            name = path.name
            fpath = path / (name + '.xml')
            if fpath.is_file():
                try:
                    editor = next(editor_iter)
                    image_loader = material_import.MaterialImageLoader(editor.load_image,
                                                                       root_folder=material_library_path,
                                                                       material_folder=str(path))
                    yield name, material_import.compile_material_from_xml(fpath.read_text(), editor, image_loader)
                except material_import.UnsupportedNode as e:
                    print('Unsupported:', name, e)
                except BaseException as e:
                    print('Failure:', name, e)

    @pytest.mark.skip
    def test_production_library(self, render_image_check_fixture, material_setup):

        material_library_path = r'C:\Program Files\AMD\RadeonProRenderPlugins\Maya\MaterialLibrary'

        def iter_material_editors():
            while True:
                yield editor

        mtl_iter = iter(self.iter_materials(material_library_path, iter_material_editors()))
        for i in itertools.count():

            preview_scene_folder = Path(__file__).parent.parent.parent / 'tests' / 'preview'
            bpy.ops.wm.open_mainfile(filepath=str(preview_scene_folder / 'orb.blend'))

            # bpy.context.scene.rpr.render.rendering_limits.iterations = 200
            # render_image_check_fixture.viewport_fixture.render_resolution = (512, 512)
            bpy.context.scene.rpr.render.rendering_limits.type = 'ITER'  # TIME ITER
            bpy.context.scene.rpr.render.rendering_limits.time = 5
            bpy.context.scene.rpr.render.rendering_limits.iterations = 400
            render_image_check_fixture.viewport_fixture.render_resolution = (128, 128)

            rpr_settings = bpy.context.scene.rpr.render
            rpr_settings.aa.filter = "MITCHELL"
            rpr_settings.aa.radius = 1.5
            rpr_settings.global_illumination.max_ray_depth = 10

            for o in bpy.context.scene.objects:
                if o.name.startswith('Line'):
                    material = o.active_material

                    material.use_nodes = True
                    tree = material.node_tree
                    tree.nodes.clear()

                    output = tree.nodes.new('rpr_shader_node_output')
                    output.location = 550, 400

                    editor = MaterialEditor(tree)

                    shader = editor.create_diffuse_material_node()
                    shader.set_input_socket_value_by_name('color', (0, 1, 0, 1))

                    image_texture = editor.create_image_texture_node()

                    image = bpy_extras.image_utils.load_image(
                        str(preview_scene_folder / '53863A_AMD_E_Blk_RGB_square.png'))
                    image_texture.set_image(image)
                    editor.link_nodes(image_texture, shader.get_input_socket_by_name('color'))

                    editor.link_nodes(shader, material_editor.OutputNode(output, editor).get_input_shader_socket())

            materials = set()
            for o in bpy.context.scene.objects:
                if o.name.startswith('Probe'):
                    materials.add(o.active_material)

            assert 1 == len(materials)
            material = materials.pop()

            material.use_nodes = True
            tree = material.node_tree
            tree.nodes.clear()

            output = tree.nodes.new('rpr_shader_node_output')
            output.location = 550, 400

            editor = MaterialEditor(tree)

            try:
                name, shader = next(mtl_iter)
            except StopIteration:
                break

            editor.link_nodes(shader, material_editor.OutputNode(output, editor).get_input_shader_socket())

            with render_image_check_fixture.set_expected('production_material_library/' + name + '.png', gamma=2.2,
                                                         clamp=(0, 1)):
                pass
        print(i)


def test_render_image_check_fixture(render_image_check_fixture):
    bpy.context.scene.rpr.render.rendering_limits.iterations = 10

    with render_image_check_fixture.set_expected(None):
        generate_uv()

    renderer = render_image_check_fixture.viewport_fixture.viewport_renderer.scene_renderer

    if not render_image_check_fixture.quick:
        assert 9 == renderer.iteration_in_progress
    else:
        assert 0 == renderer.iteration_in_progress


@notquick
def test_default_scene_stress(render_image_check_fixture, material_setup, request, tmpdir_factory):
    basic_render_settings()
    rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
    rpr_settings.rendering_limits.iterations = 1

    time_start = time.perf_counter()

    for i in range(100):
        print('stress:', i)
        fixture = ViewportFixture()
        fixture.start()
        fixture.viewport_renderer.scene_renderer_threaded.sleep_delay = 0
        fixture.wait_for_render_complete()
        fixture.destroy()

    print('done in ', time.perf_counter() - time_start)


def test_material_diffuse(render_image_check_fixture, material_setup, request, tmpdir_factory):
    with render_image_check_fixture.set_expected('material_diffuse_color_expected'):
        generate_uv()

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)

        # create Normal Map node and connect it to Diffuse material Normal input
        testee = editor.create_diffuse_material_node()

        editor.link_nodes(testee, output.get_input_shader_socket())

        editor.link_nodes(testee, output.get_input_shader_socket())
        testee.set_color_value((1, 1, 0, 1))

    with render_image_check_fixture.set_expected('material_diffuse_image_map_expected'):
        image_texture = editor.create_image_texture_node()
        image_texture.set_image(create_striped_gradients_image_packed(256, 256))
        editor.link_nodes(image_texture, testee.get_input_socket_by_name('color'))

    with render_image_check_fixture.set_expected('material_diffuse_image_map_packed_expected'):
        width, height = (32, 32)
        image = bpy.data.images.new("rpr_fantasy", width=width, height=height)
        im = np.full((height, width, 4), (0.25, 0.5, 0.75, 1), dtype=np.float32)
        image.pixels = im.flatten()

        image_texture = editor.create_image_texture_node()
        image_texture.set_image(image)
        editor.link_nodes(image_texture, testee.get_input_socket_by_name('color'))

@pytest.mark.skip
def test_region(render_image_check_fixture, material_setup, request, tmpdir_factory):
    render_image_check_fixture.viewport_fixture.render_region = None
    with render_image_check_fixture.set_expected('region/none_expected'):
        generate_uv()

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)

        # create Normal Map node and connect it to Diffuse material Normal input
        testee = editor.create_diffuse_material_node()

        editor.link_nodes(testee, output.get_input_shader_socket())

        editor.link_nodes(testee, output.get_input_shader_socket())
        testee.set_color_value((1, 1, 0, 1))

    with render_image_check_fixture.set_expected('region/none_expected'):
        pass

    resolution = render_image_check_fixture.viewport_fixture.render_resolution

    render_image_check_fixture.viewport_fixture.viewport_renderer.update_render_region((0, resolution[0]-1, 0, resolution[1]-1))
    with render_image_check_fixture.set_expected('region/none_expected'):
        pass

    render_image_check_fixture.viewport_fixture.viewport_renderer.update_render_region((0, resolution[0]//2-1, 0, resolution[1]//2-1))
    with render_image_check_fixture.set_expected('region/quedrant_0_expected'):
        pass



def test_material_image_sync(render_image_check_fixture, material_setup, request, tmpdir_factory):
    """ Check that image on materials syncs without problems, can be removed, re-added
    and doesn't misbehave(e.g. not deleted along the way)
    """

    with render_image_check_fixture.set_expected('material_diffuse_color_expected'):
        generate_uv()

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)

        # create Normal Map node and connect it to Diffuse material Normal input
        testee = editor.create_diffuse_material_node()

        editor.link_nodes(testee, output.get_input_shader_socket())

        editor.link_nodes(testee, output.get_input_shader_socket())
        testee.set_color_value((1, 1, 0, 1))

    log("set image")
    image_file = create_striped_gradients_image_packed(256, 256)
    with render_image_check_fixture.set_expected_synced('material_diffuse_image_map_expected'):
        image_texture = editor.create_image_texture_node()
        image_texture.set_image(image_file)
        editor.link_nodes(image_texture, testee.get_input_socket_by_name('color'))

    log("set packed image")
    with render_image_check_fixture.set_expected_synced('material_diffuse_image_map_packed_expected'):
        width, height = (32, 32)
        image = bpy.data.images.new("rpr_fantasy", width=width, height=height)
        im = np.full((height, width, 4), (0.25, 0.5, 0.75, 1), dtype=np.float32)
        image.pixels = im.flatten()

        image_texture = editor.create_image_texture_node()
        image_texture.set_image(image)
        editor.link_nodes(image_texture, testee.get_input_socket_by_name('color'))

    log("set image back")
    with render_image_check_fixture.set_expected_synced('material_diffuse_image_map_expected'):
        image_texture = editor.create_image_texture_node()
        image_texture.set_image(image_file)
        editor.link_nodes(image_texture, testee.get_input_socket_by_name('color'))


def test_material_blend(render_image_check_fixture, material_setup, request, tmpdir_factory):
    with render_image_check_fixture.set_expected('blend_expected'):
        generate_uv()

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)

        testee = editor.create_blend_material_node()

        editor.link_nodes(testee, output.get_input_shader_socket())

        a = editor.create_diffuse_material_node()
        a.set_input_socket_value_by_name('color', (1, 1, 0, 1))
        editor.link_nodes(a, testee.get_input_socket_by_name('shader1'))

        b = editor.create_diffuse_material_node()
        b.set_input_socket_value_by_name('color', (0, 0, 1, 1))
        editor.link_nodes(b, testee.get_input_socket_by_name('shader2'))

        testee.set_input_socket_value_by_name('weight', 0.25)


def test_material_normalmap(render_image_check_fixture, material_setup):
    # no input connected
    with render_image_check_fixture.set_expected('material_error'):
        # generate simple uvs
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.unwrap()
        bpy.ops.object.mode_set(mode='OBJECT')

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = material_editor.OutputNode(material_setup.get_node_tree_output(tree), editor)

        # this should be diffuse
        surface_material = material_editor.DiffuseMaterial(output.get_input_shader_socket().links[0].from_node, editor)

        # create Normal Map node and connect it to Diffuse material Normal input

        node_normalmap = editor.create_normalmap_node()
        editor.link_nodes(node_normalmap, surface_material.get_input_socket_by_name('normal'))
        node_normalmap.set_scale_value(1.5)

    # image input
    with render_image_check_fixture.set_expected('normalmap/image_expected'):
        # load image into imagemap node and connect it to NormalMap node input
        node_imagemap = material_editor.ValueNode(tree.nodes.new(type='rpr_texture_node_image_map'), editor)
        image = bpy_extras.image_utils.load_image(testdata.get_path('../data/material_normalmap_normals.png'))
        if is_blender_support_new_image_node():
            node_imagemap.node.image = image
        else:
            node_imagemap.node.image_name = image.name

        editor.link_nodes(node_imagemap, node_normalmap.get_input_socket_by_name('map'))

    with render_image_check_fixture.set_expected('normalmap/mapping_expected'):
        node_mapping = material_editor.ValueNode(tree.nodes.new(type='rpr_mapping_node'), editor)

        node_mapping.set_input_socket_value_by_name('scale', (2, 2))
        node_mapping.set_input_socket_value_by_name('offset', (0.1, 0.1))
        editor.link_nodes(node_mapping, node_imagemap.get_input_socket_by_name('mapping'))


def test_material_bumpmap(render_image_check_fixture, material_setup, tmpdir_factory):
    # no input connected
    with render_image_check_fixture.set_expected('material_error'):
        generate_uv()

        tree = material_setup.create_default_node_tree()
        output = material_setup.get_node_tree_output(tree)

        editor = MaterialEditor(tree)

        surface_material = material_editor.DiffuseMaterial(output.inputs[output.shader_in].links[0].from_node, editor)

        # create Normal Map node and connect it to Diffuse material Normal input

        testee = editor.create_bumpmap_node()

        editor.link_nodes(testee, surface_material.get_input_normal_socket())
        testee.set_scale_value(1.5)

    # test image input
    with render_image_check_fixture.set_expected('material_bumpmap/image_expected'):
        node_imagemap = material_editor.ImageTexture(create_hemisphere_image_map('bumpmap', tree, tmpdir_factory),
                                                     editor)
        editor.link_nodes(node_imagemap, testee.get_input_map_socket())

    # test mapping
    with render_image_check_fixture.set_expected('material_bumpmap/mapping_expected'):
        node_mapping = material_editor.ValueNode(tree.nodes.new(type='rpr_mapping_node'), editor)

        node_mapping.set_input_socket_value_by_name('scale', (2, 2))
        node_mapping.set_input_socket_value_by_name('offset', (0.1, 0.1))
        editor.link_nodes(node_mapping, node_imagemap.get_input_socket_by_name('mapping'))

    # test noise2d input
    with render_image_check_fixture.set_expected('material_bumpmap/noise_expected'):
        testee.set_scale_value(10)
        node_mapping.set_input_socket_value_by_name('scale', (1, 1))
        node_mapping.set_input_socket_value_by_name('offset', (0, 0))

        # load image into imagemap node and connect it to NormalMap node input
        node_noise = material_editor.ValueNode(tree.nodes.new(type='rpr_texture_node_noise2d'), editor)
        editor.link_nodes(node_noise,
                          testee.get_input_map_socket())
        editor.link_nodes(node_mapping, node_noise.get_input_socket_by_name('mapping'))

    # test dot input
    with render_image_check_fixture.set_expected('material_bumpmap/dot_expected'):
        node_mapping.set_input_socket_value_by_name('scale', (
            (0.125, 0.125) if 0x010000239 >= pyrpr.API_VERSION else
            (1, 1)))

        node_mapping.set_input_socket_value_by_name('offset', (0.0, 0.0))
        editor.link_nodes(material_editor.ValueNode(tree.nodes.new(type='rpr_texture_node_dot'), editor),
                          testee.get_input_map_socket())


def test_material_subsurface(render_image_check_fixture, material_setup, request, tmpdir_factory):
    add_emissive_object(material_setup)
    bpy.context.scene.rpr.render.rendering_limits.iterations = 100

    with render_image_check_fixture.set_expected('material_subsurface/subsurface_default'):
        generate_uv()

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)

        volume = editor.create_subsurface_material_node()
        volume_node = volume.node
        editor.link_nodes(volume, output.get_input_volume_socket())

        diffuse = editor.create_diffuse_material_node()
        diffuse.set_input_socket_value_by_name('color', (1, 1, 0, 1))
        editor.link_nodes(diffuse, output.get_input_shader_socket())

    with render_image_check_fixture.set_expected('material_subsurface/subsurface_intensity_0'):
        volume_node.inputs[volume_node.surface_intensity_in].default_value = 0.0

    with render_image_check_fixture.set_expected('material_subsurface/subsurface_intensity_1'):
        volume_node.inputs[volume_node.surface_intensity_in].default_value = 1.0

    with render_image_check_fixture.set_expected('material_subsurface/subsurface_density_0'):
        volume_node.inputs[volume_node.surface_intensity_in].default_value = 0.5
        volume_node.inputs[volume_node.density_in].default_value = 0.0

    with render_image_check_fixture.set_expected('material_subsurface/subsurface_scatter_amount_1'):
        volume_node.inputs[volume_node.surface_intensity_in].default_value = 0.3
        volume_node.inputs[volume_node.density_in].default_value = 1
        volume_node.inputs[volume_node.scatter_amount_in].default_value = 1
        volume_node.inputs[volume_node.subsurface_color_in].default_value = (0, 0, 1, 0)
        volume_node.inputs[volume_node.emission_color_in].default_value = (0, 1, 0, 0)
        volume_node.inputs[volume_node.scatter_color_in].default_value = (1, 0, 0, 0)

    with render_image_check_fixture.set_expected('material_subsurface/subsurface_scatter_amount_0'):
        volume_node.inputs[volume_node.scatter_amount_in].default_value = 0

    with render_image_check_fixture.set_expected('material_subsurface/subsurface_scattering_direction_neg'):
        volume_node.inputs[volume_node.scatter_amount_in].default_value = 1
        volume_node.inputs[volume_node.scattering_direction_in].default_value = -1

    with render_image_check_fixture.set_expected('material_subsurface/subsurface_scattering_direction_pos'):
        volume_node.inputs[volume_node.scattering_direction_in].default_value = 1

    # following crashes on CPU
    if enable_cpu and (0x010000255 >= pyrpr.API_VERSION):
        return

    with render_image_check_fixture.set_expected('material_subsurface/subsurface_multiscatter'):
        volume_node.inputs[volume_node.multiscatter_in].default_value = True


def test_material_volume(render_image_check_fixture, material_setup, request, tmpdir_factory):
    add_emissive_object(material_setup)
    bpy.context.scene.rpr.render.rendering_limits.iterations = 100

    with render_image_check_fixture.set_expected('material_volume/volume_default'):
        generate_uv()

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)

        volume = editor.create_volume_material_node()
        volume_node = volume.node
        editor.link_nodes(volume, output.get_input_volume_socket())

    with render_image_check_fixture.set_expected('material_volume/volume_density'):
        volume_node.inputs[volume_node.density_in].default_value = 0.0

    with render_image_check_fixture.set_expected('material_volume/volume_color'):
        volume_node.inputs[volume_node.density_in].default_value = 0.6
        volume_node.inputs[volume_node.transmission_color_in].default_value = (0, 0, 1, 0)
        volume_node.inputs[volume_node.emission_color_in].default_value = (0, 1, 0, 0)
        volume_node.inputs[volume_node.scatter_color_in].default_value = (1, 0, 0, 0)

    with render_image_check_fixture.set_expected('material_volume/volume_scattering_direction_neg'):
        volume_node.inputs[volume_node.scattering_direction_in].default_value = -1

    with render_image_check_fixture.set_expected('material_volume/volume_scattering_direction_pos'):
        volume_node.inputs[volume_node.scattering_direction_in].default_value = 1

    # following crashes on CPU
    if enable_cpu and (0x010000255 >= pyrpr.API_VERSION):
        return

    with render_image_check_fixture.set_expected('material_volume/volumee_multiscatter'):
        volume_node.inputs[volume_node.multiscatter_in].default_value = True

    with render_image_check_fixture.set_expected_synced('material_volume/detached'):
        editor.tree.links.remove(output.get_input_socket_by_name('volume').links[0])


def test_material_noise2d(render_image_check_fixture):
    # TODO: Noise2d renders negative pixels - AMDBLENDER-99
    max_dev = None

    # offset - noise2d somehow render negative values on diffuse
    with render_image_check_fixture.set_expected('material_noise2d_expected', max_avg_dev=max_dev, max_std_dev=max_dev):
        generate_uv()
        tree = create_node_tree()
        editor = MaterialEditor(tree)
        surface_material = material_editor.DiffuseMaterial(get_surface_material(tree), editor)
        # create Normal Map node and connect it to Diffuse material Normal input
        testee = editor.create_noise2d_node()
        editor.link_nodes(testee, surface_material.get_input_socket_by_name('color'))


def test_material_gradient(render_image_check_fixture):
    # Test default gradient.
    with render_image_check_fixture.set_expected('material_gradient_expected'):
        # generate simple uvs
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.unwrap()
        bpy.ops.object.mode_set(mode='OBJECT')

        # setup material graph
        mesh = bpy.context.object.data  # type: bpy.types.Mesh
        material = mesh.materials[0]

        # create material nodetree and retrieve it
        override = bpy.context.copy()
        override['material'] = material
        bpy.ops.rpr.op_material_add_nodetree(override)
        tree = material.node_tree
        output = node_editor.find_node_in_nodetree(tree, node_editor.shader_node_output_name)

        # this should be diffuse
        surface_material = output.inputs[output.shader_in].links[0].from_node

        # create gradient node and connect it to diffuse material
        node_gradient = tree.nodes.new(type='rpr_texture_node_gradient')
        tree.links.new(node_gradient.outputs[node_gradient.value_out],
                       surface_material.inputs[surface_material.color_in])

    # Test red / blue gradient.
    with render_image_check_fixture.set_expected('material_gradient_color_expected'):
        node_gradient.inputs[node_gradient.color1_in].default_value = (1, 0, 0, 1)
        node_gradient.inputs[node_gradient.color2_in].default_value = (0, 0, 1, 1)


def test_material_checker(render_image_check_fixture):
    # Test default checker pattern.
    with render_image_check_fixture.set_expected('material_checker_expected'):

        # generate simple uvs
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.unwrap()
        bpy.ops.object.mode_set(mode='OBJECT')

        # setup material graph
        mesh = bpy.context.object.data  # type: bpy.types.Mesh
        material = mesh.materials[0]

        # create material nodetree and retrieve it
        override = bpy.context.copy()
        override['material'] = material
        bpy.ops.rpr.op_material_add_nodetree(override)
        tree = material.node_tree
        output = node_editor.find_node_in_nodetree(tree, node_editor.shader_node_output_name)

        # this should be diffuse
        surface_material = output.inputs[output.shader_in].links[0].from_node

        # create checker node and connect it to diffuse material
        testee = tree.nodes.new(type='rpr_texture_node_checker')
        tree.links.new(testee.outputs[testee.value_out], surface_material.inputs[surface_material.color_in])

        if 0x010000236 >= pyrpr.API_VERSION:
            node_mapping = tree.nodes.new(type='rpr_mapping_node')
            tree.links.new(node_mapping.outputs[node_mapping.value_out], testee.inputs[testee.mapping_in])
            node_mapping.inputs[node_mapping.scale_in].default_value = (8, 8)

    # Test 2x scaled and offset UV coordinates checker pattern.
    with render_image_check_fixture.set_expected('material_checker_scaled_expected'):
        node_mapping = tree.nodes.new(type='rpr_mapping_node')
        tree.links.new(node_mapping.outputs[node_mapping.value_out], testee.inputs[testee.mapping_in])

        if 0x010000236 >= pyrpr.API_VERSION:
            node_mapping.inputs[node_mapping.scale_in].default_value = (2 * 8, 2 * 8)
            node_mapping.inputs[node_mapping.offset_in].default_value = (0.1 * 8, 0.1 * 8)
        else:
            node_mapping.inputs[node_mapping.scale_in].default_value = (2, 2)
            node_mapping.inputs[node_mapping.offset_in].default_value = (0.1, 0.1)


def test_texture_node_dot(render_image_check_fixture):
    # Test default dot texture.
    with render_image_check_fixture.set_expected('texture_node_dot_expected'):
        generate_uv()
        tree = create_node_tree()
        surface_material = get_surface_material(tree)
        node = tree.nodes.new(type='rpr_texture_node_dot')
        tree.links.new(node.outputs[node.value_out], surface_material.inputs[surface_material.color_in])

        if 0x010000239 >= pyrpr.API_VERSION:
            node_mapping = tree.nodes.new(type='rpr_mapping_node')
            node_mapping.inputs[node_mapping.scale_in].default_value = (1 / 8, 1 / 8)
            tree.links.new(node_mapping.outputs[node_mapping.value_out], node.inputs[node.mapping_in])

    # Test dot texture with UV scale param.
    with render_image_check_fixture.set_expected('texture_node_dot_scaled_expected'):
        node_mapping = tree.nodes.new(type='rpr_mapping_node')
        # node_mapping.inputs[node_mapping.scale_in].default_value = (5, 5)
        node_mapping.inputs[node_mapping.scale_in].default_value = (
            (5 / 8, 5 / 8) if 0x010000239 >= pyrpr.API_VERSION else
            (5, 5))

        tree.links.new(node_mapping.outputs[node_mapping.value_out], node.inputs[node.mapping_in])


def test_fresnel_schlick_node(render_image_check_fixture):
    with render_image_check_fixture.set_expected('fresnel_schlick_node_expected'):
        generate_uv()
        tree = create_node_tree()
        editor = MaterialEditor(tree)
        surface_material = material_editor.DiffuseMaterial(get_surface_material(tree), editor)

        node = editor.create_fresnel_schlick_node()
        editor.link_nodes(node, surface_material.get_input_socket_by_name('color'))
        node.set_input_socket_value_by_name('reflectance', 0.2)

        # add lookup node
        lookup = editor.create_input_lookup_node()
        editor.link_nodes(lookup, node.get_input_socket_by_name('in_vec'))
        lookup.node.type = 'INVEC'

        add_normal_map(tree, node.node)


def test_fresnel_node(render_image_check_fixture):
    with render_image_check_fixture.set_expected('fresnel_node_expected'):
        generate_uv()
        tree = create_node_tree()
        editor = MaterialEditor(tree)
        surface_material = material_editor.DiffuseMaterial(get_surface_material(tree), editor)

        node = editor.create_fresnel_node()
        editor.link_nodes(node, surface_material.get_input_socket_by_name('color'))
        node.set_input_socket_value_by_name('ior', 1.52)

        # add lookup node
        lookup = editor.create_input_lookup_node()
        editor.link_nodes(lookup, node.get_input_socket_by_name('in_vec'))
        lookup.node.type = 'INVEC'

        add_normal_map(tree, node.node)


def test_shader_node_value(render_image_check_fixture, material_setup, request, tmpdir_factory):
    with render_image_check_fixture.set_expected('value/value_vector'):
        generate_uv()
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)
        diffuse_node = editor.create_diffuse_material_node()

        editor.link_nodes(diffuse_node, output.get_input_shader_socket())

        value_node = editor.create_input_value_node()
        editor.link_nodes(value_node, diffuse_node.get_input_socket_by_name('color'))
        value_node.node.type = 'vector'
        value_node.node.default_value = (1, 0, 1, 1)


def test_shader_node_oren_nayar(render_image_check_fixture, material_setup):
    with render_image_check_fixture.set_expected('oren_nayar/oren_nayar_expected'):
        generate_uv()
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = material_editor.OutputNode(material_setup.get_node_tree_output(tree), editor)
        node = editor.create_oren_nayar_material_node()
        # roughness is default 0.5
        editor.link_nodes(node, output.get_input_shader_socket())

    with render_image_check_fixture.set_expected('oren_nayar/oren_nayar_roughness_0_expected'):
        node.set_input_socket_value_by_name('roughness', 0)

    with render_image_check_fixture.set_expected('oren_nayar/oren_nayar_roughness_1_expected'):
        node.set_input_socket_value_by_name('roughness', 1)

    with render_image_check_fixture.set_expected('oren_nayar/oren_nayar_normal_expected'):
        node.set_input_socket_value_by_name('roughness', 0.5)
        add_normal_map(tree, node.node)


def test_shader_node_microfacet(render_image_check_fixture, material_setup):
    with render_image_check_fixture.set_expected('microfacet/microfacet_expected'):
        generate_uv()
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = material_editor.OutputNode(material_setup.get_node_tree_output(tree), editor)

        node = editor.create_microfacet_material_node()
        # roughness is default 0.5
        editor.link_nodes(node, output.get_input_shader_socket())

    with render_image_check_fixture.set_expected('microfacet/microfacet_roughness_0_expected'):
        node.set_input_socket_value_by_name('roughness', 0)

    with render_image_check_fixture.set_expected('microfacet/microfacet_roughness_1_expected'):
        node.set_input_socket_value_by_name('roughness', 1)

    with render_image_check_fixture.set_expected('microfacet/microfacet_normal_expected'):
        node.set_input_socket_value_by_name('roughness', 0.5)

        normal_map = material_editor.ValueNode(create_normalmap(tree), editor)
        normal_map.set_input_socket_value_by_name('scale', 0.4)
        editor.link_nodes(normal_map, node.get_input_socket_by_name('normal'))


def test_shader_node_microfacet_refraction(render_image_check_fixture, material_setup):
    # make an emissive mesh to show through our main cube with refraction material
    add_emissive_object(material_setup)
    # reffraction with emissive needs a bit more iterations to converge(a lot) and for faster testing
    # we are we use bigger tolerance for image comparison
    bpy.context.scene.rpr.render.rendering_limits.iterations = 200

    with render_image_check_fixture.set_expected('microfacet_refraction/microfacet_refraction_expected'):
        generate_uv()
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = material_editor.OutputNode(material_setup.get_node_tree_output(tree), editor)
        node = editor.create_microfacet_refraction_material_node()

        # roughness is default 0.5
        # ior is default 1.0
        editor.link_nodes(node, output.get_input_shader_socket())

    with render_image_check_fixture.set_expected('microfacet_refraction/microfacet_refraction_roughness_0_expected'):
        node.set_input_socket_value_by_name('roughness', 0)

    with render_image_check_fixture.set_expected('microfacet_refraction/microfacet_refraction_roughness_1_expected'):
        node.set_input_socket_value_by_name('roughness', 1)

    with render_image_check_fixture.set_expected('microfacet_refraction/microfacet_refraction_ior_glass_expected'):
        node.set_input_socket_value_by_name('ior', 1.52)

    with render_image_check_fixture.set_expected('microfacet_refraction/microfacet_refraction_normal_expected'):
        normal_map = material_editor.ValueNode(create_normalmap(tree), editor)
        normal_map.set_input_socket_value_by_name('scale', 0.5)
        editor.link_nodes(normal_map, node.get_input_socket_by_name('normal'))


def test_shader_node_refraction(render_image_check_fixture, material_setup, request, tmpdir_factory):
    # make an emissive mesh to show through our main cube with refraction material
    add_emissive_object(material_setup)
    # reffraction with emissive needs a bit more iterations to converge(a lot) and for faster testing
    # we are we use bigger tolerance for image comparison
    bpy.context.scene.rpr.render.rendering_limits.iterations = 200
    # add_ibl(tmpdir_factory)

    with render_image_check_fixture.set_expected('refraction/refraction_expected'):
        generate_uv()
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = material_setup.get_node_tree_output(tree)
        node = editor.create_refraction_material_node()

        # ior is default 1.0
        editor.link_nodes(node, material_editor.OutputNode(output, editor).get_input_shader_socket())

    with render_image_check_fixture.set_expected('refraction/refraction_ior_glass_expected'):
        node.set_input_socket_value_by_name('ior', 1.52)

    with render_image_check_fixture.set_expected('refraction/refraction_normal_expected'):
        normal_map = material_editor.ValueNode(create_normalmap(tree), editor)
        normal_map.set_input_socket_value_by_name('scale', 0.4)
        editor.link_nodes(normal_map, node.get_input_socket_by_name('normal'))


def test_shader_node_reflection(render_image_check_fixture, material_setup, request, tmpdir_factory):
    add_ibl(tmpdir_factory)

    with render_image_check_fixture.set_expected('reflection/reflection_expected'):
        generate_uv()
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = material_editor.OutputNode(material_setup.get_node_tree_output(tree), editor)
        node = editor.create_reflection_material_node()
        editor.link_nodes(node, output.get_input_shader_socket())

    with render_image_check_fixture.set_expected('reflection/reflection_color_expected'):
        node.set_color_value((0.5, 1, 0.75, 1))

    node.set_color_value((1, 1, 1, 1))

    with render_image_check_fixture.set_expected('reflection/reflection_normal_expected'):
        normal_map = material_editor.ValueNode(create_normalmap(tree), editor)
        editor.link_nodes(normal_map, node.get_input_socket_by_name('normal'))
        normal_map.set_input_socket_value_by_name('scale', 0.5)

    with render_image_check_fixture.set_expected('reflection/reflection_color_node_expected'):
        noise = editor.create_noise2d_node()
        editor.link_nodes(noise, node.get_input_socket_by_name('color'))


def test_shader_node_transparent(render_image_check_fixture, material_setup, request, tmpdir_factory):
    obj = add_emissive_object(material_setup)
    obj.scale = (2.0, 0.5, 0.5)

    with render_image_check_fixture.set_expected('transparent/transparent_expected'):
        generate_uv()
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = material_editor.OutputNode(material_setup.get_node_tree_output(tree), editor)
        node = editor.create_transparent_material_node()
        editor.link_nodes(node, output.get_input_shader_socket())
        node.set_input_socket_value_by_name('color', (1.0, 0.5, 0.1, 1))


def test_shader_node_ward(render_image_check_fixture, material_setup, request, tmpdir_factory):
    # obj = add_emissive_object(material_setup)
    # obj.scale = (2.0,0.5,0.5)

    with render_image_check_fixture.set_expected('ward/ward_expected'):
        generate_uv()
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = material_editor.OutputNode(material_setup.get_node_tree_output(tree), editor)
        node = editor.create_ward_material_node()
        editor.link_nodes(node, output.get_input_shader_socket())

    with render_image_check_fixture.set_expected('ward/ward_roughness_y_expected'):
        node.set_input_socket_value_by_name('roughness_x', 0.5)
        node.set_input_socket_value_by_name('roughness_y', 1)

    with render_image_check_fixture.set_expected('ward/ward_roughness_x_expected'):
        node.set_input_socket_value_by_name('roughness_x', 1)
        node.set_input_socket_value_by_name('roughness_y', 0.1)

    with render_image_check_fixture.set_expected('ward/ward_rotation_expected'):
        node.set_input_socket_value_by_name('rotation', -0.5)

    with render_image_check_fixture.set_expected('ward/ward_normal_expected'):
        normal_map = add_normal_map(tree, node.node)
        normal_map.inputs[normal_map.scale_in].default_value = 0.5


def test_material_lookup(render_image_check_fixture, material_setup):
    with render_image_check_fixture.set_expected('material_lookup_expected'):
        # generate simple uvs
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.unwrap()
        bpy.ops.object.mode_set(mode='OBJECT')

        tree = material_setup.create_default_node_tree()
        output = material_setup.get_node_tree_output(tree)

        # this should be diffuse
        surface_material = output.inputs[output.shader_in].links[0].from_node

        # create node and connect it to material input
        lookup = tree.nodes.new(type='rpr_input_node_lookup')
        tree.links.new(lookup.outputs[lookup.value_out], surface_material.inputs[surface_material.color_in])
        lookup.type = 'UV'

    with render_image_check_fixture.set_expected('material_lookup_P_expected'):
        lookup.type = 'P'

    with render_image_check_fixture.set_expected('material_lookup_INVEC_expected'):
        lookup.type = 'INVEC'

    with render_image_check_fixture.set_expected('material_lookup_N_expected'):
        lookup.type = 'N'


def test_material_emissive(render_image_check_fixture, material_setup):
    with render_image_check_fixture.set_expected('emissive/expected'):
        # generate simple uvs
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.unwrap()
        bpy.ops.object.mode_set(mode='OBJECT')

        mesh = bpy.context.object.data  # type: bpy.types.Mesh
        material = mesh.materials[0]

        # create material nodetree and retrieve it
        override = bpy.context.copy()
        override['material'] = material
        bpy.ops.rpr.op_material_add_nodetree(override)
        tree = material.node_tree
        material_editor = MaterialEditor(tree)
        output = OutputNode(node_editor.find_node_in_nodetree(tree, node_editor.shader_node_output_name),
                            material_editor)

        # create Normal Map node and connect it to Diffuse material Normal input
        emissive = material_editor.create_emissive_material_node()

        material_editor.link_nodes(emissive, output.get_input_shader_socket())
        emissive.set_color_value((1, 1, 0, 1))

    with render_image_check_fixture.set_expected('emissive/uv_input_expected'):
        lookup = material_editor.create_input_lookup_node()
        material_editor.link_nodes(lookup, emissive.get_input_socket_by_name('color'))
        lookup.set_type('UV')

    with render_image_check_fixture.set_expected('emissive/intensity_expected'):
        emissive.set_input_socket_value_by_name('intensity', 10)


def test_material_diffuse_refraction(render_image_check_fixture, material_setup):
    # make an emissive mesh to show through our main cube with refraction material
    add_emissive_object(material_setup)
    # reffraction with emissive needs a bit more iterations to converge(a lot) and for faster testing
    # we are we use bigger tolerance for image comparison
    bpy.context.scene.rpr.render.rendering_limits.iterations = 200
    with render_image_check_fixture.set_expected('material_diffuse_refraction/expected', max_avg_dev=0.01,
                                                 max_std_dev=0.02):
        bpy.context.object.scale = (1.0, 1.0, 0.1)

        # generate simple uvs
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.unwrap()
        bpy.ops.object.mode_set(mode='OBJECT')

        tree = material_setup.create_default_node_tree()
        output = material_setup.get_node_tree_output(tree)

        testee = tree.nodes.new(type='rpr_shader_node_diffuse_refraction')
        tree.links.new(testee.outputs[testee.shader_out], output.inputs[output.shader_in])

        testee.inputs[testee.color_in].default_value = (1, 1, 0, 1)

    with render_image_check_fixture.set_expected('material_diffuse_refraction/color_node_expected', max_avg_dev=0.01,
                                                 max_std_dev=0.02):
        node_checker = tree.nodes.new(type='rpr_texture_node_checker')
        tree.links.new(node_checker.outputs[node_checker.value_out], testee.inputs[testee.color_in])
        if 0x010000236 >= pyrpr.API_VERSION:
            node_mapping = tree.nodes.new(type='rpr_mapping_node')
            tree.links.new(node_mapping.outputs[node_mapping.value_out], node_checker.inputs[node_checker.mapping_in])
            node_mapping.inputs[node_mapping.scale_in].default_value = (8, 8)

    with render_image_check_fixture.set_expected('material_diffuse_refraction/normal_image_expected', max_avg_dev=0.01,
                                                 max_std_dev=0.02):
        testee.inputs[testee.color_in].default_value = (1, 1, 1, 1)

        # create Normal Map node and connect it to Diffuse material Normal input
        node_normalmap = tree.nodes.new(type='rpr_input_node_normalmap')
        tree.links.new(node_normalmap.outputs[node_normalmap.value_out], testee.inputs[testee.normal_in])
        # node_normalmap.inputs[node_normalmap.scale_in].default_value = 1.0

        node_imagemap = tree.nodes.new(type='rpr_texture_node_image_map')
        image = bpy_extras.image_utils.load_image(testdata.get_path('../data/material_normalmap_normals.png'))

        if is_blender_support_new_image_node():
            node_imagemap.image = image
        else:
            node_imagemap.image_name = image.name

        tree.links.new(node_imagemap.outputs[node_imagemap.value_out], node_normalmap.inputs[node_normalmap.map_in])


def test_shader_node_uber(render_image_check_fixture, material_setup, request, tmpdir_factory):
    add_emissive_object(material_setup).scale = (2.0, 0.5, 0.5)

    # check defaults params
    with render_image_check_fixture.set_expected('uber/uber_default_expected'):
        generate_uv()
        tree = material_setup.create_default_node_tree()
        output = material_setup.get_node_tree_output(tree)
        uber = tree.nodes.new(type='rpr_shader_node_uber')
        tree.links.new(uber.outputs[uber.shader_out], output.inputs[output.shader_in])

    # check diffuse and transparent only
    with render_image_check_fixture.set_expected('uber/uber_with_normals_expected'):
        uber.inputs[uber.diffuse_color_in].default_value = (0.1, 0.1, 1.0, 1)
        uber.inputs[uber.transparency_color_in].default_value = (0.1, 1.0, 0.1, 1)
        uber.inputs[uber.transparency_level_in].default_value = 0.3
        node_normalmap = create_normalmap(tree)
        tree.links.new(node_normalmap.outputs[node_normalmap.value_out], uber.inputs[uber.diffuse_normal_in])

    # REFLECTION
    with render_image_check_fixture.set_expected('uber/uber_reflection_ior_10_expected'):
        uber.reflection = True
        uber.inputs[uber.reflect_ior_in].default_value = 10
        uber.inputs[uber.reflect_roughness_x_in].default_value = 0
        uber.inputs[uber.reflect_roughness_y_in].default_value = 0
        add_ibl(tmpdir_factory)
        uber.inputs[uber.transparency_level_in].default_value = 0

        node_reflection_normal = create_normalmap(tree, 0.3)
        tree.links.new(node_reflection_normal.outputs[node_reflection_normal.value_out],
                       uber.inputs[uber.reflect_normal_in])

    # RPR has a problem if roughness_y == 0 and roughness_x > 0
    with render_image_check_fixture.set_expected('uber/uber_reflection_roughness_x_0.5_expected'):
        uber.inputs[uber.reflect_roughness_x_in].default_value = 0.5
        uber.inputs[uber.reflect_roughness_y_in].default_value = 0

    with render_image_check_fixture.set_expected('uber/uber_reflection_roughness_y_0.5_expected'):
        uber.inputs[uber.reflect_roughness_x_in].default_value = 0
        uber.inputs[uber.reflect_roughness_y_in].default_value = 0.5

    with render_image_check_fixture.set_expected('uber/uber_reflection_roughness_xy_0.5_expected'):
        uber.inputs[uber.reflect_roughness_x_in].default_value = 0.5
        uber.inputs[uber.reflect_roughness_y_in].default_value = 0.5

    with render_image_check_fixture.set_expected('uber/uber_reflection_ior_1_expected'):
        uber.inputs[uber.reflect_ior_in].default_value = 1

    # CLEAR COAT
    with render_image_check_fixture.set_expected('uber/uber_clear_coat_ior_10_expected'):
        uber.reflection = False
        uber.clear_coat = True
        uber.inputs[uber.coat_ior_in].default_value = 10
        uber.inputs[uber.coat_color_in].default_value = (0.3, 1.0, 0.3, 1)

        node_clear_coat_normal = create_normalmap(tree, 0.3)
        tree.links.new(node_clear_coat_normal.outputs[node_clear_coat_normal.value_out],
                       uber.inputs[uber.coat_normal_in])

    with render_image_check_fixture.set_expected('uber/uber_clear_coat_ior_1_expected'):
        uber.inputs[uber.coat_ior_in].default_value = 1

    # REFRACTION
    bpy.context.scene.rpr.render.rendering_limits.iterations = 200

    with render_image_check_fixture.set_expected('uber/uber_refraction_expected'):
        uber.clear_coat = False
        uber.refraction = True
        uber.inputs[uber.refraction_level_in].default_value = 0.6

    with render_image_check_fixture.set_expected('uber/uber_refraction_ior_10_expected'):
        uber.inputs[uber.refraction_ior_in].default_value = 10

    with render_image_check_fixture.set_expected('uber/uber_refraction_ior_10_normal_expected'):
        node_refraction_normal = create_normalmap(tree, 0.4)
        tree.links.new(node_clear_coat_normal.outputs[node_refraction_normal.value_out],
                       uber.inputs[uber.refraction_normal_in])

    with render_image_check_fixture.set_expected('uber/uber_refraction_roughness_expected'):
        uber.inputs[uber.refraction_roughness_in].default_value = 0.04


def test_shader_node_uber2(render_image_check_fixture, material_setup, request, tmpdir_factory):
    add_emissive_object(material_setup).scale = (2.0, 0.5, 0.5)

    add_ibl(tmpdir_factory)

    generate_uv()
    tree = material_setup.create_default_node_tree()
    output = material_setup.get_node_tree_output(tree)
    uber2 = tree.nodes.new(type='rpr_shader_node_uber2')
    tree.links.new(uber2.outputs[uber2.shader_out], output.inputs[output.shader_in])

    uber2.normal = True  # enable normal first to be able to link socket
    normal_map = create_normalmap(tree)
    normal_map_0_3 = create_normalmap(tree, 0.3)
    tree.links.new(normal_map_0_3.outputs[normal_map_0_3.value_out],uber2.inputs[uber2.normal_in])
    assert uber2.inputs[uber2.normal_in].is_linked and len(uber2.inputs[uber2.normal_in].links) > 0

    # check defaults params
    with render_image_check_fixture.set_expected('uber2/uber2_default_expected'):
        uber2.coating = False
        uber2.diffuse = True
        uber2.emissive = False
        uber2.normal = False
        uber2.reflection = False
        uber2.refraction = False
        uber2.subsurface = False
        uber2.transparency = False

        uber2.inputs[uber2.diffuse_color].default_value = (0.63, 0.63, 0.63, 1.0)

    # check diffuse and transparent only
    with render_image_check_fixture.set_expected('uber2/uber2_with_normals_expected'):
        uber2.coating = False
        uber2.diffuse = True
        uber2.emissive = False
        uber2.normal = True
        uber2.reflection = False
        uber2.refraction = False
        uber2.subsurface = False
        uber2.transparency = True

        uber2.inputs[uber2.diffuse_weight].default_value = 1
        uber2.inputs[uber2.diffuse_roughness].default_value = 1

        uber2.inputs[uber2.transparency_value].default_value = 0.1

        uber2.inputs[uber2.diffuse_color].default_value = (0.63, 0.63, 0.63, 1.0)
        # tree.links.new(normal_map.outputs[normal_map.value_out], uber2.inputs[uber2.diffuse_color])

    # REFLECTION
    with render_image_check_fixture.set_expected('uber2/uber2_reflection_ior_0_2_expected'):
        uber2.coating = False
        uber2.diffuse = True
        uber2.emissive = False
        uber2.normal = True
        uber2.reflection = True
        uber2.refraction = False
        uber2.subsurface = False
        uber2.transparency = False

        tree.links.new(normal_map_0_3.outputs[normal_map_0_3.value_out], uber2.inputs[uber2.reflection_color])
        uber2.inputs[uber2.reflection_weight].default_value = 1
        uber2.inputs[uber2.reflection_roughness].default_value = 1

        uber2.reflection_fresnel_metalmaterial = False
        uber2.inputs[uber2.reflection_ior].default_value = 0.2

    with render_image_check_fixture.set_expected('uber2/uber2_reflection_ior_0_1_expected'):
        uber2.coating = False
        uber2.diffuse = True
        uber2.emissive = False
        uber2.normal = True
        uber2.reflection = True
        uber2.refraction = False
        uber2.subsurface = False
        uber2.transparency = False

        tree.links.new(normal_map_0_3.outputs[normal_map_0_3.value_out], uber2.inputs[uber2.reflection_color])
        uber2.inputs[uber2.reflection_weight].default_value = 1
        uber2.inputs[uber2.reflection_roughness].default_value = 1

        uber2.reflection_fresnel_metalmaterial = False
        uber2.inputs[uber2.reflection_ior].default_value = 0.1

    with render_image_check_fixture.set_expected('uber2/uber2_reflection_ior_2_expected'):
        uber2.coating = False
        uber2.diffuse = True
        uber2.emissive = False
        uber2.normal = True
        uber2.reflection = True
        uber2.refraction = False
        uber2.subsurface = False
        uber2.transparency = False

        tree.links.new(normal_map_0_3.outputs[normal_map_0_3.value_out], uber2.inputs[uber2.reflection_color])
        uber2.inputs[uber2.reflection_weight].default_value = 1
        uber2.inputs[uber2.reflection_roughness].default_value = 1

        uber2.reflection_fresnel_metalmaterial = False
        uber2.inputs[uber2.reflection_ior].default_value = 2

    # CLEAR COAT
    with render_image_check_fixture.set_expected('uber2/uber2_clear_coat_ior_0_1_expected'):
        uber2.coating = True
        uber2.diffuse = True
        uber2.emissive = False
        uber2.normal = True
        uber2.reflection = False
        uber2.refraction = False
        uber2.subsurface = False
        uber2.transparency = False

        uber2.inputs[uber2.coating_color].default_value = (0.3, 1.0, 0.3, 1)
        uber2.inputs[uber2.coating_weight].default_value = 1
        uber2.inputs[uber2.coating_roughness].default_value = 1

        uber2.coating_fresnel_metal_material = False
        uber2.inputs[uber2.coating_ior].default_value = 0.1

    with render_image_check_fixture.set_expected('uber2/uber2_clear_coat_ior_0_2_expected'):
        uber2.coating = True
        uber2.diffuse = True
        uber2.emissive = False
        uber2.normal = True
        uber2.reflection = False
        uber2.refraction = False
        uber2.subsurface = False
        uber2.transparency = False

        uber2.inputs[uber2.coating_color].default_value = (0.3, 1.0, 0.3, 1)
        uber2.inputs[uber2.coating_weight].default_value = 1
        uber2.inputs[uber2.coating_roughness].default_value = 1

        uber2.coating_fresnel_metal_material = False
        uber2.inputs[uber2.coating_ior].default_value = 0.2

    with render_image_check_fixture.set_expected('uber2/uber2_clear_coat_ior_2_expected'):
        uber2.coating = True
        uber2.diffuse = True
        uber2.emissive = False
        uber2.normal = True
        uber2.reflection = False
        uber2.refraction = False
        uber2.subsurface = False
        uber2.transparency = False

        uber2.inputs[uber2.coating_color].default_value = (0.3, 1.0, 0.3, 1)
        uber2.inputs[uber2.coating_weight].default_value = 1
        uber2.inputs[uber2.coating_roughness].default_value = 1

        uber2.coating_fresnel_metal_material = False
        uber2.inputs[uber2.coating_ior].default_value = 2


    # REFRACTION
    with render_image_check_fixture.set_expected('uber2/uber2_refraction_ior_0_1_expected'):
        uber2.coating = False
        uber2.diffuse = True
        uber2.emissive = False
        uber2.normal = True
        uber2.reflection = False
        uber2.refraction = True
        uber2.subsurface = False
        uber2.transparency = False

        tree.links.new(normal_map_0_3.outputs[normal_map_0_3.value_out], uber2.inputs[uber2.refraction_color])
        uber2.inputs[uber2.refraction_weight].default_value = 1
        uber2.inputs[uber2.refraction_roughness].default_value = 1
        uber2.inputs[uber2.refraction_ior].default_value = 0.1

    with render_image_check_fixture.set_expected('uber2/uber2_refraction_ior_0_2_expected'):
        uber2.coating = False
        uber2.diffuse = True
        uber2.emissive = False
        uber2.normal = True
        uber2.reflection = False
        uber2.refraction = True
        uber2.subsurface = False
        uber2.transparency = False

        tree.links.new(normal_map_0_3.outputs[normal_map_0_3.value_out], uber2.inputs[uber2.refraction_color])
        uber2.inputs[uber2.refraction_weight].default_value = 1
        uber2.inputs[uber2.refraction_roughness].default_value = 1
        uber2.inputs[uber2.refraction_ior].default_value = 0.2

    with render_image_check_fixture.set_expected('uber2/uber2_refraction_ior_2_expected'):
        uber2.coating = False
        uber2.diffuse = True
        uber2.emissive = False
        uber2.normal = True
        uber2.reflection = False
        uber2.refraction = True
        uber2.subsurface = False
        uber2.transparency = False

        tree.links.new(normal_map_0_3.outputs[normal_map_0_3.value_out], uber2.inputs[uber2.refraction_color])
        uber2.inputs[uber2.refraction_weight].default_value = 1
        uber2.inputs[uber2.refraction_roughness].default_value = 1
        uber2.inputs[uber2.refraction_ior].default_value = 2


    # EMISSIVE
    with render_image_check_fixture.set_expected('uber2/uber2_emissive_expected'):
        uber2.coating = False
        uber2.diffuse = True
        uber2.emissive = True
        uber2.normal = True
        uber2.reflection = False
        uber2.refraction = False
        uber2.subsurface = False
        uber2.transparency = False

        uber2.inputs[uber2.emissive_color].default_value = (0, 0, 1, 1)


    # SUBSURFACE
    # TODO: REGENERATE ONCE CORE BUGS HAVE BEEN FIXED
    with render_image_check_fixture.set_expected('uber2/uber2_basic_sss_expected'):
        uber2.coating = False
        uber2.diffuse = False
        uber2.emissive = False
        uber2.normal = True
        uber2.reflection = False
        uber2.refraction = False
        uber2.subsurface = True
        uber2.transparency = False

        uber2.inputs[uber2.subsurface_color].default_value = (1, 0, 0, 1)
        uber2.inputs[uber2.subsurface_volume_transmission].default_value = (0, 1, 0, 1)
        uber2.inputs[uber2.subsurface_volume_scatter].default_value = (0, 0, 1, 1)

def test_node_value_blend(render_image_check_fixture):
    with render_image_check_fixture.set_expected('node_value_blend_expected'):
        # generate simple uvs
        generate_uv()

        #
        # setup material graph
        #

        mesh = bpy.context.object.data  # type: bpy.types.Mesh
        material = mesh.materials[0]

        # create material nodetree and retrieve it
        override = bpy.context.copy()
        override['material'] = material
        bpy.ops.rpr.op_material_add_nodetree(override)
        tree = material.node_tree
        output = node_editor.find_node_in_nodetree(tree, node_editor.shader_node_output_name)
        # this should be diffuse
        surface_material = output.inputs[output.shader_in].links[0].from_node

        # create Normal Map node and connect it to Diffuse material Normal input
        editor = MaterialEditor(tree)
        blend_node = editor.create_blend_value_node()

        editor.link_nodes(blend_node,
                          material_editor.DiffuseMaterial(surface_material, editor).get_input_socket_by_name('color'))

        blend_node.set_input_socket_value_by_name('value1', (1, 0, 0, 1))
        blend_node.set_input_socket_value_by_name('value2', (0, 1, 0, 1))
        blend_node.set_input_socket_value_by_name('weight', 0.3)


math_operations = ['ADD', 'SUB', 'MUL', 'SIN', 'COS', 'TAN', 'COS', 'ASIN', 'ACOS', 'ATAN',
                   'DOT3', 'DOT4', 'CROSS3', 'LENGTH3', 'NORMALIZE3', 'POW', 'MIN', 'MAX', 'FLOOR',
                   'MOD', 'SELECT_X', 'SELECT_Y', 'SELECT_Z', 'SELECT_W', 'COMBINE', 'AVERAGE_XYZ', 'AVERAGE',
                   'DIV']


@pytest.mark.parametrize("op", math_operations)
def test_node_math(op, render_image_check_fixture, material_setup, request, tmpdir_factory):
    # generate simple uvs
    generate_uv()

    # setup material graph
    mesh = bpy.context.object.data  # type: bpy.types.Mesh
    material = mesh.materials[0]

    # create material nodetree and retrieve it
    override = bpy.context.copy()
    override['material'] = material
    bpy.ops.rpr.op_material_add_nodetree(override)
    tree = material.node_tree

    editor = MaterialEditor(tree)

    output = node_editor.find_node_in_nodetree(tree, node_editor.shader_node_output_name)
    # this should be diffuse
    surface_material = material_editor.DiffuseMaterial(output.inputs[output.shader_in].links[0].from_node, editor)

    # create Normal Map node and connect it to Diffuse material Normal input
    math_node = editor.create_math_node()
    editor.link_nodes(math_node, surface_material.get_input_color_socket())
    math_node.node.type = 'vector'  # need 4 component for DOT4 and SELECT_W
    math_node.set_operand_value(0, (0.5, 0, 1, 0.75))
    math_node.set_operand_value(1, (0.5, 0, 0.75, 0.20))
    math_node.set_operand_value(2, (0, 0.5, 0.5, 0))

    # without arithmetics node
    img_name = 'node_math/' + op.lower() + '_expected'
    with render_image_check_fixture.set_expected(img_name):
        math_node.op = op
    # check value - parse_arithmetics_node_math

    # with clamp
    img_name = 'node_math/' + op.lower() + '_with_clamp'
    with render_image_check_fixture.set_expected(img_name):
        math_node.node.use_clamp = True

    math_node.node.use_clamp = False

    # with arithmetics node
    node1 = editor.create_image_texture_node()
    blender_image = create_striped_gradients_image_packed(256, 256)
    # blender_image = create_striped_gradients_image(tmpdir_factory)
    node1.set_image(blender_image)

    node2 = editor.create_input_constant_node()
    # node2.node.color = (1, 0.2, 0 if op != 'DIV' else 0.5, 1.0)
    # TODO: initial tests were wrongly using default_value on constant color node(should be color instead)
    # to that actual second param was 1s
    node2.node.color = (1,) * 4 if op != 'DIV' else (1, 0.2, 0.5, 0.75)

    editor.link_nodes(node1, math_node.get_input_operand_socket(0))
    editor.link_nodes(node2, math_node.get_input_operand_socket(1))

    img_name = 'node_math/' + op.lower() + '_with_node_expected'
    with render_image_check_fixture.set_expected(img_name):
        math_node.op = op


def test_node_reroute(render_image_check_fixture, material_setup, request, tmpdir_factory):
    with render_image_check_fixture.set_expected('node_reroute_expected'):
        generate_uv()

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)
        testee = editor.create_blend_material_node()
        editor.link_nodes(testee, output.get_input_shader_socket())

        a = editor.create_diffuse_material_node()
        a.set_input_socket_value_by_name('color', (1, 1, 0, 1))
        editor.link_nodes(a, testee.get_input_socket_by_name('shader1'))

        b = editor.create_microfacet_material_node()
        b.set_input_socket_value_by_name('color', (0, 0, 1, 1))
        editor.link_nodes(b, testee.get_input_socket_by_name('shader2'))

        testee.set_input_socket_value_by_name('weight', 0.25)

        reroute = editor.tree.nodes.new(type='NodeReroute')

        color1 = a.get_input_socket_by_name('color')
        editor.tree.links.new(reroute.outputs[0], color1)
        color2 = b.get_input_socket_by_name('color')
        editor.tree.links.new(reroute.outputs[0], color2)

        input_color = editor.create_input_constant_node()
        input_color.node.color = (1, 0.5, 0.25, 1)
        input_color.link_to(reroute.inputs[0])


def test_tonemapping_and_white_balance(render_image_check_fixture, material_setup, request, tmpdir_factory):
    bpy.ops.mesh.primitive_ico_sphere_add()
    bpy.context.object.location = (1, 0, -1)
    bpy.context.object.scale = (1.5,) * 3

    tm = bpy.context.scene.rpr.render.tone_mapping
    tm.enable = True
    tm.type = 'simplified'

    wb = bpy.context.scene.rpr.render.white_balance

    print('check: simplified default settings')
    with render_image_check_fixture.set_expected('tonemapping/tonemapping_simplified_default_expected'):
        pass

    print('check: simplified 10000K whitebalance')
    with render_image_check_fixture.set_expected('tonemapping/tonemapping_simplified_10000K_expected'):
        wb.enable = True
        wb.color_temperature = 10000

    print('check: simplified 2700K whitebalance')
    with render_image_check_fixture.set_expected('tonemapping/tonemapping_simplified_2700K_expected'):
        wb.color_temperature = 2700

    print('check: whitebalance off')
    with render_image_check_fixture.set_expected('tonemapping/tonemapping_simplified_default_expected'):
        wb.enable = False

    print('check: linear')
    with render_image_check_fixture.set_expected('tonemapping/tonemapping_linear_expected'):
        tm.type = 'linear'

    print('check: nonlinear')
    with render_image_check_fixture.set_expected('tonemapping/tonemapping_nonlinear_expected'):
        tm.type = 'non_linear'


def test_dof(render_image_check_fixture, material_setup, request, tmpdir_factory):
    render_image_check_fixture.viewport_fixture.render_resolution = (640, 480)
    bpy.context.scene.rpr.render.rendering_limits.iterations = 200

    scene_file_name = testdata.get_path('../data/dof.blend')
    bpy.ops.wm.open_mainfile(filepath=scene_file_name)
    dof = bpy.context.scene.rpr.render.dof
    camera = bpy.context.scene.camera.data

    with render_image_check_fixture.set_expected('dof/dof_camera_object_expected'):
        assert camera.dof_object
        dof.enable = True

    with render_image_check_fixture.set_expected('dof/dof_camera_distance_expected'):
        camera.dof_object = None
        camera.dof_distance = 15.0

    with render_image_check_fixture.set_expected('dof/dof_camera_fstop_4_expected'):
        camera.gpu_dof.fstop = 0.04

    with render_image_check_fixture.set_expected('dof/dof_camera_fstop_12_expected'):
        camera.gpu_dof.fstop = 0.12

    with render_image_check_fixture.set_expected('dof/dof_off_expected'):
        dof.enable = False


class TestMaterialSync:
    def set_diffuse_color(self, color, output):
        surface_material = output.inputs[output.shader_in].links[0].from_node
        surface_material.inputs[surface_material.color_in].default_value = color
        return surface_material

    def test_link_change(self, render_image_check_fixture: RenderImageCheck, sync_fixture, material_setup):
        with render_image_check_fixture.set_expected(None):
            # generate simple uvs
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.uv.unwrap()
            bpy.ops.object.mode_set(mode='OBJECT')

            tree = material_setup.create_default_node_tree()
            output = material_setup.get_node_tree_output(tree)

            # this should be diffuse
            surface_material = output.inputs[output.shader_in].links[0].from_node

            # create checker node without connecting
            node_checker = tree.nodes.new(type='rpr_texture_node_checker')

            if 0x010000236 >= pyrpr.API_VERSION:
                node_mapping = tree.nodes.new(type='rpr_mapping_node')
                tree.links.new(node_mapping.outputs[node_mapping.value_out],
                               node_checker.inputs[node_checker.mapping_in])
                node_mapping.inputs[node_mapping.scale_in].default_value = (8, 8)

        # just sync once
        with render_image_check_fixture.set_expected_synced(None):
            pass

        with render_image_check_fixture.set_expected_synced('material_checker_expected'):
            tree.links.new(node_checker.outputs[node_checker.value_out],
                           surface_material.inputs[surface_material.color_in])
            # NOTE: seems like simply connecting two sockets with links.new doesn't tag material update
            material_setup.get_active_material().update_tag()

    def test_two_meshes_separate_materials(self, render_image_check_fixture: RenderImageCheck, sync_fixture,
                                           material_setup):
        with render_image_check_fixture.set_expected('material_sync_two_meshes_separate_materials_expected'):
            bpy.context.object.location = (-1, 0, 0)
            tree = material_setup.create_default_node_tree()
            output = material_setup.get_node_tree_output(tree)
            self.set_diffuse_color((1, 0, 0, 1), output)

            bpy.ops.mesh.primitive_cube_add()
            bpy.context.object.location = (1, 0, 0)

            # create default material
            material = bpy.data.materials.new('Material 2')
            mesh = bpy.context.object.data
            mesh.materials.append(material)

            tree = material_setup.create_default_node_tree()
            output = material_setup.get_node_tree_output(tree)
            self.set_diffuse_color((0, 1, 0, 1), output)

        # change color back and sync
        with render_image_check_fixture.set_expected_synced(
            'material_sync_two_meshes_separate_materials_changed_expected'):
            self.set_diffuse_color((0, 0, 1, 1), output)
            material.update_tag()

    def test_one_material_on_two_meshes(self, render_image_check_fixture: RenderImageCheck, sync_fixture,
                                        material_setup):
        with render_image_check_fixture.set_expected('material_sync_one_material_on_two_meshes_expected'):
            bpy.context.object.location = (-1, 0, 0)
            bpy.ops.object.duplicate(linked=True)
            bpy.context.object.location = (1, 0, 0)

            tree = material_setup.create_default_node_tree()
            output = material_setup.get_node_tree_output(tree)

            material = material_setup.material

            self.set_diffuse_color((1, 0, 0, 1), output)

        # change color and re-render
        with render_image_check_fixture.set_expected('material_sync_one_material_on_two_meshes_changed_expected'):
            self.set_diffuse_color((0, 1, 0, 1), output)
            material.update_tag()

        # change color back and sync
        with render_image_check_fixture.set_expected_synced('material_sync_one_material_on_two_meshes_expected'):
            self.set_diffuse_color((1, 0, 0, 1), output)
            material.update_tag()

    def make_simple_material(self):
        mesh = bpy.context.object.data
        material = bpy.data.materials.new(name='Iron')
        return material

    def test_two_materials_on_one_mesh(self, render_image_check_fixture: RenderImageCheck, material_setup):
        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
        rpr_settings_env = bpy.context.scene.world.rpr_data.environment
        rpr_settings_env.ibl.color = (0.5,) * 3

        bpy.context.object.data.materials[0] = self.make_simple_material()
        assert 1 == len(bpy.context.object.data.materials)
        bpy.context.object.data.materials.append(self.make_simple_material())
        assert 2 == len(bpy.context.object.data.materials)

        self.set_diffuse_color(
            (0, 1, 0, 1),
            material_setup.get_node_tree_output(
                material_setup.create_default_node_tree(bpy.context.object.data.materials[0])))

        self.set_diffuse_color(
            (1, 0, 0, 1),
            material_setup.get_node_tree_output(
                material_setup.create_default_node_tree(bpy.context.object.data.materials[1])))

        bpy.context.object.data.polygons[0].material_index = 1

        with render_image_check_fixture.set_expected('material_sync/two_materials_on_one_mesh/first_material'):
            pass

        with render_image_check_fixture.set_expected('material_sync/two_materials_on_one_mesh/second_material'):
            bpy.context.object.rotation_euler = (3.142, 0, 0)

        with render_image_check_fixture.set_expected('material_sync/two_materials_on_one_mesh/both_materials'):
            bpy.context.object.rotation_euler = (3.142 * 0.75, 0, 0)

    def test_linked_duplicate_should_keep_same_material(self, render_image_check_fixture: RenderImageCheck,
                                                        sync_fixture, material_setup):
        with render_image_check_fixture.set_expected(None):
            tree = material_setup.create_default_node_tree()
            output = material_setup.get_node_tree_output(tree)
            self.set_diffuse_color((1, 0, 0, 1), output)
            bpy.context.object.location = (-1, 0, 0)

        # duplicate object
        with render_image_check_fixture.set_expected_synced('material_sync_one_material_on_two_meshes_expected'):
            bpy.ops.object.duplicate(linked=True)
            bpy.context.object.location = (1, 0, 0)

    def test_regular_duplicate_should_keep_same_material(self, render_image_check_fixture: RenderImageCheck,
                                                         sync_fixture, material_setup):
        with render_image_check_fixture.set_expected(None):
            tree = material_setup.create_default_node_tree()
            output = material_setup.get_node_tree_output(tree)
            self.set_diffuse_color((1, 0, 0, 1), output)
            bpy.context.object.location = (-1, 0, 0)

        # duplicate object
        with render_image_check_fixture.set_expected_synced('material_sync_one_material_on_two_meshes_expected'):
            bpy.ops.object.duplicate(linked=False)
            bpy.context.object.location = (1, 0, 0)

    @pytest.mark.skip(reason="fails because we use custom nodetree and it's not duplicated on 'make single user'")
    def test_regular_duplicate_make_single_use_for_material_should_make_separate_material(self,
                                                                                          render_image_check_fixture: RenderImageCheck,
                                                                                          material_setup):
        with render_image_check_fixture.set_expected(None):
            tree = material_setup.create_default_node_tree()
            output = material_setup.get_node_tree_output(tree)
            self.set_diffuse_color((1, 0, 0, 1), output)
            bpy.context.object.location = (-1, 0, 0)

        # duplicate object
        with render_image_check_fixture.set_expected_synced('material_sync_two_meshes_separate_materials_expected'):
            bpy.ops.object.duplicate(linked=False)
            bpy.context.object.location = (1, 0, 0)

            bpy.ops.object.make_single_user(object=False, obdata=False, material=True, texture=True, animation=False)

            mesh = bpy.context.object.data
            material = mesh.materials[0]
            output = material_setup.get_node_tree_output(material.node_tree)

            self.set_diffuse_color((0, 1, 0, 1), output)

    def test_group_instance(self, render_image_check_fixture, material_setup):
        # create instance and expect it to have same material as the prototype
        with render_image_check_fixture.set_expected('material_sync_one_material_on_two_meshes_expected'):
            tree = material_setup.create_default_node_tree()
            output = material_setup.get_node_tree_output(tree)

            self.set_diffuse_color((1, 0, 0, 1), output)

            # create instance
            bpy.context.object.location = (-1, 0, 0)
            bpy.ops.group.create()
            bpy.ops.object.group_instance_add()
            bpy.context.object.location = (2, 0, 0)

        with render_image_check_fixture.set_expected('material_sync_one_material_on_two_meshes_changed_expected'):
            self.set_diffuse_color((0, 1, 0, 1), output)
            material_setup.material.update_tag()

        with render_image_check_fixture.set_expected_synced('material_sync_one_material_on_two_meshes_expected'):
            self.set_diffuse_color((1, 0, 0, 1), output)
            material_setup.material.update_tag()

    def test_group_instance_add_sync(self, render_image_check_fixture, material_setup):
        with render_image_check_fixture.set_expected(None):
            tree = material_setup.create_default_node_tree()
            output = material_setup.get_node_tree_output(tree)

            self.set_diffuse_color((1, 0, 0, 1), output)

        # add instance and expect it to have same material as the prototype
        with render_image_check_fixture.set_expected_synced('material_sync_one_material_on_two_meshes_expected'):
            # create instance
            bpy.context.object.location = (-1, 0, 0)
            bpy.ops.group.create()
            bpy.ops.object.group_instance_add()
            bpy.context.object.location = (2, 0, 0)

    def test_group_instance_from_invisible_layer_add_sync(self, render_image_check_fixture, material_setup):
        with render_image_check_fixture.set_expected(None):
            tree = material_setup.create_default_node_tree()
            output = material_setup.get_node_tree_output(tree)

            self.set_diffuse_color((1, 0, 0, 1), output)

        # add instance and expect it to have same material as the prototype
        with render_image_check_fixture.set_expected_synced('material_sync_one_material_on_two_meshes_expected'):
            # create instance
            bpy.context.object.location = (-1, 0, 0)
            bpy.ops.group.create()
            bpy.ops.object.group_instance_add()
            bpy.context.object.location = (2, 0, 0)


@pytest.mark.skipif(condition=not pytest.config.option.perf, reason="perf")
def test_viewport_sync_perf_multiple_objects(viewport_fixture, sync_fixture):
    bpy.context.object.location = (0, 1, 0)

    bpy.ops.group.create()
    bpy.ops.object.group_instance_add(
        group='Group',
        location=(2, 0, 0))
    bpy.context.object.name = 'B'

    with TimedContext("make  duplicators"):
        count = 1000
        for i in range(count):
            bpy.ops.object.group_instance_add(location=(i % 10, (i // 10) % 10, i // 100))

    bpy.context.scene.update()

    with viewport_fixture:
        sync_fixture.set_sync(viewport_fixture.update)

        with sync_fixture:
            time_start = time.perf_counter()

            bpy.context.object.location = (1, 1, 0)
            bpy.context.scene.update()
            viewport_fixture.wait_for_render_complete()

            log(time.perf_counter() - time_start)

        im = viewport_fixture.viewport_renderer.get_image()
        assert im is not None


def set_ibl_image(ibl, path):
    if versions.is_blender_support_ibl_image():
        try:
            ibl.ibl_image = bpy.data.images.load(path, True)
        except RuntimeError:
            ibl.ibl_image = None
    else:
        ibl.ibl_map = path


def set_background_image(ibl, path):
    if versions.is_blender_support_ibl_image():
        try:
            ibl.maps.background_image = bpy.data.images.load(path, True)
        except RuntimeError:
            ibl.maps.background_image = None
    else:
        ibl.maps.background_map = path


class TestEnvironmentLight:
    def set_diffuse_color(self, color, output):
        surface_material = output.inputs[output.shader_in].links[0].from_node
        surface_material.inputs[surface_material.color_in].default_value = color
        return surface_material

    def test_simple(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        path = str(tmpdir_factory.mktemp('data').join('ibl.png'))
        image = create_striped_sky_image(path)

        bpy.context.scene.camera.location = (0, 0, 16)

        tree = material_setup.create_default_node_tree()
        output = material_setup.get_node_tree_output(tree)
        # self.set_diffuse_color((0, 0, 0, 1), output)

        # XXX: offset needed as RPR renders negative pixels along the envmap stitch
        # see AMDBLENDER-103
        log("render ibl")
        environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment

        log("test no map set gives error")
        with render_image_check_fixture.set_expected('environment_light/error_expected'):
            environment.enable = True
            environment.ibl.use_ibl_map = True
            environment.type = 'IBL'

        log("test sync map set after it was not")
        with render_image_check_fixture.set_expected_synced('environment_light/simple_expected'):
            set_ibl_image(environment.ibl, path)

        log("test environment disable")
        with render_image_check_fixture.set_expected('environment_light/off_expected'):
            environment.enable = False

        environment.enable = True

        log("test default color")
        with render_image_check_fixture.set_expected_synced('environment_light/color_expected'):
            environment.ibl.color = (0, 1, 1)
            environment.ibl.use_ibl_map = False

        log("test color sync")
        with render_image_check_fixture.set_expected_synced('environment_light/color_changed_expected'):
            environment.ibl.color = (1, 1, 0)
            environment.ibl.use_ibl_map = False

        log("not a file image")
        with render_image_check_fixture.set_expected('environment_light/error_expected'):
            environment.ibl.use_ibl_map = True

            missing_path = str(tmpdir_factory.mktemp('textures').join('missing_image_texture.png'))

            image = bpy.data.images.new("rpr_striped_gradients", width=32, height=32)
            image.pixels = []  # emulate missing image load
            image.filepath_raw = missing_path

            # TODO: simulate missing file with bpy.ops.wm.save_mainfile(filepath=)
            set_ibl_image(environment.ibl, missing_path)

        log("test map removed while ibl enabled")
        with render_image_check_fixture.set_expected('environment_light/simple_expected'):
            set_ibl_image(environment.ibl, path)

        log("test intensity")
        with render_image_check_fixture.set_expected('environment_light/intens_x2_expected'):
            environment.ibl.intensity = 2.0

        log("test environment off sync")
        with render_image_check_fixture.set_expected_synced('environment_light/off_expected'):
            environment.enable = False

        log("test rotation")
        with render_image_check_fixture.set_expected('environment_light/rotation_expected'):
            environment.enable = True
            environment.ibl.intensity = 1.0
            environment.gizmo_rotation = (3.142 / 4, 3.142 / 8, 3.142 / 16)

    def _test_simplest(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        render_image_check_fixture.viewport_fixture.render_resolution = (32, 32)

        path = str(tmpdir_factory.mktemp('data').join('ibl.png'))
        image = create_striped_sky_image(path)

        tree = material_setup.create_default_node_tree()
        output = material_setup.get_node_tree_output(tree)
        # self.set_diffuse_color((0, 0, 0, 1), output)

        # XXX: offset needed as RPR renders negative pixels along the envmap stitch
        # see AMDBLENDER-103
        log("render ibl")
        with render_image_check_fixture.set_expected('environment_light/simplest/expected'):
            bpy.context.scene.camera.location = (0, 0, 16)

            bpy.context.scene.world.rpr_data.environment.enable = True
            bpy.context.scene.world.rpr_data.environment.type = 'IBL'
            bpy.context.scene.world.rpr_data.environment.ibl.use_ibl_map = True
            bpy.context.scene.world.rpr_data.environment.ibl.ibl_map = path

        with render_image_check_fixture.set_expected('environment_light/simplest/off_expected'):
            bpy.context.scene.world.rpr_data.environment.enable = False

        with render_image_check_fixture.set_expected('environment_light/simplest/off_expected'):
            bpy.context.scene.world.rpr_data.environment.enable = True
            bpy.context.scene.world.rpr_data.environment.ibl.use_ibl_map = False

        with render_image_check_fixture.set_expected('environment_light/simplest/error_expected'):
            bpy.context.scene.world.rpr_data.environment.ibl.use_ibl_map = True

            bpy.context.scene.world.rpr_data.environment.ibl.ibl_map = 'not here!!!'

        with render_image_check_fixture.set_expected('environment_light/simplest/expected'):
            bpy.context.scene.world.rpr_data.environment.ibl.ibl_map = path

        with render_image_check_fixture.set_expected('environment_light/simplest/intens_x2_expected'):
            bpy.context.scene.world.rpr_data.environment.ibl.intensity = 2.0

    def test_background_simple(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request,
                               material_setup):
        # 1.239 has bug with light from Background - AMDMAX-1060
        render_image_check_fixture.skip_image_comparison = 0x010000239 == pyrpr.API_VERSION

        bpy.context.scene.objects['Lamp'].hide = True

        background_image_path = str(tmpdir_factory.mktemp('data').join('background.png'))
        background_image = create_color_fill_image(background_image_path, (0.0, 1.0, 1.0))

        ibl_image_path = str(tmpdir_factory.mktemp('data').join('ibl.png'))
        ibl_image = create_color_fill_image(ibl_image_path, (1.0, 0.0, 0.0))

        tree = material_setup.create_default_node_tree()
        output = material_setup.get_node_tree_output(tree)
        # self.set_diffuse_color((0, 0, 0, 1), output)

        # XXX: offset needed as RPR renders negative pixels along the envmap stitch
        # see AMDBLENDER-103
        with render_image_check_fixture.set_expected('environment_light/backplate_simple_expected'):
            bpy.context.scene.camera.location = (0, 0, 16)

            bpy.context.scene.world.rpr_data.environment.enable = True
            bpy.context.scene.world.rpr_data.environment.type = 'IBL'
            bpy.context.scene.world.rpr_data.environment.ibl.use_ibl_map = True

            set_ibl_image(bpy.context.scene.world.rpr_data.environment.ibl, ibl_image_path)
            bpy.context.scene.world.rpr_data.environment.ibl.maps.override_background = True
            set_background_image(bpy.context.scene.world.rpr_data.environment.ibl, background_image_path)


    def test_background(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        # 1.239 has bug with light from Background - AMDMAX-1060
        # render_image_check_fixture.skip_image_comparison = 0x010000239 == pyrpr.API_VERSION

        background_image_path = str(tmpdir_factory.mktemp('data').join('background.png'))
        background_image = create_striped_sky_image(background_image_path)

        ibl_image_path = str(tmpdir_factory.mktemp('data').join('ibl.png'))
        ibl_image = create_color_fill_image(ibl_image_path, (1.0, 0.0, 0.0))

        tree = material_setup.create_default_node_tree()
        output = material_setup.get_node_tree_output(tree)
        # self.set_diffuse_color((0, 0, 0, 1), output)

        # XXX: offset needed as RPR renders negative pixels along the envmap stitch
        # see AMDBLENDER-103
        with render_image_check_fixture.set_expected('environment_light/backplate_expected'):
            bpy.context.scene.camera.location = (0, 0, 16)

            bpy.context.scene.world.rpr_data.environment.enable = True
            bpy.context.scene.world.rpr_data.environment.type = 'IBL'
            bpy.context.scene.world.rpr_data.environment.ibl.use_ibl_map = True
            set_ibl_image(bpy.context.scene.world.rpr_data.environment.ibl, ibl_image_path)
            bpy.context.scene.world.rpr_data.environment.ibl.maps.override_background = True
            set_background_image(bpy.context.scene.world.rpr_data.environment.ibl, background_image_path)

        with render_image_check_fixture.set_expected_synced('environment_light/backplate_off_expected'):
            bpy.context.scene.world.rpr_data.environment.ibl.maps.override_background = False

        log('test turning on same background again')
        with render_image_check_fixture.set_expected_synced('environment_light/backplate_expected'):
            bpy.context.scene.world.rpr_data.environment.ibl.maps.override_background = True

        log('test not an image')
        with render_image_check_fixture.set_expected_synced('environment_light/backplate_error_expected'):
            image = bpy.data.images.new("rpr_striped_gradients", width=32, height=32)
            image.filepath_raw = str(tmpdir_factory.mktemp('textures').join('missing_image_texture.png'))

            # TODO: simulate missing file with bpy.ops.wm.save_mainfile(filepath=)
            set_background_image(bpy.context.scene.world.rpr_data.environment.ibl, image.filepath_raw)

        log('color')
        with render_image_check_fixture.set_expected_synced('environment_light/backplate_color'):
            bpy.context.scene.world.rpr_data.environment.ibl.maps.override_background_type = 'color'
            bpy.context.scene.world.rpr_data.environment.ibl.maps.background_color = (1, 1, 0)

        log('color change')
        with render_image_check_fixture.set_expected_synced('environment_light/backplate_color_changed'):
            bpy.context.scene.world.rpr_data.environment.ibl.maps.override_background_type = 'color'
            bpy.context.scene.world.rpr_data.environment.ibl.maps.background_color = (0, 0.5, 1)


class TestLights:
    def test_point(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (0.25, 0.5, 2)

        with render_image_check_fixture.set_expected('lights/point_expected'):
            pass

    def test_spot(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.data.type = 'SPOT'
        lamp_object.location = (0.25, 0.5, 2)
        lamp_object.data.spot_size = 75
        lamp_object.data.spot_blend = 0.75
        set_light_intensity(lamp_object, 40)

        with render_image_check_fixture.set_expected('lights/spot_expected'):
            pass

    def test_sun(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.data.type = 'SUN'
        lamp_object.location = (0.25, 0.5, 2)
        lamp_object.rotation_euler = (-3.142 / 4, 0, 0)
        lamp_object.data.color = (1, 1, 0)
        set_light_intensity(lamp_object, 5)

        with render_image_check_fixture.set_expected('lights/sun_expected.png', scale=0.4):
            pass

    def test_ies(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (0.25, 0.5, 2)
        set_light_intensity(lamp_object, 0.2 * 4 * math.pi)
        lamp_object.data.rpr_lamp.ies_file_name = testdata.get_path('../data/ies_light_example.ies')
        with render_image_check_fixture.set_expected('lights/point_ies_expected'):
            pass

    @pytest.mark.parametrize("n", range(1))
    def test_area(self, n, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        bpy.context.scene.rpr.render.rendering_limits.type = 'ITER'
        # emissive/area lights need a bit more iteration to converge
        bpy.context.scene.rpr.render.rendering_limits.iterations = 200

        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object0 = lamp_object
        lamp_object.location = (0.25, 1.0, 2)
        lamp_object.rotation_euler = (-3.142 / 4, 0, 0)
        lamp_object.data.type = 'AREA'
        lamp_object.data.color = (1, 1, 0)
        set_light_intensity(lamp_object, 3.0)

        log("simple square light")
        with render_image_check_fixture.set_expected('lights/area_expected'):
            lamp_object.data.shape = 'SQUARE'
            lamp_object.data.size = 1

        log("rect light")
        with render_image_check_fixture.set_expected('lights/area_rectangle_expected'):
            lamp_object.location = (0.0, 1.0, 1.25)

            lamp_object.data.shape = 'RECTANGLE'
            lamp_object.data.size = 1.0
            lamp_object.data.size_y = 0.1
            set_light_intensity(lamp_object, 0.5)

        log("add another light")
        with render_image_check_fixture.set_expected_synced('lights/area_two_lights_expected'):
            bpy.ops.object.lamp_add(type='AREA')
            lamp_object = bpy.context.object
            lamp_object1 = lamp_object
            lamp_object.location = (0.0, -1.0, 1.25)
            lamp_object.rotation_euler = (3.142 / 4, 0, 0)
            lamp_object.data.type = 'AREA'
            lamp_object.data.color = (0, 1, 1)

            lamp_object.data.shape = 'RECTANGLE'
            lamp_object.data.size = 1.0
            lamp_object.data.size_y = 0.1
            set_light_intensity(lamp_object, 0.5)

        log("hide light")
        with render_image_check_fixture.set_expected_synced('lights/area_rectangle_expected'):
            lamp_object.hide = True

        log("un-hide light")
        with render_image_check_fixture.set_expected_synced('lights/area_two_lights_expected'):
            lamp_object.hide = False

    def test_area_not_visible_visibility(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request,
                                         material_setup):
        bpy.context.scene.rpr.render.rendering_limits.type = 'ITER'
        # emissive/area lights need a bit more iteration to converge
        bpy.context.scene.rpr.render.rendering_limits.iterations = 50

        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (0.0, 0.0, 1.25)
        lamp_object.rotation_euler = (0, 0, 0)
        lamp_object.data.type = 'AREA'
        lamp_object.data.color = (0.25, 1, 0.5)

        lamp_object.data.shape = 'SQUARE'
        lamp_object.data.size = 0.5
        set_light_intensity(lamp_object, 1.0)

        with render_image_check_fixture.set_expected('lights/area_not_visible_expected'):
            pass

    def test_area_no_shadow(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request,
                            material_setup):
        bpy.context.scene.rpr.render.rendering_limits.type = 'ITER'
        # emissive/area lights need a bit more iteration to converge
        bpy.context.scene.rpr.render.rendering_limits.iterations = 50

        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (0.5, 0.0, 2.0)

        # first, make sure shadows are working
        with render_image_check_fixture.set_expected('lights/area_shadow_expected'):
            bpy.ops.mesh.primitive_plane_add(radius=1)
            plane = bpy.context.object
            plane.location = (0.5, 0.0, 1.5)
            plane.scale = (0.25,) * 3
            plane.rotation_euler = (0, 0, 0)
        plane.hide = True

        # then, check that area light doesn't drop one
        with render_image_check_fixture.set_expected('lights/area_no_shadow_expected'):
            bpy.ops.object.lamp_add(type='AREA')
            lamp_object = bpy.context.object
            lamp_object.location = (0.5, 0.0, 1.5)
            lamp_object.rotation_euler = (0, 0, 0)
            lamp_object.data.type = 'AREA'
            lamp_object.data.color = (0.0, 1, 0.0)

            lamp_object.data.shape = 'SQUARE'
            lamp_object.data.size = 0.5
            set_light_intensity(lamp_object, 0.5)


@pytest.mark.skip(reason="shadowcatcher was disabled since 1.257")
class TestShadowcatcher:
    def test_simple(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        shadowcatcher_obj = bpy.context.object

        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (0.0, 0.0, 2)
        set_light_intensity(lamp_object, 4 * math.pi)

        bpy.ops.mesh.primitive_plane_add(radius=1)
        plane = bpy.context.object
        plane.location = (0.0, 0.0, 1.5)
        plane.scale = (0.25,) * 3
        plane.rotation_euler = (0, 0, 0)

        environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment
        environment.enable = True
        environment.type = 'IBL'
        environment.ibl.use_ibl_map = False
        environment.ibl.color = (0, 1, 1)
        environment.ibl.intensity = 1

        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RPRRenderSettings
        rpr_settings.rendering_limits.iterations = 100

        shadowcatcher_obj.rpr_object.shadowcatcher = True

        with render_image_check_fixture.set_expected('shadowcatcher/expected'):
            pass

        shadowcatcher_obj.rpr_object.shadowcatcher = False

        with render_image_check_fixture.set_expected('shadowcatcher/off_expected'):
            pass

        log("test on sync")
        with render_image_check_fixture.set_expected_synced('shadowcatcher/expected'):
            shadowcatcher_obj.rpr_object.shadowcatcher = True
            shadowcatcher_obj.update_tag()

        log("test off sync")
        with render_image_check_fixture.set_expected_synced('shadowcatcher/off_expected'):
            shadowcatcher_obj.rpr_object.shadowcatcher = False
            shadowcatcher_obj.update_tag()

    def test_blocks_light(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        bpy.ops.object.delete()

        # make shadowcatcher that hides object from light completely
        bpy.ops.mesh.primitive_plane_add(radius=1)
        plane = bpy.context.object
        plane.location = (0.0, 0.0, 0)
        plane.scale = (2, 2, 2)
        plane.rotation_euler = (0, 3.142 / 2, 0)

        shadowcatcher_obj = bpy.context.object

        # make object
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, size=2)
        plane = bpy.context.object
        plane.location = (-2, 0, 0)

        # make light
        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (0.5, 0, 0)
        lamp_object.rotation_euler = (0, 3.142 / 2, 0)
        lamp_object.data.type = 'AREA'
        lamp_object.data.color = (1, 0, 0)
        set_light_intensity(lamp_object, 2.0)
        lamp_object.data.shape = 'SQUARE'
        lamp_object.data.size = 0.5

        environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment
        environment.enable = True
        environment.type = 'IBL'
        environment.ibl.use_ibl_map = False
        environment.ibl.color = (0, 0.5, 0.5)
        environment.ibl.intensity = 1

        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RPRRenderSettings
        rpr_settings.rendering_limits.iterations = 100

        shadowcatcher_obj.rpr_object.shadowcatcher = True

        # make sure shadows flag works in one way first
        with render_image_check_fixture.set_expected('shadowcatcher/blocks_light_disabled'):
            shadowcatcher_obj.rpr_object.shadows = False

        with render_image_check_fixture.set_expected('shadowcatcher/blocks_light'):
            # simulate blocking light by turning it off for old core version with the issue
            # AMDBLENDER-426
            if 0x010000256 >= pyrpr.API_VERSION:
                set_light_intensity(lamp_object, 0)
            shadowcatcher_obj.rpr_object.shadows = True


class TestRenderLayers:

    def test_layer(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request,
                            material_setup):
        bpy.context.scene.rpr.render.rendering_limits.type = 'ITER'
        # emissive/area lights need a bit more iteration to converge
        bpy.context.scene.rpr.render.rendering_limits.iterations = 50

        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (0.5, 0.0, 2.0)

        # first, make sure shadows are working
        with render_image_check_fixture.set_expected('render_layers/layer/shadowcaster_expected'):
            bpy.ops.mesh.primitive_plane_add(radius=1)
            plane = bpy.context.object
            plane.location = (0.5, 0.0, 1.5)
            plane.scale = (0.25,) * 3
            plane.rotation_euler = (0, 0, 0)

        #bpy.context.scene.render.layers.active.layers_exclude[1] = True

        with render_image_check_fixture.set_expected('render_layers/layer/shadowcaster_in_invisible_layer'):
            # move shadowcaster to a separate layer
            bpy.context.object.layers[1] = True
            bpy.context.object.layers[0] = False

        with render_image_check_fixture.set_expected('render_layers/layer/shadowcaster_expected'):
            # enable shadowcaster's layer
            bpy.context.scene.layers[1] = True

        with render_image_check_fixture.set_expected('render_layers/layer/shadowcaster_shadow_but_no_shape'):
            # disable shadowscaster's primary visibility
            bpy.context.scene.render.layers.active.layers[1] = False



class TestPortallight:

    def test_simple(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        portallight_obj = bpy.context.object

        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (0.0, 0.0, 2)
        set_light_intensity(lamp_object, 4 * math.pi)

        bpy.ops.mesh.primitive_plane_add(radius=1)
        plane = bpy.context.object
        plane.location = (0.0, 0.0, 1.5)
        plane.scale = (0.25,) * 3
        plane.rotation_euler = (0, 0, 0)

        environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment
        environment.enable = True
        environment.type = 'IBL'
        environment.ibl.use_ibl_map = False
        environment.ibl.color = (0, 1, 1)
        environment.ibl.intensity = 1

        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RPRRenderSettings
        rpr_settings.rendering_limits.iterations = 100

        portallight_obj.rpr_object.portallight = True

        with render_image_check_fixture.set_expected('portallight/expected'):
            pass

        portallight_obj.rpr_object.portallight = False

        with render_image_check_fixture.set_expected('portallight/off_expected'):
            pass

        log("test on sync")
        with render_image_check_fixture.set_expected_synced('portallight/expected'):
            portallight_obj.rpr_object.portallight = True
            portallight_obj.update_tag()

        log("test off sync")
        with render_image_check_fixture.set_expected_synced('portallight/off_expected'):
            portallight_obj.rpr_object.portallight = False
            portallight_obj.update_tag()


        # seems line in RPR 1.252 background is not visible through invisible portal!
        # so enabling background dosn't make eny difference
        environment.ibl.maps.override_background = True
        environment.ibl.maps.override_background_type = 'color'
        environment.ibl.maps.background_color = (1, 1, 0)

        with render_image_check_fixture.set_expected('portallight/visibility_primary_off_expected'):
            portallight_obj.rpr_object.visibility_in_primary_rays = False
            portallight_obj.rpr_object.portallight = True

    def test_lighting(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):

        bpy.context.object.select = False
        bpy.context.scene.objects['Lamp'].select = True
        bpy.ops.object.delete()

        cube = bpy.context.object

        bpy.ops.mesh.primitive_plane_add(radius=1)
        plane = bpy.context.object
        plane.location = (0.0, 0.0, 1.5)
        plane.scale = (0.25,) * 3
        plane.rotation_euler = (3.14159, 0, 0) # rotate portal to face mesh to light
        portallight_obj = plane

        environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment
        environment.enable = True
        environment.type = 'IBL'
        environment.ibl.use_ibl_map = False
        environment.ibl.color = (0, 1, 1)
        environment.ibl.intensity = 5

        portallight_obj.rpr_object.portallight = True

        with render_image_check_fixture.set_expected('portallight/lighting/expected'):
            pass

        with render_image_check_fixture.set_expected('portallight/lighting/visibility_primary_off_expected'):
            portallight_obj.rpr_object.visibility_in_primary_rays = False

        log("check background doesn't change lighting")
        environment.ibl.maps.override_background = True
        environment.ibl.maps.override_background_type = 'color'
        environment.ibl.maps.background_color = (1, 1, 0)

        with render_image_check_fixture.set_expected('portallight/lighting/visibility_primary_off_expected'):
            pass

        with render_image_check_fixture.set_expected('portallight/lighting/expected'):
            portallight_obj.rpr_object.visibility_in_primary_rays = True

        log("test sync")
        with render_image_check_fixture.set_expected_synced('portallight/lighting/visibility_primary_off_expected'):
            portallight_obj.rpr_object.visibility_in_primary_rays = False
            portallight_obj.update_tag()

        with render_image_check_fixture.set_expected_synced('portallight/lighting/expected'):
            portallight_obj.rpr_object.visibility_in_primary_rays = True
            portallight_obj.update_tag()

    def test_appearance(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):

        cube = bpy.context.object
        cube.scale = (0.5,) * 3

        bpy.ops.mesh.primitive_plane_add(radius=1)
        plane = bpy.context.object
        plane.location = (0.0, 0.0, 1.5)
        plane.scale = (1,) * 3
        portallight_obj = plane

        environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment
        environment.enable = True
        environment.type = 'IBL'
        environment.ibl.use_ibl_map = False
        environment.ibl.color = (0, 1, 1)
        environment.ibl.intensity = 1

        portallight_obj.rpr_object.portallight = True

        with render_image_check_fixture.set_expected('portallight/appearance/expected'):
            pass

        with render_image_check_fixture.set_expected('portallight/appearance/visibility_primary_off_expected'):
            portallight_obj.rpr_object.visibility_in_primary_rays = False

        log("check background doesn't change lighting")
        environment.ibl.maps.override_background = True
        environment.ibl.maps.override_background_type = 'color'
        environment.ibl.maps.background_color = (1, 1, 0)

        #NOTE: RPR 1.273 doesn't show background for portal tha doesn't show shape in primary rays
        with render_image_check_fixture.set_expected('portallight/appearance/visibility_primary_off_with_background_expected'):
            pass

        with render_image_check_fixture.set_expected('portallight/appearance/background'):
            portallight_obj.rpr_object.visibility_in_primary_rays = True


class TestMotionblur:
    def test_simple(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        motionblur_obj = bpy.context.object

        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (0.0, 0.0, 0)
        set_light_intensity(lamp_object, 4 * math.pi)

        environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment
        environment.enable = True
        environment.type = 'IBL'
        environment.ibl.use_ibl_map = False
        environment.ibl.color = (1, 1, 1)
        environment.ibl.intensity = 1

        bpy.context.scene.rpr.render.motion_blur = True
        bpy.context.scene.rpr.render.motion_blur_type = "GEOMETRY"

        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = 10

        motionblur_obj.location[1] = 1.0
        motionblur_obj.keyframe_insert(data_path="location", frame=2.0, index=1)
        motionblur_obj.location[1] = 10.0
        motionblur_obj.keyframe_insert(data_path="location", frame=8.0, index=1)

        bpy.context.scene.frame_set(3)

        with render_image_check_fixture.set_expected('motionblur/expected'):
            bpy.context.scene.rpr.render.motion_blur = True

        with render_image_check_fixture.set_expected('motionblur/off_expected'):
            bpy.context.scene.rpr.render.motion_blur = False

        log("test on sync")
        with render_image_check_fixture.set_expected_synced('motionblur/expected'):
            bpy.context.scene.rpr.render.motion_blur = True
        log("test off sync")
        with render_image_check_fixture.set_expected_synced('motionblur/off_expected'):
            bpy.context.scene.rpr.render.motion_blur = False

        log("test on sync")
        with render_image_check_fixture.set_expected_synced('motionblur/expected'):
            bpy.context.scene.rpr.render.motion_blur = True

    @pytest.mark.skip(reason="not implemented")
    def test_dupli(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        motionblur_obj = bpy.context.object

        bpy.ops.group.create()
        bpy.ops.object.group_instance_add(
            group='Group',
            location=(0, -2.5, 0))

        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (0.0, 0.0, 0)
        set_light_intensity(lamp_object, 10)

        environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment
        environment.enable = True
        environment.type = 'IBL'
        environment.ibl.use_ibl_map = False
        environment.ibl.color = (1, 1, 1)
        environment.ibl.intensity = 1

        bpy.context.scene.rpr.render.motion_blur = True
        bpy.context.scene.rpr.render.motion_blur_type = "GEOMETRY"

        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = 10

        motionblur_obj.location[1] = 1.0
        motionblur_obj.keyframe_insert(data_path="location", frame=2.0, index=1)
        motionblur_obj.location[1] = 10.0
        motionblur_obj.keyframe_insert(data_path="location", frame=8.0, index=1)

        bpy.context.scene.frame_set(3)

        with render_image_check_fixture.set_expected('motionblur/expected'):
            bpy.context.scene.rpr.render.motion_blur = True

        with render_image_check_fixture.set_expected('motionblur/off_expected'):
            bpy.context.scene.rpr.render.motion_blur = False

        log("test on sync")
        with render_image_check_fixture.set_expected_synced('motionblur/expected'):
            bpy.context.scene.rpr.render.motion_blur = True
        log("test off sync")
        with render_image_check_fixture.set_expected_synced('motionblur/off_expected'):
            bpy.context.scene.rpr.render.motion_blur = False

        log("test on sync")
        with render_image_check_fixture.set_expected_synced('motionblur/expected'):
            bpy.context.scene.rpr.render.motion_blur = True


class TestShadows:
    def test_emissive_mesh(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        # remove point light
        bpy.context.object.select = False
        bpy.context.scene.objects['Lamp'].select = True
        bpy.ops.object.delete()

        bpy.ops.mesh.primitive_plane_add()
        material = bpy.data.materials.new('Emissive')
        bpy.context.object.data.materials.append(material)
        tree = material_setup.create_default_node_tree()
        output = material_setup.get_node_tree_output(tree)
        emissive = tree.nodes.new(type='rpr_shader_node_emissive')
        emissive.inputs[emissive.color_in].default_value = (1, 1, 1, 1)
        tree.links.new(emissive.outputs[emissive.shader_out], output.inputs[output.shader_in])
        emissive.inputs[emissive.intensity_in].default_value = 20
        bpy.context.object.location = (-1, 0, 2.5)
        bpy.context.object.rotation_euler = (3.14159, 0, 0)
        bpy.context.object.scale = (0.25,) * 3

        self.run_shadows_test(render_image_check_fixture, material_setup)

    def test_area_light(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        # remove point light
        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (-1, 0, 2.5)
        lamp_object.rotation_euler = (0, 0, 0)
        lamp_object.data.type = 'AREA'
        lamp_object.data.color = (1, 1, 1)
        lamp_object.data.shape = 'SQUARE'
        lamp_object.data.size = 0.5
        set_light_intensity(lamp_object, 20 * lamp_object.data.size ** 2)

        self.run_shadows_test(render_image_check_fixture, material_setup)

    def run_shadows_test(self, render_image_check_fixture, material_setup):
        bpy.ops.mesh.primitive_cube_add()
        bpy.context.object.location = (0, 0, 1.5)
        bpy.context.object.scale = (0.5, 0.5, 0.2)
        shadowcaster_obj = bpy.context.object
        bpy.context.object.data.materials.append(bpy.data.materials.new('Material'))
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = material_editor.OutputNode(material_setup.get_node_tree_output(tree), editor)
        node = editor.create_microfacet_refraction_material_node()
        node.set_input_socket_value_by_name('color', (0.0, 1.0, 1.0, 1))
        node.set_input_socket_value_by_name('ior', 1.3)
        editor.link_nodes(node, output.get_input_shader_socket())
        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RPRRenderSettings
        rpr_settings_env = bpy.context.scene.world.rpr_data.environment
        rpr_settings.rendering_limits.iterations = 200
        rpr_settings_env.enable = False
        with render_image_check_fixture.set_expected('shadows/expected'):
            shadowcaster_obj.rpr_object.shadows = True
        with render_image_check_fixture.set_expected('shadows/off_expected'):
            shadowcaster_obj.rpr_object.shadows = False
        with render_image_check_fixture.set_expected_synced('shadows/expected'):
            shadowcaster_obj.rpr_object.shadows = True
            shadowcaster_obj.update_tag()
        with render_image_check_fixture.set_expected_synced('shadows/off_expected'):
            shadowcaster_obj.rpr_object.shadows = False
            shadowcaster_obj.update_tag()


def test_subdivision(render_image_check_fixture):
    bpy.context.scene.rpr.render.rendering_limits.iterations = 4

    folder = 'subdivision'

    with render_image_check_fixture.set_expected(folder + '/expected'):
        # make sure no crash without uvs
        # generate_uv()

        bpy.context.object.rpr_object.subdivision = 2
        bpy.context.object.rpr_object.subdivision_boundary = 'EDGE_AND_CORNER'
        bpy.context.object.rpr_object.subdivision_crease_weight = 0.0

    with render_image_check_fixture.set_expected(folder + '/expected_crease'):
        bpy.context.object.rpr_object.subdivision = 2
        bpy.context.object.rpr_object.subdivision_boundary = 'EDGE_AND_CORNER'
        bpy.context.object.rpr_object.subdivision_crease_weight = 1.0

    with render_image_check_fixture.set_expected(folder + '/expected_border'):
        bpy.context.object.rpr_object.subdivision = 2
        bpy.context.object.rpr_object.subdivision_boundary = 'EDGE_AND_CORNER'
        bpy.context.object.rpr_object.subdivision_crease_weight = 2.0


def test_subdivision_show_hide_with_material(render_image_check_fixture, material_setup):
    bpy.context.scene.rpr.render.rendering_limits.iterations = 4

    # normal subdivision was broken in 1.261(or 260)
    folder = 'subdivision'

    add_simple_material(material_setup, (1, 1, 0, 1))

    with render_image_check_fixture.set_expected(folder + '/expected_colored'):
        # generate_uv()

        bpy.context.object.rpr_object.subdivision_boundary = 'EDGE_AND_CORNER'
        bpy.context.object.rpr_object.subdivision_crease_weight = 0.0
        bpy.context.object.rpr_object.subdivision = 6

    with render_image_check_fixture.set_expected_synced(folder + '/expected_empty'):
        bpy.context.object.hide = True

    with render_image_check_fixture.set_expected_synced(
            folder + '/expected_colored'):
        bpy.context.object.hide = False


def test_subdivision_surface_material(render_image_check_fixture, material_setup):
    bpy.context.scene.rpr.render.rendering_limits.iterations = 4

    # normal subdivision was broken in 1.261(or 260)
    folder = 'subdivision'

    add_simple_material(material_setup, (1, 1, 0, 1))

    log("renders with yellow material")
    with render_image_check_fixture.set_expected(folder + '/expected_colored'):
        # generate_uv()

        bpy.context.object.rpr_object.subdivision_boundary = 'EDGE_AND_CORNER'
        bpy.context.object.rpr_object.subdivision_crease_weight = 0.0
        bpy.context.object.rpr_object.subdivision = 6

    log("renders with DIFFERENT material")
    with render_image_check_fixture.set_expected_synced(folder + '/expected_other_colored'):

        material = bpy.data.materials.new(name='YellowAgain')

        # create node tree with output node
        tree = material_setup.create_default_node_tree(material)
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)

        # create colored diffuse node and connect to output
        testee = editor.create_diffuse_material_node()
        editor.link_nodes(testee, output.get_input_shader_socket())
        testee.set_color_value((0, 1, 1, 1))

        # set material to active slot
        bpy.context.object.data.materials[0] = material
        material.update_tag()

@notquick
def test_subdivision_stress():
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=2, smoothness=0)
    bpy.ops.object.mode_set(mode='OBJECT')
    #
    # bpy.context.scene.rpr.render.rendering_limits.iterations = 1
    #
    # with render_image_check_fixture.set_expected(None):
    #     bpy.context.object.rpr_object.subdivision = 6 if i%1 else 8
    #
    # # with render_image_check_fixture.set_expected(None):
    # #     bpy.context.object.rpr_object.subdivision = 8

    basic_render_settings()
    rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
    rpr_settings.rendering_limits.iterations = 1

    time_start = time.perf_counter()

    for i, subviv in enumerate(6 if (i % 2) else 8 for i in range(4)):
        print('stress:', i, subviv)
        fixture = ViewportFixture()
        time_start = time.perf_counter()
        bpy.context.object.rpr_object.subdivision = subviv
        fixture.start()
        fixture.wait_for_render_complete()
        fixture.destroy()
        print('done in', time.perf_counter() - time_start)

    print('done in ', time.perf_counter() - time_start)


def test_displacement(render_image_check_fixture, material_setup, tmpdir_factory):
    with render_image_check_fixture.set_expected('displacement/expected'):
        # generate simple uvs - RPR subdivision code requires them
        generate_uv()

        bpy.context.object.rpr_object.subdivision = 8
        bpy.context.object.rpr_object.subdivision_crease_weight = 0.0

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = material_editor.OutputNode(material_setup.get_node_tree_output(tree), editor)
        testee = editor.create_displacement_node()

        testee.node.scale_min = 0
        testee.node.scale_max = 0.2

        node_imagemap = material_editor.ImageTexture(create_hemisphere_image_map('displacement', tree, tmpdir_factory),
                                                     editor)
        editor.link_nodes(node_imagemap, testee.get_input_socket_by_name('map'))

        editor.link_nodes(testee, output.get_input_socket_by_name('displacement'))

    log("check that displacement disconnect syncs")
    with render_image_check_fixture.set_expected_synced('displacement/detached_expected'):
        log("add colored surface material - seems there is a bug that it's removed when displacement removed")
        colored = editor.create_diffuse_material_node()
        colored.set_color_value((1, 1, 0, 1))
        editor.link_nodes(colored, output.get_input_shader_socket())

        editor.tree.links.remove(output.get_input_socket_by_name('displacement').links[0])



def test_displacement_shading_normal(render_image_check_fixture, material_setup, tmpdir_factory):
    passes_aov = get_render_passes_aov(bpy.context)
    passes_aov.enable = True

    aov_nam = 'shading_normal'
    blender_pass = rprblender.render.render_layers.aov_info[aov_nam]['name']

    for i in range(len(passes_aov.passesStates)):
        passes_aov.passesStates[i] = aov_nam == passes_aov.render_passes_items[i][0]

    with render_image_check_fixture.set_expected('displacement/shading_normal_expected',
                                                 aov=aov_nam):
        # generate simple uvs - RPR subdivision code requires them
        generate_uv()

        bpy.context.object.rpr_object.subdivision = 8
        bpy.context.object.rpr_object.subdivision_crease_weight = 0.0

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = material_editor.OutputNode(material_setup.get_node_tree_output(tree), editor)
        testee = editor.create_displacement_node()

        testee.node.scale_min = 0
        testee.node.scale_max = 0.2

        node_imagemap = material_editor.ImageTexture(create_hemisphere_image_map('displacement', tree, tmpdir_factory),
                                                     editor)
        editor.link_nodes(node_imagemap, testee.get_input_socket_by_name('map'))

        editor.link_nodes(testee, output.get_input_socket_by_name('displacement'))


class TestViewRenderBorder:

    def setup_method(self, test_method):
        generate_uv()

        bpy.context.scene.rpr.render.rendering_limits.iterations = 10
        bpy.context.scene.rpr.render.render_mode = 'TEXCOORD'

    def test_border_persp(self, render_image_check_fixture: RenderImageCheck):
        self.run_border_test(render_image_check_fixture, 'view/border/persp')

    def run_border_test(self, render_image_check_fixture, folder):
        folder = Path(folder)
        with render_image_check_fixture.set_expected(folder / 'horizontal/default_expected'):
            pass

        render_image_check_fixture.viewport_fixture.render_region = [[0.25, 0.5], [0, 1]]

        with render_image_check_fixture.set_expected(folder / 'horizontal/left_expected'):
            pass

class TestCameraBorder:

    def setup_method(self, test_method):
        generate_uv()

        bpy.context.scene.rpr.render.rendering_limits.iterations = 10
        bpy.context.scene.rpr.render.render_mode = 'TEXCOORD'

    def test_border_persp(self, render_image_check_fixture: RenderImageCheck):
        self.run_border_test(render_image_check_fixture, 'camera/border/persp')

    def test_border_ortho(self, render_image_check_fixture: RenderImageCheck):
        camera = bpy.context.scene.camera

        camera.data.type = 'ORTHO'
        camera.data.ortho_scale = 3

        self.run_border_test(render_image_check_fixture, 'camera/border/ortho/')

    def run_border_test(self, render_image_check_fixture, folder):
        folder = Path(folder)
        with render_image_check_fixture.set_expected(folder / 'horizontal/default_expected'):
            pass
        bpy.context.scene.render.use_border = True
        bpy.context.scene.render.border_min_x = 0.25
        bpy.context.scene.render.border_max_x = 0.5
        with render_image_check_fixture.set_expected(folder / 'horizontal/left_expected'):
            pass
        bpy.context.scene.render.border_min_x = 0.5
        bpy.context.scene.render.border_max_x = 0.75
        with render_image_check_fixture.set_expected(folder / 'horizontal/right_expected'):
            pass
        bpy.context.scene.render.border_min_x = 0
        bpy.context.scene.render.border_max_x = 1
        bpy.context.scene.render.border_min_y = 0.25
        bpy.context.scene.render.border_max_y = 0.5
        with render_image_check_fixture.set_expected(folder / 'horizontal/down_expected'):
            pass
        bpy.context.scene.render.border_min_y = 0.5
        bpy.context.scene.render.border_max_y = 0.75
        with render_image_check_fixture.set_expected(folder / 'horizontal/up_expected'):
            pass
        bpy.context.scene.render.border_min_x = 0.25
        bpy.context.scene.render.border_max_x = 0.75
        bpy.context.scene.render.border_min_y = 0.25
        bpy.context.scene.render.border_max_y = 0.75
        with render_image_check_fixture.set_expected(folder / 'horizontal/center_expected'):
            pass
        bpy.context.scene.render.use_border = False
        # make vertical
        render_resolution = render_image_check_fixture.viewport_fixture.render_resolution
        render_image_check_fixture.viewport_fixture.render_resolution = render_resolution[1], render_resolution[0]
        with render_image_check_fixture.set_expected(folder / 'vertical/default_expected'):
            pass
        bpy.context.scene.render.use_border = True
        bpy.context.scene.render.border_min_x = 0.25
        bpy.context.scene.render.border_max_x = 0.5
        with render_image_check_fixture.set_expected(folder / 'vertical/left_expected'):
            pass
        bpy.context.scene.render.border_min_x = 0.5
        bpy.context.scene.render.border_max_x = 0.75
        with render_image_check_fixture.set_expected(folder / 'vertical/right_expected'):
            pass
        bpy.context.scene.render.border_min_x = 0
        bpy.context.scene.render.border_max_x = 1
        bpy.context.scene.render.border_min_y = 0.25
        bpy.context.scene.render.border_max_y = 0.5
        with render_image_check_fixture.set_expected(folder / 'vertical/down_expected'):
            pass
        bpy.context.scene.render.border_min_y = 0.5
        bpy.context.scene.render.border_max_y = 0.75
        with render_image_check_fixture.set_expected(folder / 'vertical/up_expected'):
            pass
        bpy.context.scene.render.border_min_x = 0.25
        bpy.context.scene.render.border_max_x = 0.75
        bpy.context.scene.render.border_min_y = 0.25
        bpy.context.scene.render.border_max_y = 0.75
        with render_image_check_fixture.set_expected(folder / 'vertical/center_expected'):
            pass



class TestVRCamera:
    def test_simple(self, render_image_check_fixture: RenderImageCheck, material_setup):
        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RPRRenderSettings

        lamp_object = bpy.context.scene.objects['Lamp']
        lamp_object.location = (0.0, 0.0, 4)

        bpy.ops.mesh.primitive_cube_add()
        bpy.context.object.location = (0, 0, 8)
        self.set_colored_material(material_setup, (1, 0, 0, 1))

        bpy.ops.mesh.primitive_cube_add()
        bpy.context.object.location = (0, 4, 4)
        self.set_colored_material(material_setup, (0, 1, 0, 1))

        bpy.ops.mesh.primitive_cube_add()
        bpy.context.object.location = (4, 0, 4)
        self.set_colored_material(material_setup, (0, 0, 1, 1))

        bpy.ops.mesh.primitive_cube_add()
        bpy.context.object.location = (-4, 0, 4)
        self.set_colored_material(material_setup, (0, 1, 1, 1))

        bpy.ops.mesh.primitive_cube_add()
        bpy.context.object.location = (0, -4, 4)
        self.set_colored_material(material_setup, (1, 1, 0, 1))

        with render_image_check_fixture.set_expected('camera/default_expected'):
            pass

        rpr_settings.camera.override_camera_settings = True

        with render_image_check_fixture.set_expected('camera/cubemap_expected'):
            rpr_settings.camera.panorama_type = 'CUBEMAP'

        with render_image_check_fixture.set_expected('camera/spherical_panorama_expected'):
            rpr_settings.camera.panorama_type = 'SPHERICAL_PANORAMA'

        with render_image_check_fixture.set_expected('camera/stereo_cubemap_expected'):
            rpr_settings.camera.panorama_type = 'CUBEMAP'
            rpr_settings.camera.stereo = True

        with render_image_check_fixture.set_expected('camera/stereo_spherical_panorama_expected'):
            rpr_settings.camera.panorama_type = 'SPHERICAL_PANORAMA'
            rpr_settings.camera.stereo = True

        rpr_settings.camera.override_camera_settings = False
        with render_image_check_fixture.set_expected('camera/default_expected'):
            pass

        log("check settings on camera object rpr_camera")
        with render_image_check_fixture.set_expected('camera/spherical_panorama_expected'):
            bpy.context.scene.camera.data.type = 'PANO'
            assert not bpy.context.scene.camera.data.rpr_camera.stereo

        log("check settings type/stereo works")
        with render_image_check_fixture.set_expected('camera/stereo_cubemap_expected'):
            bpy.context.scene.camera.data.type = 'PANO'
            bpy.context.scene.camera.data.rpr_camera.panorama_type = 'CUBEMAP'
            bpy.context.scene.camera.data.rpr_camera.stereo = True

    def set_colored_material(self, material_setup, color):
        context = bpy.context

        material = bpy.data.materials.new('Material 2')
        mesh = context.object.data
        mesh.materials.append(material)

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)
        material = editor.create_diffuse_material_node()
        editor.link_nodes(material, output.get_input_shader_socket())
        material.set_color_value(color)


def add_simple_material(material_setup, color):
    bpy.context.object.data.materials.append(bpy.data.materials.new('Material'))
    tree = material_setup.create_default_node_tree()
    editor = MaterialEditor(tree)
    output = OutputNode(material_setup.get_node_tree_output(tree), editor)
    # create Normal Map node and connect it to Diffuse material Normal input
    testee = editor.create_diffuse_material_node()
    editor.link_nodes(testee, output.get_input_shader_socket())
    editor.link_nodes(testee, output.get_input_shader_socket())
    testee.set_color_value(color)


class TestMesh:
    # @pytest.mark.skipif(0x010000242 >= pyrpr.API_VERSION,
    #                    reason="crashing on shape delete prior to 1.243")
    def test_ngon(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        log("test polygons with >4 vertices(not supported by Core")
        bpy.ops.object.delete()
        bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2)

        with render_image_check_fixture.set_expected('mesh/cylinder_expected'):
            pass
        render_image_check_fixture.viewport_fixture.destroy()

    def test_curve_export(self, render_image_check_fixture, material_setup, request, tmpdir_factory):
        bpy.ops.object.delete()

        with render_image_check_fixture.set_expected('mesh/curve'):
            bpy.ops.curve.primitive_bezier_circle_add(radius=1)
            bpy.context.object.data.dimensions = '2D'
            bpy.context.object.data.fill_mode = 'BOTH'

            add_simple_material(material_setup, (1, 1, 1, 1))

    def test_curve_sync(self, render_image_check_fixture, material_setup, request, tmpdir_factory):
        bpy.ops.object.delete()

        with render_image_check_fixture.set_expected(None):
            pass

        print("checking add sync")
        with render_image_check_fixture.set_expected_synced('mesh/curve'):
            bpy.ops.curve.primitive_bezier_circle_add(radius=1)
            bpy.context.object.data.dimensions = '2D'
            bpy.context.object.data.fill_mode = 'BOTH'

            add_simple_material(material_setup, (1, 1, 1, 1))

    def test_surface(self, render_image_check_fixture, material_setup, request, tmpdir_factory):
        with render_image_check_fixture.set_expected('mesh/surface'):
            bpy.ops.object.delete()

            bpy.ops.surface.primitive_nurbs_surface_surface_add(radius=1)

            add_simple_material(material_setup, (1, 1, 1, 1))

    def test_text(self, render_image_check_fixture, material_setup, request, tmpdir_factory):
        with render_image_check_fixture.set_expected('mesh/text'):
            bpy.ops.object.delete()

            bpy.ops.object.text_add(radius=1)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.font.delete(type='ALL')
            bpy.ops.font.text_insert(text='RPR')
            bpy.ops.object.mode_set(mode='OBJECT')

            add_simple_material(material_setup, (1, 1, 1, 1))

    def test_meta(self, render_image_check_fixture, material_setup, request, tmpdir_factory):
        bpy.ops.object.delete()

        bpy.ops.object.metaball_add(type='BALL', radius=1)
        add_simple_material(material_setup, (1, 1, 1, 1))

        print("add second metaball to make sure all works")
        bpy.ops.object.metaball_add(type='BALL', radius=1)
        # self.add_simple_material(material_setup, (1, 1, 1, 1))
        bpy.context.object.location = (1, 0, 0)
        bpy.context.object.scale = (1, 0.5, 1)

        with render_image_check_fixture.set_expected('mesh/meta'):
            pass

        with render_image_check_fixture.set_expected_synced('mesh/meta_changed'):
            bpy.context.object.location = (2, 0, 0)

    def test_texture_coordinates(self, render_image_check_fixture, material_setup, request, tmpdir_factory):
        # bpy.ops.object.delete()
        # bpy.ops.mesh.primitive_plane_add(radius=1)
        # bpy.context.object.location = (0, 0, 1)

        bpy.context.scene.rpr.render.rendering_limits.iterations = 10
        bpy.context.scene.rpr.render.render_mode = 'TEXCOORD'

        with render_image_check_fixture.set_expected('texture_coordinates/expected'):
            generate_uv()

        with render_image_check_fixture.set_expected('texture_coordinates/non_integer'):
            uv_layer = bpy.context.object.data.uv_layers.active
            for i, loop in enumerate(uv_layer.data):
                uv = np.array(loop.uv, dtype=np.float32)
                loop.uv = uv * 0.5 + 0.25

    def test_normals(self, render_image_check_fixture, material_setup, request, tmpdir_factory):
        bpy.context.scene.rpr.render.rendering_limits.iterations = 4
        bpy.context.scene.rpr.render.render_mode = 'NORMAL'

        with render_image_check_fixture.set_expected('normals/flat'):
            pass

        with render_image_check_fixture.set_expected('normals/smooth'):
            bpy.ops.object.shade_smooth()

        print("use_auto_smooth")
        with render_image_check_fixture.set_expected('normals/flat'):
            bpy.context.object.data.use_auto_smooth = True
            bpy.context.object.data.auto_smooth_angle = 0  # 89/180*np.pi

        with render_image_check_fixture.set_expected('normals/autosmooth'):
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.subdivide(number_cuts=1, smoothness=1)
            bpy.ops.object.mode_set(mode='OBJECT')

            bpy.context.object.data.use_auto_smooth = True
            bpy.context.object.data.auto_smooth_angle = 10 / 180 * np.pi


class TestMeshSync:
    def test_readd(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory, request, material_setup):
        with render_image_check_fixture.set_expected('mesh/cube_expected'):
            pass

        print("delete cube and add cylinder")
        with render_image_check_fixture.set_expected_synced('mesh/cylinder_expected'):
            bpy.ops.object.delete()
            bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2)

        with render_image_check_fixture.set_expected_synced('mesh/cube_expected'):
            bpy.ops.object.delete()
            bpy.ops.mesh.primitive_cube_add()


def test_texturecompression(render_image_check_fixture, material_setup, request, tmpdir_factory):
    generate_uv()

    tree = material_setup.create_default_node_tree()
    editor = MaterialEditor(tree)
    output = OutputNode(material_setup.get_node_tree_output(tree), editor)

    # create Normal Map node and connect it to Diffuse material Normal input
    testee = editor.create_diffuse_material_node()

    editor.link_nodes(testee, output.get_input_shader_socket())

    editor.link_nodes(testee, output.get_input_shader_socket())

    image_texture = editor.create_image_texture_node()
    image_texture.set_image(create_gradients_image(tmpdir_factory))
    editor.link_nodes(image_texture, testee.get_input_socket_by_name('color'))

    set_light_intensity(bpy.context.scene.objects['Lamp'], 4 * math.pi * 200)

    with render_image_check_fixture.set_expected('texturecompression/compressed_diffuse',
                                                 max_avg_dev=0.002, max_std_dev=0.005):
        # force-purge core images cache
        rprblender.images.core_image_cache.purge()
        bpy.context.scene.rpr.render.texturecompression = True

    with render_image_check_fixture.set_expected('texturecompression/uncompressed_diffuse',
                                                 max_avg_dev=0.002, max_std_dev=0.005):
        # force-purge core images cache
        rprblender.images.core_image_cache.purge()
        bpy.context.scene.rpr.render.texturecompression = False


def test_load_image_speed(render_image_check_fixture, material_setup, request, tmpdir_factory):
    with render_image_check_fixture.set_expected('speed/load_image'):
        generate_uv()

        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)

        blend = editor.create_blend_material_node()

        # create Normal Map node and connect it to Diffuse material Normal input
        testee = editor.create_diffuse_material_node()
        transparent = editor.create_transparent_material_node()

        editor.link_nodes(testee, blend.get_input_socket_by_name('shader1'))
        editor.link_nodes(transparent, blend.get_input_socket_by_name('shader2'))

        editor.link_nodes(blend, output.get_input_shader_socket())
        blend.set_input_socket_value_by_name('weight', 0.0)

        image_texture = editor.create_image_texture_node()
        image = create_color_fill_image_packed((1, 1, 0), (4,) * 2)

        # image.filepath_raw = str(tmpdir_factory.mktemp('textures').join('image_texture.hdr'))
        # image.file_format = 'HDR'
        # image.save()

        environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment

        # environment.enable = True
        # environment.ibl.use_ibl_map = True
        # environment.type = 'IBL'
        # environment.ibl.ibl_map = image.filepath_raw

        image_texture.set_image(image)

        editor.link_nodes(image_texture, testee.get_input_socket_by_name('color'))

@notquick
@pytest.mark.timeout(10)
def test_load_image_cache(render_image_check_fixture, material_setup, request, tmpdir_factory):
    image = create_color_fill_image_packed((1, 1, 0), (1024,) * 2)

    # image.filepath_raw = str(tmpdir_factory.mktemp('textures').join('image_texture.hdr'))
    # image.file_format = 'HDR'
    # image.save()

    environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment

    # environment.enable = True
    # environment.ibl.use_ibl_map = True
    # environment.type = 'IBL'
    # environment.ibl.ibl_map = image.filepath_raw
    # environment.ibl.color = (1, 1, 1)

    bpy.ops.object.delete()

    # config.image_cache_blender = True
    # config.image_cache_core = False

    # make many objects with different materials using same texture
    grid_size = (10, 10, 1)
    for x in np.linspace(-1, 1, grid_size[0]):
        for y in np.linspace(-1, 1, grid_size[1]):
            bpy.ops.mesh.primitive_cube_add()
            bpy.context.object.location = (2 * x, 2 * y, 0)
            bpy.context.object.scale = (1.5 / grid_size[0], 1.5 / grid_size[1], 0.025)

            # create default material
            material = bpy.data.materials.new('Material')
            mesh = bpy.context.object.data
            mesh.materials.append(material)

            tree = material_setup.create_default_node_tree()
            editor = MaterialEditor(tree)
            output = OutputNode(material_setup.get_node_tree_output(tree), editor)

            blend = editor.create_blend_material_node()

            # create Normal Map node and connect it to Diffuse material Normal input
            testee = editor.create_diffuse_material_node()
            transparent = editor.create_diffuse_material_node()
            transparent.set_input_socket_value_by_name('color', (0.5, 0.5, 1, 1))

            editor.link_nodes(testee, blend.get_input_socket_by_name('shader1'))
            editor.link_nodes(transparent, blend.get_input_socket_by_name('shader2'))

            editor.link_nodes(blend, output.get_input_shader_socket())
            blend.set_input_socket_value_by_name('weight',
                                                 0.25 + 0.25 * np.sin((np.square(x) + np.square(y)) * np.pi * 2))
            # blend.set_input_socket_value_by_name('weight', 1)

            image_texture = editor.create_image_texture_node()

            image_texture.set_image(image)

            editor.link_nodes(image_texture, testee.get_input_socket_by_name('color'))

    with render_image_check_fixture.set_expected('speed/load_image_cache'):
        generate_uv()

    import rprblender.images
    log(rprblender.images.image_cache.stats.format_current())



@notquick
@pytest.mark.timeout(30)
def test_core_image_cache_and_context_cache_for_engine_render_calls(render_image_check_fixture, material_setup, request, tmpdir_factory):
    """"test that images are cached between unrelated render final renders, for example when renderring
    animation sequence - same settings(HW, texturecompression etc) but different RenderEngine calls"""
    #image = create_color_fill_image_packed((1, 1, 0), (4096,) * 2)

    image_fpath = str(tmpdir_factory.mktemp('textures').join('image_texture.png'))

    # make really hute texture to make sure its setup takes time
    im = np.full((16384, 16384, 3), (255, 255, 0), dtype=np.uint8)
    import imageio
    imageio.imsave(image_fpath, im)
    image = bpy_extras.image_utils.load_image(image_fpath)

    # image.filepath_raw = str(tmpdir_factory.mktemp('textures').join('image_texture.hdr'))
    # image.file_format = 'HDR'
    # image.save()

    environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment

    # environment.enable = True
    # environment.ibl.use_ibl_map = True
    # environment.type = 'IBL'
    # environment.ibl.ibl_map = image.filepath_raw
    # environment.ibl.color = (1, 1, 1)

    bpy.ops.object.delete()

    # config.image_cache_blender = True
    # config.image_cache_core = False

    x, y = 0, 0

    bpy.ops.mesh.primitive_cube_add()
    bpy.context.object.location = (2 * x, 2 * y, 0)
    bpy.context.object.scale = (0.5, 0.5, 0.025)

    # create default material
    material = bpy.data.materials.new('Material')
    mesh = bpy.context.object.data
    mesh.materials.append(material)

    tree = material_setup.create_default_node_tree()
    editor = MaterialEditor(tree)
    output = OutputNode(material_setup.get_node_tree_output(tree), editor)

    blend = editor.create_blend_material_node()

    # create Normal Map node and connect it to Diffuse material Normal input
    testee = editor.create_diffuse_material_node()
    transparent = editor.create_diffuse_material_node()
    transparent.set_input_socket_value_by_name('color', (0.5, 0.5, 1, 1))

    editor.link_nodes(testee, blend.get_input_socket_by_name('shader1'))
    editor.link_nodes(transparent, blend.get_input_socket_by_name('shader2'))

    editor.link_nodes(blend, output.get_input_shader_socket())
    blend.set_input_socket_value_by_name('weight',
                                         0.25 + 0.25 * np.sin((np.square(x) + np.square(y)) * np.pi * 2))
    # blend.set_input_socket_value_by_name('weight', 1)

    image_texture = editor.create_image_texture_node()

    image_texture.set_image(image)

    editor.link_nodes(image_texture, testee.get_input_socket_by_name('color'))

    rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
    rpr_settings.rendering_limits.enable = True
    rpr_settings.rendering_limits.type = 'ITER'
    rpr_settings.rendering_limits.iterations = 1

    # set texture compression so making core image would take more time
    rpr_settings.texturecompression = True

    for i in range(20):

        fpath = Path(str(tmpdir_factory.mktemp('data').join('image.png')))
        try:
            bpy.context.scene.render.filepath = str(fpath)
            bpy.ops.render.render(write_still=True)
            assert fpath.is_file(), tempfile
            # TODO:check resulting image here
        finally:
            fpath.unlink()

    import rprblender.images
    log(rprblender.images.image_cache.stats.format_current())


@pytest.fixture(scope='session')
def huge_image(tmpdir_factory):
    image_fpath = str(tmpdir_factory.mktemp('textures').join('huge_image.png'))
    # make really hute texture to make sure its setup takes time
    size = 4096*2
    im = np.full((size, size, 3), (255, 255, 0), dtype=np.uint8)
    import imageio
    imageio.imsave(image_fpath, im)
    yield image_fpath


@notquick
@pytest.mark.parametrize('i', range(100))
def test_context_reuse_memory(i, reset_blender, material_setup, tmpdir_factory, huge_image):
    """"test that image cache is cleared between scene loads. if not this will run only with lots os memory avail"""

    # make image unique per run so it's not definitely cached
    image_fpath = str(tmpdir_factory.mktemp('textures').join('image_texture%d.png'%i))
    shutil.copy(huge_image, image_fpath)

    image = bpy_extras.image_utils.load_image(image_fpath)

    bpy.ops.object.delete()

    x, y = 0, 0

    bpy.ops.mesh.primitive_cube_add()
    bpy.context.object.location = (2 * x, 2 * y, 0)
    bpy.context.object.scale = (0.5, 0.5, 0.025)

    # create default material
    material = bpy.data.materials.new('Material')
    mesh = bpy.context.object.data
    mesh.materials.append(material)

    tree = material_setup.create_default_node_tree()
    editor = MaterialEditor(tree)
    output = OutputNode(material_setup.get_node_tree_output(tree), editor)

    # create Normal Map node and connect it to Diffuse material Normal input
    testee = editor.create_diffuse_material_node()
    transparent = editor.create_diffuse_material_node()
    transparent.set_input_socket_value_by_name('color', (0.5, 0.5, 1, 1))

    editor.link_nodes(testee, output.get_input_shader_socket())

    image_texture = editor.create_image_texture_node()

    image_texture.set_image(image)

    editor.link_nodes(image_texture, testee.get_input_socket_by_name('color'))

    rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
    rpr_settings.rendering_limits.enable = True
    rpr_settings.rendering_limits.type = 'ITER'
    rpr_settings.rendering_limits.iterations = 1

    # set texture compression so making core image would take more time
    rpr_settings.texturecompression = True

    environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment
    environment.enable = False

    bpy.context.scene.rpr.dev.trace_dump = True
    bpy.context.scene.rpr.dev.trace_dump_folder = tracing_folder

    fpath = Path(str(tmpdir_factory.mktemp('data').join('image.png')))
    try:
        bpy.context.scene.render.filepath = str(fpath)
        bpy.ops.render.render(write_still=True)
        assert fpath.is_file(), tempfile
        # TODO:check resulting image here
    finally:
        fpath.unlink()

    import rprblender.images
    log(rprblender.images.image_cache.stats.format_current())


@notquick
@pytest.mark.timeout(20)
def test_animation_image_cache(render_image_check_fixture, material_setup, request, tmpdir_factory):
    image = create_color_fill_image_packed((1, 1, 0), (1024,) * 2)

    # image.filepath_raw = str(tmpdir_factory.mktemp('textures').join('image_texture.hdr'))
    # image.file_format = 'HDR'
    # image.save()

    environment = bpy.context.scene.world.rpr_data.environment  # type: rprblender.properties.RenderEnvironment

    # environment.enable = True
    # environment.ibl.use_ibl_map = True
    # environment.type = 'IBL'
    # environment.ibl.ibl_map = image.filepath_raw
    # environment.ibl.color = (1, 1, 1)

    bpy.ops.object.delete()

    # make many objects with different materials using same texture
    grid_size = (10, 10, 1)
    for x in np.linspace(-1, 1, grid_size[0]):
        for y in np.linspace(-1, 1, grid_size[1]):
            bpy.ops.mesh.primitive_cube_add()
            bpy.context.object.location = (2 * x, 2 * y, 0)
            bpy.context.object.scale = (1.5 / grid_size[0], 1.5 / grid_size[1], 0.025)

            # create default material
            material = bpy.data.materials.new('Material')
            mesh = bpy.context.object.data
            mesh.materials.append(material)

            tree = material_setup.create_default_node_tree()
            editor = MaterialEditor(tree)
            output = OutputNode(material_setup.get_node_tree_output(tree), editor)

            blend = editor.create_blend_material_node()

            # create Normal Map node and connect it to Diffuse material Normal input
            testee = editor.create_diffuse_material_node()
            transparent = editor.create_diffuse_material_node()
            transparent.get_input_socket_by_name('color').default_value = (0, 0, 1, 1)
            transparent.get_input_socket_by_name('color').keyframe_insert("default_value", frame=1)
            transparent.get_input_socket_by_name('color').default_value = (1, 0.5, 0.5, 1)
            transparent.get_input_socket_by_name('color').keyframe_insert("default_value", frame=10)

            editor.link_nodes(testee, blend.get_input_socket_by_name('shader1'))
            editor.link_nodes(transparent, blend.get_input_socket_by_name('shader2'))

            editor.link_nodes(blend, output.get_input_shader_socket())
            blend.set_input_socket_value_by_name('weight',
                                                 0.25 + 0.25 * np.sin((np.square(x) + np.square(y)) * np.pi * 2))
            # blend.set_input_socket_value_by_name('weight', 1)

            image_texture = editor.create_image_texture_node()

            image_texture.set_image(image)

            editor.link_nodes(image_texture, testee.get_input_socket_by_name('color'))

    for i in range(1, 10):
        bpy.context.scene.frame_set(i)
        with render_image_check_fixture.set_expected('speed/load_image_cache_animation/%d' % i):
            generate_uv()

    import rprblender.images
    log(rprblender.images.image_cache.stats.format_current())


def test_thumbnail():
    generate_uv()
    tree = create_node_tree()
    surface_material = get_surface_material(tree)

    from . import node_thumbnail

    settings = bpy.context.scene.rpr.render_thumbnail  # type: rprblender.properties.RenderSettings
    settings.rendering_limits.type = 'ITER'
    settings.rendering_limits.iterations = 10

    # force thmbnail renderer to reander A LOT of nodes simultaneously
    for i in range(100):
        print('making:', i)
        node_noise2d = tree.nodes.new(type='rpr_texture_node_noise2d')

    for name, value in node_thumbnail.get_thumbnail_manager().thumbnails.items():
        while value[0].thread:
            time.sleep(0)


class TestAov:

    blender_passes = list(rprblender.render.render_layers.pass2aov)

    @pytest.mark.parametrize('blender_pass', blender_passes)
    def test_aov(self, blender_pass, material_setup, render_image_check_fixture: RenderImageCheck):
        generate_uv()

        # make transparent material for mesh
        bpy.context.object.data.materials.append(bpy.data.materials.new('Material'))
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)
        # create Normal Map node and connect it to Diffuse material Normal input
        diffuse = editor.create_diffuse_material_node()
        transparent = editor.create_transparent_material_node()
        blend = editor.create_blend_material_node()

        diffuse.set_color_value((1.0, 0.5, 0.75, 1))
        editor.link_nodes(transparent, blend.get_input_socket_by_name('shader1'))
        editor.link_nodes(diffuse, blend.get_input_socket_by_name('shader2'))
        blend.set_input_socket_value_by_name('weight', 0.25)
        editor.link_nodes(blend, output.get_input_shader_socket())

        bpy.ops.mesh.primitive_ico_sphere_add()
        bpy.context.object.location = (1, 0, -1)
        bpy.context.object.scale = (1.5,) * 3

        passes_aov = get_render_passes_aov(bpy.context)
        passes_aov.enable = True

        aov_name_tested = rprblender.render.render_layers.pass2aov[blender_pass]
        name = 'aov/aov_pass_' + aov_name_tested

        # enable only pass under test
        for i in range(len(passes_aov.passesStates)):
            passes_aov.passesStates[i] = aov_name_tested == passes_aov.render_passes_items[i][0]

        # skip image checking for object/material index images - they randomize and fail 50% of the time
        # but render them anyway, for smoketest
        if 'index' in blender_pass.lower():
            name = None

        with render_image_check_fixture.set_expected(name, aov=aov_name_tested):
            pass

            # make sure getting combined is fine too
            # with render_image_check_fixture.set_expected_synced(name, aov='COMBINED'):
            #     pass

    def test_aov_sync(self, material_setup, render_image_check_fixture: RenderImageCheck):
        generate_uv()

        # make transparent material for mesh
        bpy.context.object.data.materials.append(bpy.data.materials.new('Material'))
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)
        # create Normal Map node and connect it to Diffuse material Normal input
        diffuse = editor.create_diffuse_material_node()
        transparent = editor.create_transparent_material_node()
        blend = editor.create_blend_material_node()

        diffuse.set_color_value((1.0, 0.5, 0.75, 1))
        editor.link_nodes(transparent, blend.get_input_socket_by_name('shader1'))
        editor.link_nodes(diffuse, blend.get_input_socket_by_name('shader2'))
        blend.set_input_socket_value_by_name('weight', 0.25)
        editor.link_nodes(blend, output.get_input_shader_socket())

        bpy.ops.mesh.primitive_ico_sphere_add()
        bpy.context.object.location = (1, 0, -1)
        bpy.context.object.scale = (1.5,) * 3

        passes_aov = get_render_passes_aov(bpy.context)
        passes_aov.enable = True

        aov_name = 'shading_normal'

        # enable only pass under test
        for i, item in enumerate(passes_aov.render_passes_items):
            passes_aov.passesStates[i] = aov_name == item[0]

        with render_image_check_fixture.set_expected('aov/aov_pass_' + aov_name,
                                                     aov=aov_name):
            pass

        # retrieving non-rendered pass
        assert render_image_check_fixture.viewport_fixture.viewport_renderer.get_image('depth') is None

        aov_name = 'depth'

        # enable only pass under test
        for i, item in enumerate(passes_aov.render_passes_items):
            passes_aov.passesStates[i] = aov_name == item[0]

        # check that retrieving image immediately doesn't fail
        render_image_check_fixture.viewport_fixture.viewport_renderer.get_image('depth')

        with render_image_check_fixture.set_expected('aov/aov_pass_' + aov_name,
                                                     aov=aov_name):
            pass

    def test_transparent(self, material_setup, render_image_check_fixture: RenderImageCheck):
        generate_uv()

        # make transparent material for mesh
        bpy.context.object.data.materials.append(bpy.data.materials.new('Material'))
        tree = material_setup.create_default_node_tree()
        editor = MaterialEditor(tree)
        output = OutputNode(material_setup.get_node_tree_output(tree), editor)
        # create Normal Map node and connect it to Diffuse material Normal input
        diffuse = editor.create_diffuse_material_node()
        transparent = editor.create_transparent_material_node()
        blend = editor.create_blend_material_node()

        diffuse.set_color_value((1.0, 0.5, 0.75, 1))
        editor.link_nodes(transparent, blend.get_input_socket_by_name('shader1'))
        editor.link_nodes(diffuse, blend.get_input_socket_by_name('shader2'))
        blend.set_input_socket_value_by_name('weight', 0.25)
        editor.link_nodes(blend, output.get_input_shader_socket())

        bpy.ops.mesh.primitive_ico_sphere_add()
        bpy.context.object.location = (1, 0, -1)
        bpy.context.object.scale = (1.5,) * 3

        passes_aov = get_render_passes_aov(bpy.context)
        passes_aov.enable = True
        passes_aov.transparent = True

        aov_name = 'default'

        # enable only pass under test
        for i, item in enumerate(passes_aov.render_passes_items):
            passes_aov.passesStates[i] = aov_name == item[0]

        with render_image_check_fixture.set_expected('aov/transparent/' + aov_name,
                                                     aov=aov_name, use_alpha=True):
            pass

        aov_name = 'shading_normal'

        # enable only pass under test
        for i, item in enumerate(passes_aov.render_passes_items):
            passes_aov.passesStates[i] = aov_name == item[0]

        with render_image_check_fixture.set_expected('aov/transparent/' + aov_name,
                                                     aov=aov_name, use_alpha=True):
            pass


class TestPerf:
    @pytest.mark.skipif(not pytest.config.option.render_quickest,
                        reason='running this test in quickest mode because it tests raw thread interop(not image render)')
    @pytest.mark.parametrize('i', range(100))
    def test_fixture_speed(self, i, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected(None):
            pass

    @pytest.mark.skip()
    def test_image_load(self, tmpdir_factory):
        render_device = rprblender.render.get_render_device()
        context = render_device.context

        for i in range(10):
            path = str(tmpdir_factory.mktemp('textures').join('image_texture%d.png' % i))
            create_color_fill_image(path, (1, 0, 0), (2048,) * 2)

            rprblender.core.image.create_core_image_from_image_file_via_blender(context, path, False)

    @pytest.mark.skipif(condition=not pytest.config.option.perf, reason='this is for simple profiling of export code')
    def test_exr(self):
        import rprblender.render.scene
        import rprblender.sync
        scene = bpy.context.scene
        render_device = rprblender.render.get_render_device(is_production=True),
        scene_synced = rprblender.sync.SceneSynced(render_device, scene.rpr.render)

        for i in range(10):
            path = None
            assert path, "set path to an .exr image"
            scene_synced._make_core_environment_light(path)


import rprblender.material_browser


class TestImportMaterialOperator:
    def test_simple(self):
        context = bpy.context

        override = context.copy()
        override.update({
            "material": context.object.active_material
            , "screen": context.screen
            , "scene": context.scene
            , "active_object": context.object
            , "blend_data": bpy.data
            , "region": context.region
            , "node": []  # i dont know what this should point at
            , "window": context.window
        })
        mlp = context.window_manager.rpr_material_library_properties
        mlp.categories
        mlp.materials
        bpy.ops.rpr.import_material_operator(override)


import rprblender.converter.cycles_converter


class TestCyclesConvertBase:
    def convert_material(self):
        # assert {'FINISHED'} == bpy.ops.rpr.convert_cycles_material(self.override)
        self.converter = rprblender.converter.cycles_converter.CyclesMaterialConverter()
        self.converter.convert(self.material)
        assert not self.converter.error

    def find_rpr_output(self, material):
        return node_editor.find_node(material, node_editor.shader_node_output_name)

    def find_cycles_output(self, material):
        return node_editor.find_node(material, node_editor.shader_node_cycles_output_name)

    def create_material_with_cycles_output(self):
        context = bpy.context
        self.override = context.copy()
        self.override.update({
            "material": None
            , "screen": context.screen
            , "scene": context.scene
            , "active_object": context.object
            , "blend_data": bpy.data
            , "region": context.region
            , "node": []  # i dont know what this should point at
            , "window": context.window
        })
        material = bpy.data.materials.new("test")
        self.override["material"] = material
        self.material = material
        material.use_nodes = True
        self.tree = material.node_tree
        self.tree.nodes.new('ShaderNodeOutputMaterial')
        bpy.context.object.active_material = material
        return material

    def create_cycles_surface_material(self, material, idname, out_socket_name):
        cycles_output = self.find_cycles_output(material)
        cycles_refraction = self.tree.nodes.new(idname)
        self.tree.links.new(cycles_refraction.outputs[out_socket_name], cycles_output.inputs['Surface'])
        return cycles_refraction

    def assign_cycles_normalmap(self, cycles_node, input_socket_name):
        image = bpy_extras.image_utils.load_image(testdata.get_path('../data/material_normalmap_normals.png'))
        cycles_teximage = self.tree.nodes.new('ShaderNodeTexImage')
        cycles_teximage.image = image
        cycles_teximage.color_space = 'NONE'
        cycles_normalmap = self.tree.nodes.new('ShaderNodeNormalMap')
        cycles_normalmap.inputs['Strength'].default_value = 0.5
        self.tree.links.new(cycles_teximage.outputs['Color'], cycles_normalmap.inputs['Color'])
        self.tree.links.new(cycles_normalmap.outputs['Normal'], cycles_node.inputs[input_socket_name])

    def assign_cycles_bumpmap(self, cycles_node, input_socket_name):
        image = bpy_extras.image_utils.load_image(testdata.get_path('../data/bumpmap.png'))
        cycles_teximage = self.tree.nodes.new('ShaderNodeTexImage')
        cycles_teximage.image = image
        cycles_teximage.color_space = 'NONE'
        cycles_bump = self.tree.nodes.new('ShaderNodeBump')
        cycles_bump.inputs['Strength'].default_value = 0.5
        self.tree.links.new(cycles_teximage.outputs['Color'], cycles_bump.inputs['Height'])
        self.tree.links.new(cycles_bump.outputs['Normal'], cycles_node.inputs[input_socket_name])

        cycles_bump.location = (cycles_node.location[0] - 200, cycles_node.location[1])

        cycles_teximage.location = (cycles_bump.location[0] - 200, cycles_bump.location[1])
        return cycles_bump

    def create_cycles_diffuse(self, color, roughness=0):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')
        cycles_diffuse.inputs['Color'].default_value = color
        cycles_diffuse.inputs['Roughness'].default_value = roughness
        return material, cycles_diffuse

    def create_cycles_emission(self, color, strength):
        material = self.create_material_with_cycles_output()
        cycles_emission = self.create_cycles_surface_material(material, 'ShaderNodeEmission', 'Emission')
        cycles_emission.inputs['Color'].default_value = color
        cycles_emission.inputs['Strength'].default_value = strength
        return material

    def create_cycles_rgb(self, color):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        cycles_rgb = self.tree.nodes.new('ShaderNodeRGB')
        self.tree.links.new(cycles_rgb.outputs['Color'], cycles_diffuse.inputs['Color'])
        cycles_rgb.outputs['Color'].default_value = color
        return material

    def create_cycles_mix_shader(self, color1, color2, weight):
        material = self.create_material_with_cycles_output()
        cycles_mix = self.create_cycles_surface_material(material, 'ShaderNodeMixShader', 'Shader')
        cycles_mix.inputs['Fac'].default_value = weight

        cycles_node1 = self.tree.nodes.new('ShaderNodeBsdfDiffuse')
        self.tree.links.new(cycles_node1.outputs['BSDF'], cycles_mix.inputs[1])
        cycles_node1.inputs['Color'].default_value = color1

        cycles_node2 = self.tree.nodes.new('ShaderNodeBsdfDiffuse')
        self.tree.links.new(cycles_node2.outputs['BSDF'], cycles_mix.inputs[2])
        cycles_node2.inputs['Color'].default_value = color2
        return material

    def create_cycles_add_shader(self, color1, color2):
        material = self.create_material_with_cycles_output()
        cycles_mix = self.create_cycles_surface_material(material, 'ShaderNodeAddShader', 'Shader')

        cycles_node1 = self.tree.nodes.new('ShaderNodeBsdfDiffuse')
        self.tree.links.new(cycles_node1.outputs['BSDF'], cycles_mix.inputs[0])
        cycles_node1.inputs['Color'].default_value = color1

        cycles_node2 = self.tree.nodes.new('ShaderNodeBsdfDiffuse')
        self.tree.links.new(cycles_node2.outputs['BSDF'], cycles_mix.inputs[1])
        cycles_node2.inputs['Color'].default_value = color2
        return material

    def create_cycles_transparent(self, color, weight):
        material = self.create_material_with_cycles_output()
        cycles_mix = self.create_cycles_surface_material(material, 'ShaderNodeMixShader', 'Shader')
        cycles_mix.inputs['Fac'].default_value = weight

        transparent_node = self.tree.nodes.new('ShaderNodeBsdfTransparent')
        self.tree.links.new(transparent_node.outputs['BSDF'], cycles_mix.inputs[1])
        transparent_node.inputs['Color'].default_value = color

        diffuse_node = self.tree.nodes.new('ShaderNodeBsdfDiffuse')
        self.tree.links.new(diffuse_node.outputs['BSDF'], cycles_mix.inputs[2])
        diffuse_node.inputs['Color'].default_value = (1, 1, 1, 1)
        return material

    math_vector_operator = ['ADD', 'SUBTRACT', 'NORMALIZE', 'CROSS_PRODUCT', 'DOT_PRODUCT', 'AVERAGE']
    math_vector_rpr_operator = ['ADD', 'SUB', 'NORMALIZE3', 'CROSS3', 'DOT3', 'AVERAGE']

    def create_cycles_vector_math(self, op, val1=(1, 0, 1), val2=(1, 1, 0)):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        math_node = self.tree.nodes.new('ShaderNodeVectorMath')
        self.tree.links.new(math_node.outputs['Vector'], cycles_diffuse.inputs['Color'])

        math_node.operation = op
        math_node.inputs[0].default_value = val1
        math_node.inputs[1].default_value = val2
        return material

    separate_component_rgb = ['R', 'G', 'B']
    separate_component_xyz = ['X', 'Y', 'Z']

    def create_cycles_separate_rgb(self, color, component):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        cycles_separate_rgb = self.tree.nodes.new('ShaderNodeSeparateRGB')
        self.tree.links.new(cycles_separate_rgb.outputs[component], cycles_diffuse.inputs['Color'])
        cycles_separate_rgb.inputs['Image'].default_value = color
        return material

    def create_cycles_separate_xyz(self, vector, component):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        cycles_separate_xyz = self.tree.nodes.new('ShaderNodeSeparateXYZ')
        self.tree.links.new(cycles_separate_xyz.outputs[component], cycles_diffuse.inputs['Color'])
        cycles_separate_xyz.inputs['Vector'].default_value = vector
        return material

    def create_cycles_diffuse_with_checker_simple(self):
        cycles_checker, material = self.create_cycles_diffuse_with_checker_base('Fac')
        cycles_checker.inputs['Scale'].default_value = 8  # to match default scaling of RPR Checker
        return material, cycles_checker

    def create_cycles_diffuse_with_checker_base(self, checker_output_socket_name):
        material = self.create_material_with_cycles_output()
        cycles_output = self.find_cycles_output(material)
        # create diffuse
        cycles_diffuse = self.tree.nodes.new('ShaderNodeBsdfDiffuse')
        cycles_diffuse.location = (cycles_output.location[0] - 200, cycles_output.location[1])
        self.tree.links.new(cycles_diffuse.outputs['BSDF'], cycles_output.inputs['Surface'])
        cycles_checker = self.tree.nodes.new('ShaderNodeTexChecker')
        cycles_checker.location = (cycles_diffuse.location[0] - 200, cycles_diffuse.location[1])
        self.tree.links.new(cycles_checker.outputs[checker_output_socket_name], cycles_diffuse.inputs['Color'])
        return cycles_checker, material

    def create_cycles_diffuse_with_noise_base(self, checker_output_socket_name):
        material = self.create_material_with_cycles_output()
        cycles_output = self.find_cycles_output(material)
        # create diffuse
        cycles_diffuse = self.tree.nodes.new('ShaderNodeBsdfDiffuse')
        cycles_diffuse.location = (cycles_output.location[0] - 200, cycles_output.location[1])
        self.tree.links.new(cycles_diffuse.outputs['BSDF'], cycles_output.inputs['Surface'])
        cycles_noise = self.tree.nodes.new('ShaderNodeTexNoise')
        cycles_noise.location = (cycles_diffuse.location[0] - 200, cycles_diffuse.location[1])
        self.tree.links.new(cycles_noise.outputs[checker_output_socket_name], cycles_diffuse.inputs['Color'])
        return cycles_noise, material

    def create_cycles_diffuse_with_input_from_image(self, output_socket_name, image):
        material = self.create_material_with_cycles_output()
        cycles_output = self.find_cycles_output(material)
        # create diffuse
        cycles_diffuse = self.tree.nodes.new('ShaderNodeBsdfDiffuse')
        cycles_diffuse.location = (cycles_output.location[0] - 200, cycles_output.location[1])
        self.tree.links.new(cycles_diffuse.outputs['BSDF'], cycles_output.inputs['Surface'])
        cycles_teximage = self.tree.nodes.new('ShaderNodeTexImage')
        cycles_teximage.location = (cycles_diffuse.location[0] - 200, cycles_diffuse.location[1])
        cycles_teximage.image = image
        self.tree.links.new(cycles_teximage.outputs[output_socket_name], cycles_diffuse.inputs['Color'])
        return material

    def create_cycles_glass(self, color, roughness, ior):
        material = self.create_material_with_cycles_output()
        cycles_glass = self.create_cycles_surface_material(material, 'ShaderNodeBsdfGlass', 'BSDF')
        cycles_glass.inputs['Color'].default_value = color
        cycles_glass.inputs['Roughness'].default_value = roughness
        cycles_glass.inputs['IOR'].default_value = ior
        image = bpy_extras.image_utils.load_image(testdata.get_path('../data/material_normalmap_normals.png'))
        cycles_normalmap = self.tree.nodes.new('ShaderNodeNormalMap')
        cycles_normalmap.location = (cycles_glass.location[0] - 200, cycles_glass.location[1])
        cycles_teximage = self.tree.nodes.new('ShaderNodeTexImage')
        cycles_teximage.location = (cycles_normalmap.location[0] - 400, cycles_normalmap.location[1])
        cycles_teximage.image = image
        cycles_teximage.color_space = 'NONE'
        self.tree.links.new(cycles_teximage.outputs['Color'], cycles_normalmap.inputs['Color'])
        self.tree.links.new(cycles_normalmap.outputs['Normal'], cycles_glass.inputs['Normal'])
        return material

    def create_cycles_refraction(self, color, roughness, ior):
        material = self.create_material_with_cycles_output()
        cycles_refraction = self.create_cycles_surface_material(material, 'ShaderNodeBsdfRefraction', 'BSDF')
        cycles_refraction.inputs['Color'].default_value = color
        cycles_refraction.inputs['Roughness'].default_value = roughness
        cycles_refraction.inputs['IOR'].default_value = ior
        self.assign_cycles_normalmap(cycles_refraction, 'Normal')
        return material

    def create_cycles_glossy(self, color, roughness):
        material = self.create_material_with_cycles_output()

        cycles_glossy = self.create_cycles_surface_material(material, 'ShaderNodeBsdfGlossy', 'BSDF')
        cycles_glossy.inputs['Color'].default_value = color
        cycles_glossy.inputs['Roughness'].default_value = roughness
        self.assign_cycles_normalmap(cycles_glossy, 'Normal')

        return material

    math_operator = ['ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'SINE', 'COSINE', 'TANGENT', 'ARCSINE', 'ARCCOSINE',
                     'ARCTANGENT', 'POWER', 'MODULO', 'ABSOLUTE', 'MINIMUM', 'MAXIMUM', 'ROUND']
    math_rpr_operator = ['ADD', 'SUB', 'MUL', 'DIV', 'SIN', 'COS', 'TAN', 'ASIN', 'ACOS', 'ATAN', 'POW', 'MOD', 'ABS',
                         'MIN', 'MAX', 'FLOOR']

    def create_cycles_math(self, op, val1, val2, clamp):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        math_node = self.tree.nodes.new('ShaderNodeMath')
        self.tree.links.new(math_node.outputs['Value'], cycles_diffuse.inputs['Color'])

        math_node.operation = op
        math_node.use_clamp = clamp
        math_node.inputs[0].default_value = val1
        math_node.inputs[1].default_value = val2
        return material

    def create_cycles_mix_value(self, color1, color2, weight):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        cycles_mix = self.tree.nodes.new('ShaderNodeMixRGB')
        self.tree.links.new(cycles_mix.outputs['Color'], cycles_diffuse.inputs['Color'])
        cycles_mix.inputs['Fac'].default_value = weight

        cycles_mix.inputs['Color1'].default_value = color1

        cycles_rgb = self.tree.nodes.new('ShaderNodeRGB')
        self.tree.links.new(cycles_rgb.outputs['Color'], cycles_mix.inputs['Color2'])
        cycles_rgb.outputs['Color'].default_value = color2
        return material

    def create_cycles_combine_xyz(self, x, y, z):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        cycles_combine = self.tree.nodes.new('ShaderNodeCombineXYZ')
        self.tree.links.new(cycles_combine.outputs['Vector'], cycles_diffuse.inputs['Color'])
        cycles_combine.inputs['X'].default_value = x
        cycles_combine.inputs['Y'].default_value = y
        cycles_combine.inputs['Z'].default_value = z
        return material

    def create_cycles_combine_rgb(self, r, g, b):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        cycles_combine = self.tree.nodes.new('ShaderNodeCombineRGB')
        self.tree.links.new(cycles_combine.outputs['Image'], cycles_diffuse.inputs['Color'])
        cycles_combine.inputs['R'].default_value = r
        cycles_combine.inputs['G'].default_value = g

        cycles_value = self.tree.nodes.new('ShaderNodeValue')
        self.tree.links.new(cycles_value.outputs['Value'], cycles_combine.inputs['B'])
        cycles_value.outputs['Value'].default_value = b
        return material

    def create_cycles_fresnel(self, ior):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        cycles_fresnel = self.tree.nodes.new('ShaderNodeFresnel')
        self.tree.links.new(cycles_fresnel.outputs['Fac'], cycles_diffuse.inputs['Color'])
        cycles_fresnel.inputs['IOR'].default_value = ior
        return material

    def create_cycles_subsurface(self, faloff, color, scale, radius, sharpness, texture_blur):
        material = self.create_material_with_cycles_output()
        cycles_glass = self.create_cycles_surface_material(material, 'ShaderNodeSubsurfaceScattering', 'BSSRDF')
        cycles_glass.inputs['Color'].default_value = color
        cycles_glass.inputs['Scale'].default_value = scale
        cycles_glass.inputs['Radius'].default_value = radius
        cycles_glass.inputs['Sharpness'].default_value = sharpness
        cycles_glass.inputs['Texture Blur'].default_value = texture_blur
        self.assign_cycles_normalmap(cycles_glass, 'Normal')
        return material

    def create_cycles_volume_scatter(self, color, density, anisotropy):
        material = self.create_material_with_cycles_output()
        cycles_output = self.find_cycles_output(material)
        cycles_volume_scatter = self.tree.nodes.new('ShaderNodeVolumeScatter')
        self.tree.links.new(cycles_volume_scatter.outputs['Volume'], cycles_output.inputs['Volume'])
        cycles_volume_scatter.inputs['Color'].default_value = color
        cycles_volume_scatter.inputs['Density'].default_value = density
        cycles_volume_scatter.inputs['Anisotropy'].default_value = anisotropy
        return material

    def create_cycles_volume_absorption(self, color, density):
        material = self.create_material_with_cycles_output()
        cycles_output = self.find_cycles_output(material)
        cycles_volume_scatter = self.tree.nodes.new('ShaderNodeVolumeAbsorption')
        self.tree.links.new(cycles_volume_scatter.outputs['Volume'], cycles_output.inputs['Volume'])
        cycles_volume_scatter.inputs['Color'].default_value = color
        cycles_volume_scatter.inputs['Density'].default_value = density
        return material

    tex_coord_output = ['Normal', 'UV']
    geometry_output = ['Normal', 'Incoming', 'Position']

    def create_cycles_tex_coord(self, type):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        cycles_tex_image = self.tree.nodes.new('ShaderNodeTexImage')
        self.tree.links.new(cycles_tex_image.outputs['Color'], cycles_diffuse.inputs['Color'])
        image = create_striped_gradients_image_packed(256, 256)
        cycles_tex_image.image = image
        cycles_tex_image.color_space = 'NONE'

        cycles_tex_coord = self.tree.nodes.new('ShaderNodeTexCoord')
        self.tree.links.new(cycles_tex_coord.outputs[type], cycles_tex_image.inputs['Vector'])
        return material

    def create_cycles_geometry(self, type):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        cycles_tex_coord = self.tree.nodes.new('ShaderNodeNewGeometry')
        self.tree.links.new(cycles_tex_coord.outputs[type], cycles_diffuse.inputs['Color'])
        return material

    def create_cycles_translucent(self, color):
        material = self.create_material_with_cycles_output()
        cycles_translucent = self.create_cycles_surface_material(material, 'ShaderNodeBsdfTranslucent', 'BSDF')
        cycles_translucent.inputs['Color'].default_value = color
        return material

    mapping_types = ['TEXTURE', 'POINT', 'VECTOR', 'NORMAL']

    def create_cycles_mapping(self, type, use_clamp):
        material = self.create_material_with_cycles_output()
        cycles_diffuse = self.create_cycles_surface_material(material, 'ShaderNodeBsdfDiffuse', 'BSDF')

        cycles_tex_image = self.tree.nodes.new('ShaderNodeTexImage')
        self.tree.links.new(cycles_tex_image.outputs['Color'], cycles_diffuse.inputs['Color'])
        image = create_striped_gradients_image_packed(256, 256)
        cycles_tex_image.image = image
        cycles_tex_image.color_space = 'NONE'

        cycles_mapping = self.tree.nodes.new('ShaderNodeMapping')
        cycles_mapping.scale = (2, 0.5, 1)
        cycles_mapping.translation = (0.5, 1, 0)
        cycles_mapping.vector_type = type
        if use_clamp:
            cycles_mapping.use_min = use_clamp
            cycles_mapping.min = (0.25, 0.25, 0.25)
            cycles_mapping.use_max = use_clamp
            cycles_mapping.max = (0.75, 0.75, 0.75)
        self.tree.links.new(cycles_mapping.outputs['Vector'], cycles_tex_image.inputs['Vector'])

        cycles_tex_coord = self.tree.nodes.new('ShaderNodeTexCoord')
        self.tree.links.new(cycles_tex_coord.outputs['UV'], cycles_mapping.inputs['Vector'])
        return material


class TestCyclesConvert(TestCyclesConvertBase):
    def test_diffuse(self):
        color = (0.5, 1, 0.25, 1)
        roughness = 0.5
        material, cycles_diffuse = self.create_cycles_diffuse(color, roughness)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        assert color == tuple(color_socket.default_value)
        assert not color_socket.is_linked

        roughness_socket = diffuse_node.inputs[diffuse_node.roughness_in]
        assert roughness == roughness_socket.default_value
        assert not roughness_socket.is_linked

    def test_diffuse_normal_noise(self):
        color = (0.5, 1, 0.25, 1)
        roughness = 0.5
        material, cycles_diffuse = self.create_cycles_diffuse(color, roughness)

        # self.assign_cycles_normalmap(cycles_diffuse, 'Normal')
        cycles_node = cycles_diffuse
        input_socket_name = 'Normal'
        cycles_tex = self.tree.nodes.new('ShaderNodeTexNoise')
        cycles_normalmap = self.tree.nodes.new('ShaderNodeNormalMap')
        cycles_normalmap.inputs['Strength'].default_value = 0.5
        self.tree.links.new(cycles_tex.outputs['Fac'], cycles_normalmap.inputs['Color'])
        self.tree.links.new(cycles_normalmap.outputs['Normal'], cycles_node.inputs[input_socket_name])

        self.convert_material()

    def test_diffuse_bump_noise(self):
        color = (0.5, 1, 0.25, 1)
        roughness = 0.5
        material, cycles_diffuse = self.create_cycles_diffuse(color, roughness)

        # self.assign_cycles_normalmap(cycles_diffuse, 'Normal')
        cycles_node = cycles_diffuse
        input_socket_name = 'Normal'
        cycles_tex = self.tree.nodes.new('ShaderNodeTexNoise')

        cycles_bump = self.tree.nodes.new('ShaderNodeBump')
        cycles_bump.inputs['Strength'].default_value = 0.5
        self.tree.links.new(cycles_tex.outputs['Fac'], cycles_bump.inputs['Height'])
        self.tree.links.new(cycles_bump.outputs['Normal'], cycles_node.inputs[input_socket_name])

        cycles_bump.location = (cycles_node.location[0] - 200, cycles_node.location[1])

        self.convert_material()

    def test_emmision(self):
        color = (0.5, 1, 0.25, 1)
        strength = 10
        material = self.create_cycles_emission(color, strength)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        emissive_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_emissive' == emissive_node.bl_idname

        color_socket = emissive_node.inputs[emissive_node.color_in]
        assert color == tuple(color_socket.default_value)
        assert not color_socket.is_linked

        intensity_socket = emissive_node.inputs[emissive_node.intensity_in]
        assert strength == intensity_socket.default_value
        assert not intensity_socket.is_linked

    def test_rgb(self):
        color = (0.25, 0.75, 0.75, 1)
        material = self.create_cycles_rgb(color)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        assert 1 == len(color_socket.links)

        rgb_node = color_socket.links[0].from_node
        assert 'rpr_input_node_constant' == rgb_node.bl_idname
        assert color == tuple(rgb_node.color)

    def test_mix_shader(self):
        weight = 0.75
        color1 = (1.0, 0.75, 0.25, 1)
        color2 = (0.25, 0.5, 1.0, 1)
        material = self.create_cycles_mix_shader(color1, color2, weight)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        blend_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_blend' == blend_node.bl_idname

        weight_socket = blend_node.inputs[blend_node.weight_in]
        assert weight == weight_socket.default_value
        assert not weight_socket.is_linked

        shader1_socket = blend_node.inputs[blend_node.shader1_in]
        assert 1 == len(shader1_socket.links)

        shader2_socket = blend_node.inputs[blend_node.shader2_in]
        assert 1 == len(shader2_socket.links)

    def test_add_shader(self):
        color1 = (1.0, 0.75, 0.25, 1)
        color2 = (0.25, 0.5, 1.0, 1)
        material = self.create_cycles_add_shader(color1, color2)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        blend_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_blend' == blend_node.bl_idname

        weight_socket = blend_node.inputs[blend_node.weight_in]
        assert 0.5 == weight_socket.default_value
        assert not weight_socket.is_linked

        shader1_socket = blend_node.inputs[blend_node.shader1_in]
        assert 1 == len(shader1_socket.links)

        shader2_socket = blend_node.inputs[blend_node.shader2_in]
        assert 1 == len(shader2_socket.links)

    def test_transparent(self):
        weight = 0.5
        color = (0.25, 1.0, 0.25, 1)
        material = self.create_cycles_transparent(color, weight)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        blend_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_blend' == blend_node.bl_idname

        shader1_socket = blend_node.inputs[blend_node.shader1_in]
        transparent_node = shader1_socket.links[0].from_node
        assert 'rpr_shader_node_transparent' == transparent_node.bl_idname

        color_socket = transparent_node.inputs[transparent_node.color_in]
        assert color == tuple(color_socket.default_value)
        assert not color_socket.is_linked

    @pytest.mark.parametrize('math_op', TestCyclesConvertBase.math_vector_operator)
    def test_vector_math(self, math_op):
        val1 = (1, 0, 1)
        val2 = (1, 1, 0)
        material = self.create_cycles_vector_math(math_op, val1, val2)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        math_node = color_socket.links[0].from_node
        assert 'rpr_arithmetics_node_math' == math_node.bl_idname

        # don't use RPRValueNode_Math.op_settings[op] for testing

        index = TestCyclesConvertBase.math_vector_operator.index(math_op)
        assert index >= 0 or index < len(TestCyclesConvertBase.math_vector_rpr_operator)
        rpr_op = TestCyclesConvertBase.math_vector_rpr_operator[index]

        if rpr_op == 'NORMALIZE3':
            assert math_node.inputs[0].enabled
            assert not math_node.inputs[1].enabled
            assert not math_node.inputs[2].enabled

            value_socket = math_node.inputs[0]
            assert (val1[0], val1[1], val1[2], 0) == tuple(value_socket.default_value)
        else:
            assert math_node.inputs[0].enabled
            assert math_node.inputs[1].enabled
            assert not math_node.inputs[2].enabled

            value1_socket = math_node.inputs[0]
            assert (val1[0], val1[1], val1[2], 0) == tuple(value1_socket.default_value)
            value2_socket = math_node.inputs[1]
            assert (val2[0], val2[1], val2[2], 0) == tuple(value2_socket.default_value)

    @pytest.mark.parametrize('component', TestCyclesConvertBase.separate_component_rgb)
    def test_separate_rgb(self, component):
        color = (0, 0.5, 1, 0)
        material = self.create_cycles_separate_rgb(color, component)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        assert 1 == len(color_socket.links)

        math_node = color_socket.links[0].from_node
        assert 'rpr_arithmetics_node_math' == math_node.bl_idname
        assert math_node.inputs[0].enabled
        assert not math_node.inputs[1].enabled
        assert not math_node.inputs[2].enabled
        assert math_node.type == 'color'
        value_socket = math_node.inputs[0]
        assert color == tuple(value_socket.default_value)

        if component == 'R':
            op = 'SELECT_X'
        elif component == 'G':
            op = 'SELECT_Y'
        elif component == 'B':
            op = 'SELECT_Z'
        else:
            assert False, 'unknown socket'

        assert math_node.op == op

    @pytest.mark.parametrize('component', TestCyclesConvertBase.separate_component_xyz)
    def test_separate_xyz(self, component):
        vector = (1, 0, 0.5)
        material = self.create_cycles_separate_xyz(vector, component)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        assert 1 == len(color_socket.links)

        math_node = color_socket.links[0].from_node
        assert 'rpr_arithmetics_node_math' == math_node.bl_idname
        assert math_node.inputs[0].enabled
        assert not math_node.inputs[1].enabled
        assert not math_node.inputs[2].enabled
        assert math_node.type == 'vector'
        value_socket = math_node.inputs[0]
        assert (vector[0], vector[1], vector[2], 0) == tuple(value_socket.default_value)

        if component == 'X':
            op = 'SELECT_X'
        elif component == 'Y':
            op = 'SELECT_Y'
        elif component == 'Z':
            op = 'SELECT_Z'
        else:
            assert False, 'unknown socket'

        assert math_node.op == op

    def test_checker_simple(self):
        cycles_checker, material = self.create_cycles_diffuse_with_checker_base('Fac')
        cycles_checker.inputs['Scale'].default_value = 8  # to match default scaling of RPR Checker

        self.convert_material()

        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        assert color_socket.is_linked
        checker_node = color_socket.links[0].from_node
        assert 'rpr_texture_node_checker' == checker_node.bl_idname

        mapping_socket = checker_node.inputs[checker_node.mapping_in]
        assert not mapping_socket.is_linked

    def test_checker_scale(self):
        cycles_checker, material = self.create_cycles_diffuse_with_checker_base('Fac')
        cycles_checker.inputs['Scale'].default_value = 5

        self.convert_material()

        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        diffuse_node = surface_socket.links[0].from_node
        color_socket = diffuse_node.inputs[diffuse_node.color_in]

        checker_node = color_socket.links[0].from_node
        mapping_socket = checker_node.inputs[checker_node.mapping_in]
        assert mapping_socket.is_linked
        mapping_node = checker_node.inputs[checker_node.mapping_in].links[0].from_node
        assert 'rpr_mapping_node' == mapping_node.bl_idname

        assert (0, 0) == tuple(mapping_node.inputs[mapping_node.offset_in].default_value)
        np.testing.assert_almost_equal(
            (5 / 8, 5 / 8), mapping_node.inputs[mapping_node.scale_in].default_value)

    def test_checker_mapping(self):
        cycles_checker, material = self.create_cycles_diffuse_with_checker_base('Fac')
        cycles_checker.inputs['Scale'].default_value = 5

        cycles_tex_coord = self.tree.nodes.new('ShaderNodeNewGeometry')
        self.tree.links.new(cycles_tex_coord.outputs['Position'], cycles_checker.inputs['Vector'])

        self.convert_material()

        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        diffuse_node = surface_socket.links[0].from_node
        color_socket = diffuse_node.inputs[diffuse_node.color_in]

        checker_node = color_socket.links[0].from_node
        mapping_socket = checker_node.inputs[checker_node.mapping_in]
        assert mapping_socket.is_linked

        scale_node = checker_node.inputs[checker_node.mapping_in].links[0].from_node
        assert 'rpr_arithmetics_node_math' == scale_node.bl_idname

        assert 'MUL' == scale_node.op
        assert 'float' == scale_node.type

        assert (0.625,) * 4 == tuple(scale_node.inputs[1].default_value)

        assert scale_node.inputs[0].is_linked

        lookup_graph = scale_node.inputs[0].links[0].from_node

        lookup = lookup_graph.inputs[0].links[0].from_node
        assert 'rpr_input_node_lookup' == lookup.bl_idname
        assert 'P' == lookup.type

    def test_checker_colors(self):
        cycles_checker, material = self.create_cycles_diffuse_with_checker_base('Color')

        cycles_checker.inputs['Scale'].default_value = 5
        cycles_checker.inputs['Color1'].default_value = (1, 0, 0, 1)
        cycles_checker.inputs['Color2'].default_value = (0, 1, 1, 1)

        self.convert_material()

        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        diffuse_node = surface_socket.links[0].from_node
        color_socket = diffuse_node.inputs[diffuse_node.color_in]

        blend_value_node = color_socket.links[0].from_node
        assert 'rpr_arithmetics_node_value_blend' == blend_value_node.bl_idname

        weight_socket = blend_value_node.inputs[blend_value_node.weight_in]
        assert weight_socket.is_linked
        checker_node = weight_socket.links[0].from_node

        value1_socket = blend_value_node.inputs[blend_value_node.value1_in]
        assert not value1_socket.is_linked
        assert (1, 0, 0, 1) == tuple(value1_socket.default_value)

        value2_socket = blend_value_node.inputs[blend_value_node.value2_in]
        assert not value2_socket.is_linked
        assert (0, 1, 1, 1) == tuple(value2_socket.default_value)

    def test_noise_simple(self):
        cycles_noise, material = self.create_cycles_diffuse_with_noise_base('Fac')
        cycles_noise.inputs['Scale'].default_value = 8  # to match default scaling of RPR Checker

        self.convert_material()

        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        assert color_socket.is_linked
        noise_node = color_socket.links[0].from_node
        assert 'rpr_texture_node_noise2d' == noise_node.bl_idname

        mapping_socket = noise_node.inputs[noise_node.mapping_in]
        assert mapping_socket.is_linked

        mapping_node = noise_node.inputs[noise_node.mapping_in].links[0].from_node
        assert 'rpr_mapping_node' == mapping_node.bl_idname

        assert (0, 0) == tuple(mapping_node.inputs[mapping_node.offset_in].default_value)
        np.testing.assert_almost_equal(
            (2, 2), mapping_node.inputs[mapping_node.scale_in].default_value)

    def test_image_simple(self, tmpdir_factory):
        material = self.create_cycles_diffuse_with_input_from_image('Color',
                                                                    create_striped_gradients_image_packed(256, 256))

        self.convert_material()

        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        assert color_socket.is_linked
        image_node = color_socket.links[0].from_node
        assert 'rpr_texture_node_image_map' == image_node.bl_idname

    def test_image_alpha(self, tmpdir_factory):
        image = create_striped_gradients_image_packed(256, 256)
        output_socket_name = 'Alpha'

        material = self.create_cycles_diffuse_with_input_from_image(output_socket_name, image)

        self.convert_material()

        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        assert color_socket.is_linked

        math_node = color_socket.links[0].from_node
        assert 'rpr_arithmetics_node_math' == math_node.bl_idname
        assert 'SELECT_W' == math_node.op

        op0 = math_node.inputs[0]
        assert op0.is_linked
        assert 'rpr_texture_node_image_map' == op0.links[0].from_node.bl_idname

        # image_node = color_socket.links[0].from_node
        # assert 'rpr_texture_node_image_map' == image_node.bl_idname

    def test_glass(self):

        material = self.create_cycles_glass(color=(0.5, 0.25, 0.75, 1), roughness=0.25, ior=2.0)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        blend_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_blend' == blend_node.bl_idname

        shader1_socket = blend_node.inputs[blend_node.shader1_in]
        refraction_node = shader1_socket.links[0].from_node
        assert 'rpr_shader_node_microfacet_refraction' == refraction_node.bl_idname

        shader2_socket = blend_node.inputs[blend_node.shader2_in]
        reflection_node = shader2_socket.links[0].from_node
        assert 'rpr_shader_node_microfacet' == reflection_node.bl_idname

        weight_socket = blend_node.inputs[blend_node.weight_in]
        fresnel_node = weight_socket.links[0].from_node
        assert 'rpr_fresnel_node' == fresnel_node.bl_idname

        # IOR converted to value node
        ior_node = fresnel_node.inputs[fresnel_node.ior_in].links[0].from_node
        assert 'rpr_input_node_value' == ior_node.bl_idname
        assert 2.0 == ior_node.default_value[0]
        assert ior_node.as_pointer() == refraction_node.inputs[refraction_node.ior_in].links[0].from_node.as_pointer()

        # Color converted to value node
        color_node = refraction_node.inputs[refraction_node.color_in].links[0].from_node
        assert (0.5, 0.25, 0.75, 1) == tuple(color_node.color)
        assert color_node.as_pointer() == reflection_node.inputs[reflection_node.color_in].links[
            0].from_node.as_pointer()

        roughness_node = refraction_node.inputs[refraction_node.roughness_in].links[0].from_node
        assert 0.25 == roughness_node.default_value[0]
        assert roughness_node.as_pointer() == reflection_node.inputs[reflection_node.roughness_in].links[
            0].from_node.as_pointer()

        # TODO: check normalmap
        # assert not fresnel_node.inputs[fresnel_node.normal_in].is_linked

        for normal_socket in [reflection_node.inputs[reflection_node.normal_in],
                              fresnel_node.inputs[reflection_node.normal_in],
                              refraction_node.inputs[refraction_node.normal_in],
                              ]:
            assert normal_socket.is_linked
            normal_node = normal_socket.links[0].from_node
            assert 'rpr_input_node_normalmap' == normal_node.bl_idname

            assert 'rpr_texture_node_image_map' == normal_node.inputs[normal_node.map_in].links[0].from_node.bl_idname

            #
            # color_socket = transparent_node.inputs[transparent_node.color_in]
            # assert color == tuple(color_socket.default_value)
            # assert not color_socket.is_linked

    def test_refraction(self):

        material = self.create_cycles_refraction(color=(0.5, 0.25, 0.75, 1), roughness=0.25, ior=2.0)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        refraction_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_microfacet_refraction' == refraction_node.bl_idname

        assert 2.0 == refraction_node.inputs[refraction_node.ior_in].default_value
        assert 0.25 == refraction_node.inputs[refraction_node.roughness_in].default_value
        assert (0.5, 0.25, 0.75, 1) == tuple(refraction_node.inputs[refraction_node.color_in].default_value)

        normal_socket = refraction_node.inputs[refraction_node.normal_in]

        assert normal_socket.is_linked
        normal_node = normal_socket.links[0].from_node
        assert 'rpr_input_node_normalmap' == normal_node.bl_idname

        assert 'rpr_texture_node_image_map' == normal_node.inputs[normal_node.map_in].links[0].from_node.bl_idname

    def test_glossy(self):

        material = self.create_cycles_glossy(color=(0.5, 0.25, 0.75, 1), roughness=0.25)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        reflection_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_microfacet' == reflection_node.bl_idname

        assert 0.25 == reflection_node.inputs[reflection_node.roughness_in].default_value
        assert (0.5, 0.25, 0.75, 1) == tuple(reflection_node.inputs[reflection_node.color_in].default_value)

        normal_socket = reflection_node.inputs[reflection_node.normal_in]

        assert normal_socket.is_linked
        normal_node = normal_socket.links[0].from_node
        assert 'rpr_input_node_normalmap' == normal_node.bl_idname

        assert 'rpr_texture_node_image_map' == normal_node.inputs[normal_node.map_in].links[0].from_node.bl_idname

        assert 0.5 == normal_node.inputs[normal_node.scale_in].default_value

    def test_glossy_bumpmap(self):

        color = (0.5, 0.25, 0.75, 1)
        roughness = 0.25
        bump_strength = 0.5
        bump_distance = 4.0

        material = self.create_material_with_cycles_output()

        cycles_glossy = self.create_cycles_surface_material(material, 'ShaderNodeBsdfGlossy', 'BSDF')
        cycles_glossy.inputs['Color'].default_value = color
        cycles_glossy.inputs['Roughness'].default_value = roughness
        cycles_bump = self.assign_cycles_bumpmap(cycles_glossy, 'Normal')

        cycles_bump.inputs['Strength'].default_value = bump_strength
        cycles_bump.inputs['Distance'].default_value = bump_distance

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        reflection_node = surface_socket.links[0].from_node

        normal_socket = reflection_node.inputs[reflection_node.normal_in]

        assert normal_socket.is_linked
        normal_node = normal_socket.links[0].from_node
        assert 'rpr_input_node_bumpmap' == normal_node.bl_idname

        # converted Scale value is Cycles's Strength*Distance for simplicity
        # and factor of 10 seems to match Cycles'
        assert 20.0 == normal_node.inputs[normal_node.scale_in].default_value

        assert 'rpr_texture_node_image_map' == normal_node.inputs[normal_node.map_in].links[0].from_node.bl_idname

    def test_refraction_defaults(self):
        material = self.create_material_with_cycles_output()
        cycles_output = self.find_cycles_output(material)
        cycles_refraction = self.tree.nodes.new('ShaderNodeBsdfRefraction')
        self.tree.links.new(cycles_refraction.outputs['BSDF'], cycles_output.inputs['Surface'])

        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        refraction_node = surface_socket.links[0].from_node

        normal_socket = refraction_node.inputs[refraction_node.normal_in]
        assert not normal_socket.is_linked

    def test_subsurface(self):

        material = self.create_cycles_subsurface(faloff='BURLEY',
                                                 color=(0.5, 0.25, 0.75, 1),
                                                 scale=0.25,
                                                 radius=(0.25, 0.5, 1.0),
                                                 sharpness=0.0,  # for cubic
                                                 texture_blur=0.0,
                                                 )

        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 0 == len(surface_socket.links)
        volume_socket = output_node.inputs[output_node.volume_in]
        assert 1 == len(volume_socket.links)

        sss_node = volume_socket.links[0].from_node
        assert 'rpr_shader_node_subsurface' == sss_node.bl_idname

        assert (0.5, 0.25, 0.75, 1) == tuple(sss_node.inputs[sss_node.subsurface_color_in].default_value)

        # check that scatter color is inverted input of cycles radius
        math_node = sss_node.inputs[sss_node.scatter_color_in].links[0].from_node
        assert (1,) * 4 == tuple(math_node.inputs[0].default_value)

        constant_node = math_node.inputs[1].links[0].from_node
        assert (0.25, 0.5, 1.0) == tuple(
            constant_node.default_value)[:3]

        # <bpy_struct, ShaderNodeSubsurfaceScattering("Subsurface Scattering")> ShaderNodeSubsurfaceScattering
        # [('Color', <class 'bpy_prop_array'>),
        # ('Scale', <class 'float'>),
        # ('Radius', <class 'bpy_prop_array'>),
        # ('Sharpness', <class 'float'>),
        # ('Texture Blur', <class 'float'>),
        # ('Normal', <class 'bpy_prop_array'>)]

    def test_volume_scatter(self):
        # <bpy_struct, ShaderNodeVolumeScatter("Volume Scatter")> ShaderNodeVolumeScatter
        # [('Color', <class 'bpy_prop_array'>), ('Density', <class 'float'>), ('Anisotropy', <class 'float'>)]
        # <bpy_struct, ShaderNodeVolumeAbsorption("Volume Absorption")> ShaderNodeVolumeAbsorption
        # [('Color', <class 'bpy_prop_array'>), ('Density', <class 'float'>)]

        material = self.create_cycles_volume_scatter(color=(0.5, 0.25, 0.75, 1),
                                                     density=16,
                                                     anisotropy=0.5, )

        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 0 == len(surface_socket.links)
        volume_socket = output_node.inputs[output_node.volume_in]
        assert 1 == len(volume_socket.links)

        volume_node = volume_socket.links[0].from_node
        assert 'rpr_shader_node_volume' == volume_node.bl_idname

        assert (0.5, 0.25, 0.75, 1) == tuple(volume_node.inputs[volume_node.scatter_color_in].default_value)
        assert 0.5 == volume_node.inputs[volume_node.scattering_direction_in].default_value
        assert 16.0 == volume_node.inputs[volume_node.density_in].default_value

        assert (1.0,) * 4 == tuple(volume_node.inputs[volume_node.transmission_color_in].default_value)
        assert (0, 0, 0, 1) == tuple(volume_node.inputs[volume_node.emission_color_in].default_value)

    def test_volume_absorption(self):
        # <bpy_struct, ShaderNodeVolumeScatter("Volume Scatter")> ShaderNodeVolumeScatter
        # [('Color', <class 'bpy_prop_array'>), ('Density', <class 'float'>), ('Anisotropy', <class 'float'>)]
        # <bpy_struct, ShaderNodeVolumeAbsorption("Volume Absorption")> ShaderNodeVolumeAbsorption
        # [('Color', <class 'bpy_prop_array'>), ('Density', <class 'float'>)]

        material = self.create_cycles_volume_absorption(color=(0.5, 0.25, 0.75, 1), density=16)

        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 0 == len(surface_socket.links)
        volume_socket = output_node.inputs[output_node.volume_in]
        assert 1 == len(volume_socket.links)

        volume_node = volume_socket.links[0].from_node
        assert 'rpr_shader_node_volume' == volume_node.bl_idname

        assert (0.5, 0.25, 0.75, 1) == tuple(volume_node.inputs[volume_node.transmission_color_in].default_value)
        assert 16.0 == volume_node.inputs[volume_node.density_in].default_value

        assert (0.0, 0.0, 0.0, 1) == tuple(volume_node.inputs[volume_node.scatter_color_in].default_value)
        assert (0, 0, 0, 1) == tuple(volume_node.inputs[volume_node.emission_color_in].default_value)

    @pytest.mark.parametrize('math_op', TestCyclesConvertBase.math_operator)
    def test_vector_math(self, math_op):
        val1 = 0.5
        val2 = 0.25
        material = self.create_cycles_math(math_op, val1, val2, False)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        math_node = color_socket.links[0].from_node
        assert 'rpr_arithmetics_node_math' == math_node.bl_idname

        index = TestCyclesConvertBase.math_operator.index(math_op)
        assert index >= 0 or index < len(TestCyclesConvertBase.math_operator)
        rpr_op = TestCyclesConvertBase.math_rpr_operator[index]
        assert rpr_op == math_node.op

        if math_op == 'ROUND':
            assert math_node.inputs[0].enabled
            assert not math_node.inputs[1].enabled
            assert not math_node.inputs[2].enabled

            value_socket = math_node.inputs[0]
            math_add = value_socket.links[0].from_node
            assert 'rpr_arithmetics_node_math' == math_add.bl_idname

            assert math_add.inputs[0].enabled
            assert math_add.inputs[1].enabled
            assert not math_add.inputs[2].enabled

            assert 'ADD' == math_add.op

            value1 = math_add.inputs[0].default_value
            assert (val1, val1, val1) == (value1[0], value1[1], value1[2])
            value2 = math_add.inputs[1].default_value
            assert (0.5, 0.5, 0.5) == (value2[0], value2[1], value2[2])

        elif math_op in ['SINE', 'COSINE', 'TANGENT', 'ARCSINE', 'ARCCOSINE', 'ARCTANGENT', 'ABSOLUTE']:
            assert math_node.inputs[0].enabled
            assert not math_node.inputs[1].enabled
            assert not math_node.inputs[2].enabled

            value = math_node.inputs[0].default_value
            assert (val1, val1, val1) == (value[0], value[1], value[2])
        else:
            assert math_node.inputs[0].enabled
            assert math_node.inputs[1].enabled
            assert not math_node.inputs[2].enabled

            value1 = math_node.inputs[0].default_value
            assert (val1, val1, val1) == (value1[0], value1[1], value1[2])
            value2 = math_node.inputs[1].default_value
            assert (val2, val2, val2) == (value2[0], value2[1], value2[2])

    def test_mix_values(self):
        weight = 0.25
        val1 = (1.0, 0, 0.25, 0)
        val2 = (0.25, 1.0, 0.5, 0)
        material = self.create_cycles_mix_value(val1, val2, weight)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        blend_node = color_socket.links[0].from_node
        assert 'rpr_arithmetics_node_value_blend' == blend_node.bl_idname

        weight_socket = blend_node.inputs[blend_node.weight_in]
        assert weight == weight_socket.default_value
        assert not weight_socket.is_linked

        value1_socket = blend_node.inputs[blend_node.value1_in]
        assert not value1_socket.is_linked
        assert val1 == tuple(value1_socket.default_value)

        value2_socket = blend_node.inputs[blend_node.value2_in]
        assert 1 == len(value2_socket.links)

        rgb_node = value2_socket.links[0].from_node
        assert 'rpr_input_node_constant' == rgb_node.bl_idname
        assert val2 == tuple(rgb_node.color)

    def test_combine_xyz(self):
        x = 10
        y = 1
        z = 0.25
        material = self.create_cycles_combine_xyz(x, y, z)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        math_node = color_socket.links[0].from_node
        assert 'rpr_arithmetics_node_math' == math_node.bl_idname
        assert 'COMBINE' == math_node.op
        assert 'float' == math_node.type

        value1_socket = math_node.inputs[0]
        assert (x, x, x, x) == tuple(value1_socket.default_value)

        value2_socket = math_node.inputs[1]
        assert (y, y, y, y) == tuple(value2_socket.default_value)

        value3_socket = math_node.inputs[2]
        assert (z, z, z, z) == tuple(value3_socket.default_value)

    def test_combine_rgb(self):
        r = 1
        g = 0.5
        b = 0.75
        material = self.create_cycles_combine_rgb(r, g, b)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        math_node = color_socket.links[0].from_node
        assert 'rpr_arithmetics_node_math' == math_node.bl_idname
        assert 'COMBINE' == math_node.op
        assert 'float' == math_node.type

        value1_socket = math_node.inputs[0]
        assert (r, r, r, r) == tuple(value1_socket.default_value)

        value2_socket = math_node.inputs[1]
        assert (g, g, g, g) == tuple(value2_socket.default_value)

        value3_socket = math_node.inputs[2]
        value_node = value3_socket.links[0].from_node
        assert 'rpr_input_node_value' == value_node.bl_idname
        assert (b, b, b, b) == tuple(value_node.default_value)
        assert 'float' == value_node.type

    def test_fresnel(self):
        ior = 2.0
        material = self.create_cycles_fresnel(ior)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        fresnel_node = color_socket.links[0].from_node
        assert 'rpr_fresnel_node' == fresnel_node.bl_idname

        ior_socket = fresnel_node.inputs[0]
        assert ior == ior_socket.default_value

    @pytest.mark.parametrize('tex_coord_out', TestCyclesConvertBase.tex_coord_output)
    def test_tex_coord(self, tex_coord_out):
        material = self.create_cycles_tex_coord(tex_coord_out)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname

        color_socket = diffuse_node.inputs[diffuse_node.color_in]
        image_tex_node = color_socket.links[0].from_node
        assert 'rpr_texture_node_image_map' == image_tex_node.bl_idname

        mapping_socket = image_tex_node.inputs['Mapping']
        lookup_node = mapping_socket.links[0].from_node
        assert 'rpr_input_node_lookup' == lookup_node.bl_idname

        if tex_coord_out == 'Normal':
            assert lookup_node.type == 'N'
        elif tex_coord_out == 'UV':
            assert lookup_node.type == 'UV'
        else:
            assert False

    @pytest.mark.parametrize('geometry_out', TestCyclesConvertBase.geometry_output)
    def test_geometry(self, geometry_out):
        material = self.create_cycles_geometry(geometry_out)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname
        color_socket = diffuse_node.inputs[diffuse_node.color_in]

        if geometry_out == 'Normal':
            lookup_node = color_socket.links[0].from_node
            assert 'rpr_input_node_lookup' == lookup_node.bl_idname
            assert lookup_node.type == 'N'
        elif geometry_out == 'Position':

            math_node = color_socket.links[0].from_node
            assert 'rpr_arithmetics_node_math' == math_node.bl_idname
            assert 'MUL' == math_node.op
            assert 'float' == math_node.type

            value1_socket = math_node.inputs[0]
            lookup_node = value1_socket.links[0].from_node
            assert 'rpr_input_node_lookup' == lookup_node.bl_idname
            assert lookup_node.type == 'P'

            value2_socket = math_node.inputs[1]
            assert (100, 100, 100, 100) == tuple(value2_socket.default_value)

        elif geometry_out == 'Incoming':
            math_node = color_socket.links[0].from_node
            assert 'rpr_arithmetics_node_math' == math_node.bl_idname
            assert 'MUL' == math_node.op
            assert 'float' == math_node.type

            value1_socket = math_node.inputs[0]
            lookup_node = value1_socket.links[0].from_node
            assert 'rpr_input_node_lookup' == lookup_node.bl_idname
            assert lookup_node.type == 'INVEC'

            value2_socket = math_node.inputs[1]
            assert (-1, -1, -1, -1) == tuple(value2_socket.default_value)

        else:
            assert False

    def test_translucent(self):
        color = (0.5, 1, 0.25, 1)
        material = self.create_cycles_translucent(color)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        translucent_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse_refraction' == translucent_node.bl_idname

        color_socket = translucent_node.inputs[translucent_node.color_in]
        assert color == tuple(color_socket.default_value)
        assert not color_socket.is_linked

    @pytest.mark.parametrize('mapping_type', TestCyclesConvertBase.mapping_types)
    def test_mapping(self, mapping_type):
        material = self.create_cycles_mapping(mapping_type, True)

        # convert
        self.convert_material()

        # check result
        output_node = self.find_rpr_output(material)
        surface_socket = output_node.inputs[output_node.shader_in]
        assert 1 == len(surface_socket.links)

        diffuse_node = surface_socket.links[0].from_node
        assert 'rpr_shader_node_diffuse' == diffuse_node.bl_idname
        color_socket = diffuse_node.inputs[diffuse_node.color_in]

        texture_node = color_socket.links[0].from_node
        assert 'rpr_texture_node_image_map' == texture_node.bl_idname
        input_socket = texture_node.inputs[texture_node.mapping_in]

        if mapping_type == 'NORMAL':
            normalize_node = input_socket.links[0].from_node
            assert 'NORMALIZE3' == normalize_node.op
            assert 'vector' == normalize_node.type
            assert 'rpr_arithmetics_node_math' == normalize_node.bl_idname
            input_socket = normalize_node.inputs[0]

        min_node = input_socket.links[0].from_node
        assert 'rpr_arithmetics_node_math' == min_node.bl_idname
        assert 'MIN' == min_node.op
        assert 'vector' == min_node.type
        input_socket = min_node.inputs[0]
        value2_socket = min_node.inputs[1]
        assert (0.75, 0.75, 0.75, 0) == tuple(value2_socket.default_value)

        max_node = input_socket.links[0].from_node
        assert 'rpr_arithmetics_node_math' == max_node.bl_idname
        assert 'MAX' == max_node.op
        assert 'vector' == max_node.type
        input_socket = max_node.inputs[0]
        value2_socket = max_node.inputs[1]
        assert (0.25, 0.25, 0.25, 0) == tuple(value2_socket.default_value)

        if mapping_type in ['TEXTURE', 'POINT']:
            add_node = input_socket.links[0].from_node
            assert 'rpr_arithmetics_node_math' == add_node.bl_idname
            assert 'ADD' == add_node.op
            assert 'vector' == add_node.type
            input_socket = add_node.inputs[0]
            value2_socket = add_node.inputs[1]
            val = (-0.25, -2.0, -0, 0) if mapping_type == 'TEXTURE' else (0.5, 1.0, 0, 0)
            assert val == tuple(value2_socket.default_value)

        mul_node = input_socket.links[0].from_node
        assert 'rpr_arithmetics_node_math' == mul_node.bl_idname
        assert 'MUL' == mul_node.op
        assert 'vector' == mul_node.type
        input_socket = mul_node.inputs[0]
        value2_socket = mul_node.inputs[1]
        val = (0.5, 2.0, 1, 0) if mapping_type in ['TEXTURE', 'NORMAL'] else (2.0, 0.5, 1, 0)
        assert val == tuple(value2_socket.default_value)

        lookup_node = input_socket.links[0].from_node
        assert 'rpr_input_node_lookup' == lookup_node.bl_idname
        assert 'UV' == lookup_node.type


########################################################################################################################

class TestCyclesConvertRender(TestCyclesConvertBase):
    def test_diffuse(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/diffuse'):
            generate_uv()
            color = (0.5, 1, 0.25, 1)
            self.create_cycles_diffuse(color)
            self.convert_material()

    def test_diffuse_bump_procedural(self, render_image_check_fixture: RenderImageCheck):
        color = (0.5, 1, 0.25, 1)
        roughness = 0.5
        material, cycles_diffuse = self.create_cycles_diffuse(color, roughness)

        cycles_node = cycles_diffuse
        input_socket_name = 'Normal'

        cycles_noise = self.tree.nodes.new('ShaderNodeTexNoise')
        cycles_noise.inputs['Scale'].default_value = 16

        cycles_checker = self.tree.nodes.new('ShaderNodeTexChecker')
        cycles_checker.location = (cycles_diffuse.location[0] - 200, cycles_diffuse.location[1])

        cycles_mul_node = self.tree.nodes.new('ShaderNodeMath')

        cycles_mul_node.operation = 'MULTIPLY'
        cycles_mul_node.use_clamp = False
        self.tree.links.new(cycles_checker.outputs['Fac'], cycles_mul_node.inputs[0])
        self.tree.links.new(cycles_noise.outputs['Fac'], cycles_mul_node.inputs[1])

        cycles_bump = self.tree.nodes.new('ShaderNodeBump')
        cycles_bump.inputs['Strength'].default_value = 0.5
        self.tree.links.new(cycles_mul_node.outputs['Value'], cycles_bump.inputs['Height'])

        self.tree.links.new(cycles_bump.outputs['Normal'], cycles_node.inputs[input_socket_name])

        cycles_bump.location = (cycles_node.location[0] - 200, cycles_node.location[1])

        with render_image_check_fixture.set_expected('converter/diffuse_bump_procedural'):
            generate_uv()
            self.convert_material()

    def test_emmision(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/emmision'):
            generate_uv()
            color = (1, 0.9, 0.1, 1)
            self.create_cycles_emission(color, 10)
            self.convert_material()

    def test_rgb(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/rgb'):
            generate_uv()
            color = (0.2, 0.6, 0.8, 1)
            self.create_cycles_rgb(color)
            self.convert_material()

    def test_mix(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/mix'):
            generate_uv()
            color1 = (1.0, 0.75, 0.25, 1)
            color2 = (0.25, 0.5, 1.0, 1)
            self.create_cycles_mix_shader(color1, color2, 0.75)
            self.convert_material()

    def test_add_shader(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/add_shader'):
            generate_uv()
            color1 = (1.0, 0.75, 0.25, 1)
            color2 = (0.25, 1.0, 1.0, 1)
            self.create_cycles_add_shader(color1, color2)
            self.convert_material()

    def test_transparent(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/transparent'):
            generate_uv()
            color = (0.25, 1.0, 0.25, 1)
            self.create_cycles_transparent(color, 0.6)
            self.convert_material()

    def test_glass(self, render_image_check_fixture: RenderImageCheck):
        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
        rpr_settings_env = bpy.context.scene.world.rpr_data.environment
        rpr_settings_env.ibl.color = (0.5, 0.5, 0.5)
        rpr_settings.global_illumination.use_clamp_irradiance = True
        rpr_settings.global_illumination.clamp_irradiance = 1.0

        with render_image_check_fixture.set_expected('converter/glass/normal'):
            generate_uv()
            self.create_cycles_glass(color=(0.6, 1.0, 0.9, 1), roughness=0.1, ior=1.51)
            self.convert_material()

    def test_refraction(self, render_image_check_fixture: RenderImageCheck):
        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
        rpr_settings_env = bpy.context.scene.world.rpr_data.environment
        rpr_settings_env.ibl.color = (0.5, 0.5, 0.5)
        rpr_settings.global_illumination.use_clamp_irradiance = True
        rpr_settings.global_illumination.clamp_irradiance = 1.0

        with render_image_check_fixture.set_expected('converter/refraction/normal'):
            generate_uv()
            self.create_cycles_refraction(color=(0.6, 1.0, 0.9, 1), roughness=0.1, ior=1.51)
            self.convert_material()

    def test_glossy(self, render_image_check_fixture: RenderImageCheck):
        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
        rpr_settings_env = bpy.context.scene.world.rpr_data.environment
        rpr_settings_env.ibl.color = (0.5, 0.5, 0.5)
        rpr_settings.global_illumination.use_clamp_irradiance = True
        rpr_settings.global_illumination.clamp_irradiance = 1.0

        with render_image_check_fixture.set_expected('converter/glossy/normal'):
            generate_uv()
            self.create_cycles_glossy(color=(0.6, 1.0, 0.9, 1), roughness=0.25)
            self.convert_material()

    def test_glossy_bump(self, render_image_check_fixture: RenderImageCheck):
        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
        rpr_settings_env = bpy.context.scene.world.rpr_data.environment
        rpr_settings_env.ibl.color = (0.5, 0.5, 0.5)
        rpr_settings.global_illumination.use_clamp_irradiance = True
        rpr_settings.global_illumination.clamp_irradiance = 1.0

        with render_image_check_fixture.set_expected('converter/glossy/bump'):
            generate_uv()

            color = (0.6, 1.0, 0.9, 1)
            roughness = 0.25
            bump_strength = 0.5
            bump_distance = 0.2

            material = self.create_material_with_cycles_output()

            cycles_glossy = self.create_cycles_surface_material(material, 'ShaderNodeBsdfGlossy', 'BSDF')
            cycles_glossy.inputs['Color'].default_value = color
            cycles_glossy.inputs['Roughness'].default_value = roughness
            cycles_bump = self.assign_cycles_bumpmap(cycles_glossy, 'Normal')

            cycles_bump.inputs['Strength'].default_value = bump_strength
            cycles_bump.inputs['Distance'].default_value = bump_distance

            self.convert_material()

    def test_volume_scatter(self, render_image_check_fixture: RenderImageCheck):
        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
        rpr_settings_env = bpy.context.scene.world.rpr_data.environment
        rpr_settings_env.ibl.color = (0.5, 0.5, 0.5)
        rpr_settings.global_illumination.use_clamp_irradiance = True
        rpr_settings.global_illumination.clamp_irradiance = 1.0

        with render_image_check_fixture.set_expected('converter/volume/scatter'):
            generate_uv()
            self.create_cycles_volume_scatter(color=(0.2, 0.5, 0.9, 1), density=5, anisotropy=-0.5)
            self.convert_material()

    def test_volume_absorption(self, render_image_check_fixture: RenderImageCheck):
        rpr_settings = bpy.context.scene.rpr.render  # type: rprblender.properties.RenderSettings
        rpr_settings_env = bpy.context.scene.world.rpr_data.environment
        rpr_settings_env.ibl.color = (0.5, 0.5, 0.5)
        rpr_settings.global_illumination.use_clamp_irradiance = True
        rpr_settings.global_illumination.clamp_irradiance = 1.0

        with render_image_check_fixture.set_expected('converter/volume/absorption'):
            generate_uv()
            self.create_cycles_volume_absorption(color=(0.2, 0.5, 0.9, 1), density=5)
            self.convert_material()

    @pytest.mark.parametrize('math_op', TestCyclesConvertBase.math_vector_operator)
    def test_vector_math(self, math_op, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/vector_math/' + math_op.lower()):
            generate_uv()
            self.create_cycles_vector_math(math_op)
            self.convert_material()

    @pytest.mark.parametrize('component', TestCyclesConvertBase.separate_component_rgb)
    def test_separate_rgb(self, component, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/separate_rgb/separate_' + component.lower()):
            generate_uv()
            color = (0, 0.5, 1, 0)
            self.create_cycles_separate_rgb(color, component)
            self.convert_material()

    @pytest.mark.parametrize('component', TestCyclesConvertBase.separate_component_rgb)
    def test_separate_rgb_with_color(self, component, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/separate_rgb/separate_' + component.lower()):
            generate_uv()
            color = (0, 0.5, 1, 0)
            material = self.create_cycles_separate_rgb((0.5, 1, 0, 1), component)
            cycles_separate_rgb = node_editor.find_node(material, 'ShaderNodeSeparateRGB')
            cycles_rgb = self.tree.nodes.new('ShaderNodeRGB')
            self.tree.links.new(cycles_rgb.outputs['Color'], cycles_separate_rgb.inputs['Image'])
            cycles_rgb.outputs['Color'].default_value = color
            self.convert_material()

    @pytest.mark.parametrize('component', TestCyclesConvertBase.separate_component_xyz)
    def test_separate_xyz(self, component, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/separate_xyz/separate_' + component.lower()):
            generate_uv()
            vector = (1, 0, 0.5)
            self.create_cycles_separate_xyz(vector, component)
            self.convert_material()

    @pytest.mark.parametrize('math_op', TestCyclesConvertBase.math_operator)
    def test_math(self, math_op, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/math/' + math_op.lower()):
            generate_uv()
            self.create_cycles_math(math_op, 0.9, 0.7, False)
            self.convert_material()

    @pytest.mark.parametrize('math_op', TestCyclesConvertBase.math_operator)
    def test_math_with_clamp(self, math_op, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/math/' + math_op.lower() + '_clamp'):
            generate_uv()
            self.create_cycles_math(math_op, 0.9, 0.7, True)
            self.convert_material()

            # bpy.ops.wm.save_as_mainfile(filepath='c:\\test' + math_op.lower() + '.blend')

    def test_checker_simple(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/checker/simple'):
            generate_uv()
            self.create_cycles_diffuse_with_checker_simple()
            self.convert_material()

    def test_checker_colors(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/checker/colors'):
            generate_uv()
            cycles_checker, material = self.create_cycles_diffuse_with_checker_base('Color')
            cycles_checker.inputs['Scale'].default_value = 3
            cycles_checker.inputs['Color1'].default_value = (1, 0, 0, 1)
            cycles_checker.inputs['Color2'].default_value = (0, 1, 1, 1)
            self.convert_material()

    def test_checker_complex(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/checker/complex'):
            generate_uv()
            cycles_checker, material = self.create_cycles_diffuse_with_checker_base('Color')
            cycles_checker.inputs['Scale'].default_value = 3
            cycles_checker.inputs['Color1'].default_value = (1, 0, 0, 1)
            cycles_checker.inputs['Color2'].default_value = (0, 1, 1, 1)

            cycles_checker2 = self.tree.nodes.new('ShaderNodeTexChecker')
            cycles_checker2.location = (cycles_checker.location[0] - 200, cycles_checker.location[1])
            cycles_checker2.inputs['Scale'].default_value = 6
            self.tree.links.new(cycles_checker2.outputs['Color'], cycles_checker.inputs['Color1'])

            self.convert_material()

    def test_image_simple(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory):
        with render_image_check_fixture.set_expected('converter/image/simple'):
            generate_uv()
            self.create_cycles_diffuse_with_input_from_image(
                'Color', create_striped_gradients_image_packed(256, 256))

            self.convert_material()

    def test_image_alpha(self, render_image_check_fixture: RenderImageCheck, tmpdir_factory):
        with render_image_check_fixture.set_expected('converter/image/alpha'):
            generate_uv()
            self.create_cycles_diffuse_with_input_from_image(
                'Alpha', create_striped_gradients_image_packed(256, 256))

            self.convert_material()

    def test_mix_values(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/mix_values'):
            weight = 0.25
            color1 = (1.0, 0.75, 0.0, 0)
            color2 = (0.0, 0.25, 1.0, 0)
            generate_uv()
            self.create_cycles_mix_value(color1, color2, weight)
            self.convert_material()

    def test_combine_xyz(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/combine_xyz'):
            self.create_cycles_combine_xyz(10, 1, 0.5)
            self.convert_material()

    def test_combine_rgb(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/combine_rgb'):
            self.create_cycles_combine_rgb(0, 0.5, 1.0)
            self.convert_material()

    def test_fresnel(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/fresnel'):
            self.create_cycles_fresnel(2.0)
            self.convert_material()

    @pytest.mark.parametrize('tex_coord_out', TestCyclesConvertBase.tex_coord_output)
    def test_tex_coord(self, tex_coord_out, render_image_check_fixture: RenderImageCheck):
        generate_uv()
        with render_image_check_fixture.set_expected('converter/tex_coord/' + tex_coord_out.lower()):
            self.create_cycles_tex_coord(tex_coord_out)
            self.convert_material()

    @pytest.mark.parametrize('geometry_out', TestCyclesConvertBase.geometry_output)
    def test_geometry(self, geometry_out, render_image_check_fixture: RenderImageCheck):
        generate_uv()
        with render_image_check_fixture.set_expected('converter/geometry/' + geometry_out.lower()):
            self.create_cycles_geometry(geometry_out)
            self.convert_material()

    def test_translucent(self, render_image_check_fixture: RenderImageCheck):
        with render_image_check_fixture.set_expected('converter/translucent'):
            color = (0, 0.25, 1, 0)
            self.create_cycles_translucent(color)
            self.convert_material()

    @pytest.mark.parametrize('mapping_type', TestCyclesConvertBase.mapping_types)
    def test_mapping(self, mapping_type, render_image_check_fixture: RenderImageCheck):
        generate_uv()
        with render_image_check_fixture.set_expected('converter/mapping/' + mapping_type.lower()):
            self.create_cycles_mapping(mapping_type, False)
            self.convert_material()

    @pytest.mark.parametrize('mapping_type', TestCyclesConvertBase.mapping_types)
    def test_mapping_with_clamp(self, mapping_type, render_image_check_fixture: RenderImageCheck):
        generate_uv()
        with render_image_check_fixture.set_expected('converter/mapping/' + mapping_type.lower() + '_clamp'):
            self.create_cycles_mapping(mapping_type, True)
            self.convert_material()


class TestLog:
    def test_simple(self):
        import rprblender.logging
        rprblender.logging.info("hello!!!!!!!!!!!!!")


class TestExportRpr:

    def test_simple(self, tmpdir_factory):
        fpath = Path(str(tmpdir_factory.mktemp('rprexport').join('simple.rpr')))
        rprblender.ui.export_rpr_model(bpy.context, str(fpath))
        assert fpath.is_file()
