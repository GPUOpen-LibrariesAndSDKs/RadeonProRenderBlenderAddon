import itertools
import operator
import sys
import threading
import time
import weakref

import numpy as np

import rprblender.render
import rprblender.render.render_layers
import rprblender.render.device
from rprblender import helpers
from rprblender import logging
from rprblender.helpers import CallLogger
from rprblender import properties


call_logger = CallLogger(tag='render.scene')


class SceneRenderer:

    @property
    def context(self):
        return self.render_device.context


    def __init__(self, render_device, rs, is_production=False):
        self.render_device = render_device

        self.render_targets = None
        self.render_layers = None

        self.im_tile = None
        self.im_iteration = None
        self.im_prepared = {}
        self.iteration_in_progress = None
        self.cache_generated = False
        self.time_in_progress = None
        self.resolution = None  # type: tuple
        self.region = None
        self.time_render_start = None

        self.render_settings = rs
        self.production_render = False
        self.aov_settings = None
        self.tile_image = None
        self.has_shadowcatcher = False
        self.has_denoiser = False
        self.image_filter = None

        self.is_production = is_production
        self.used_iterations = 1
        self.iteration_divider = 1

        self.render_lock = threading.Lock()

    @call_logger.logged
    def __del__(self):
        if self.render_targets:
            self.render_targets.disable_aovs()

    @call_logger.logged
    def update_render_resolution(self, render_resolution):
        self.resolution = render_resolution
        if self.render_targets:
            self.render_targets.resize(*self.resolution)
            return

        self.render_targets = self.render_device.create_render_targets(*self.resolution)
        self.render_layers = rprblender.render.render_layers.RenderLayers(
            self.aov_settings, self.render_targets, self.is_production)
        # update transparent background
        self.context.set_parameter("transparentbackground", int(self.render_layers.alpha_combine))

        if self.has_shadowcatcher:
            self.render_targets.enable_shadow_catcher()

        if self.has_denoiser:
            self.render_targets.enable_image_filter(self.render_settings.denoiser)

    @call_logger.logged
    def update_render_region(self, render_region):
        self.region = render_region

    @call_logger.logged
    def update_aov(self, aov):
        self.aov_settings = aov
        if self.render_layers:
            self.render_layers.update(self.aov_settings)

    def render_proc(self):
        yield from self._render_proc()

    def _render_proc(self):
        rs = self.render_settings
        limits = rs.rendering_limits if self.is_production else helpers.get_user_settings().viewport_render_settings.limits

        #AA-Sample and Iteration limit recalculated based on: AMDBLENDER-659
        ##iterations = (#user set iterations) * (#user set samples) / #samples
        settings = helpers.get_device_settings(self.production_render)
        numGPUs = helpers.get_used_gpu_count(settings.gpu_states)
        samples_per_iteration = settings.samples
        if limits.enable:
            if 'ITER' == limits.type:
                if numGPUs > samples_per_iteration and self.is_production:
                    samples_per_iteration = numGPUs
                
                self.used_iterations = int(limits.iterations / samples_per_iteration)
                self.iteration_divider = 1 / samples_per_iteration
        
        time_start = time.perf_counter()
        self.time_render_start = time_start
        time_local_total = 0

        self.iteration_in_progress = None

        render_resolution = self.resolution

        if self.region is not None:
            render_region = np.uint32(np.concatenate(np.multiply(self.region, [[render_resolution[0]], [render_resolution[1]]])))
        else:
            render_region = None

        self.log_debug("render_proc: redraw", self.resolution)

        timestamp_operation_last = time.perf_counter()

        with rprblender.render.core_operations(raise_error=True):
            render_mode = rs.render_mode if self.production_render else helpers.get_user_settings().viewport_render_settings.render_mode
            self.context.set_parameter("rendermode", properties.RenderSettings.rendermode_remap[render_mode])
            self.context.set_parameter("iterations", samples_per_iteration)

            if rs.global_illumination.use_clamp_irradiance:
                self.context.set_parameter("radianceclamp", rs.global_illumination.clamp_irradiance)
            else:
                self.context.set_parameter("radianceclamp", sys.float_info.max)
            
            depth = 5
            depth_diffuse = 2
            depth_glossy = 3
            depth_shadow = 3
            depth_refraction = 3
            depth_glossy_refraction = 3
            if self.production_render:
                depth = rs.global_illumination.max_ray_depth
                depth_diffuse = rs.global_illumination.max_diffuse_depth
                depth_glossy = rs.global_illumination.max_glossy_depth
                depth_shadow = rs.global_illumination.max_shadow_depth
                depth_refraction = rs.global_illumination.max_refraction_depth
                depth_glossy_refraction = rs.global_illumination.max_glossy_refraction_depth
            else:
                # if preview use viewport overrides
                render_setting_overrides = helpers.get_user_settings().viewport_render_settings
                depth = render_setting_overrides.gi_settings.max_ray_depth
                depth_diffuse = render_setting_overrides.gi_settings.max_diffuse_depth
                depth_glossy = render_setting_overrides.gi_settings.max_glossy_depth
                depth_shadow = render_setting_overrides.gi_settings.max_diffuse_depth
                depth_refraction = render_setting_overrides.gi_settings.max_glossy_depth
                depth_glossy_refraction = render_setting_overrides.gi_settings.max_glossy_depth

            self.context.set_parameter("maxRecursion", depth)
            self.context.set_parameter("maxdepth.diffuse", depth_diffuse)
            self.context.set_parameter("maxdepth.glossy", depth_glossy)
            self.context.set_parameter("maxdepth.shadow", depth_shadow)
            self.context.set_parameter("maxdepth.refraction", depth_refraction)
            self.context.set_parameter("maxdepth.refraction.glossy", depth_glossy_refraction)

            # Convert milimeters to meters
            ray_epsilon = rs.global_illumination.ray_epsilon / 1000;
            self.context.set_parameter("raycastepsilon", ray_epsilon)

            self.context.set_parameter("imagefilter.type", properties.AntiAliasingSettings.filter_remap[rs.aa.filter])

            if rs.aa.filter in properties.AntiAliasingSettings.radius_params:
                self.context.set_parameter(properties.AntiAliasingSettings.radius_params[rs.aa.filter], rs.aa.radius)

        timstamp_operation = time.perf_counter()
        time_local_total += timstamp_operation - timestamp_operation_last
        timestamp_operation_last = timstamp_operation

        self.render_targets.clear_frame_buffers()

        for i in itertools.count():
            if limits.enable:
                if 'TIME' == limits.type:
                    if limits.time != 0 and limits.time <= (time.perf_counter() - time_start):
                        break
                elif 'ITER' == limits.type:
                    if self.used_iterations != 0 and self.used_iterations <= i:
                        break

            self.iteration_in_progress = i
            self.time_in_progress = time.perf_counter() - time_start
            self.log_debug('render_proc inner loop iteration')
            timestamp_operation_last = time.perf_counter()

            self.render_targets.render(render_region)

            self.cache_generated = True

            self.im_tile = self.tile_image
            self.im_iteration = i
            self.im_prepared.clear()
            
            timstamp_operation = time.perf_counter()
            time_local_total += timstamp_operation - timestamp_operation_last
            timestamp_operation_last = timstamp_operation
            self.log_debug('render_proc inner loop iteration done:', self.iteration_in_progress)

            yield False

            self.log_debug('render_proc inner loop iteration wait')

        self.log_debug('render_proc loops completed')

        self.log_debug('render_proc calc time:')
        time_delta = time.perf_counter() - time_start
        self.log_debug('render_proc calc time ok', time_delta, time_local_total)
        self.log_debug('render_proc completed in %.2fs, used %.2fs (%3.1f%% cpu)'
                       % (time_delta, time_local_total, 100 * time_local_total / time_delta))
        self.log_debug('render_proc log time ok')

    def log_debug(self, *args):
        logging.debug(*args, tag='render.proc')

    def get_image_tile(self):
        return self.im_tile

    @call_logger.logged
    def get_image(self, aov_name='default'):
        if aov_name in self.im_prepared:
            return self.im_prepared[aov_name]

        im = self.get_aov_image(aov_name)
        if im is None:
            return None

        opacity = self.get_aov_image('opacity') if self.render_layers.alpha_combine else None
        self.im_prepared[aov_name] = self.render_layers.prepare_image_by_layer(aov_name, im, opacity=opacity)

        return self.im_prepared.get(aov_name)

    @call_logger.logged
    def iter_images(self):
        opacity = self.get_aov_image('opacity') if self.render_layers.alpha_combine else None

        while True:
            aov_name = yield
            if not aov_name:
                return

            if aov_name in self.im_prepared:
                yield self.im_prepared[aov_name]

            im = self.get_aov_image(aov_name)
            if im is None:
                yield None

            self.im_prepared[aov_name] = self.render_layers.prepare_image_by_layer(aov_name, im, opacity=opacity)

            yield self.im_prepared.get(aov_name)

    def _get_image(self, aov_name, opacity):
        if not aov_name:
            return None

        if aov_name in self.im_prepared:
            return self.im_prepared[aov_name]

        im = self.get_aov_image(aov_name)
        if im is None:
            return None

        self.im_prepared[aov_name] = self.render_layers.prepare_image_by_layer(aov_name, im, opacity=opacity)

        return self.im_prepared.get(aov_name)

    @call_logger.logged
    def get_images(self):

        class PassesImages:
            """ Use class to get opacity once fo all passes, also lock render for duration of all image retrieval"""

            def __init__(self, scene_renderer):
                rprblender.render._lock.acquire()

                self.opacity = scene_renderer.get_aov_image('opacity') \
                    if scene_renderer.render_layers.alpha_combine else None
                self.scene_renderer = scene_renderer

            def __del__(self):
                rprblender.render._lock.release()

            def get_image(self, aov_name):
                return self.scene_renderer._get_image(aov_name, self.opacity)

        self.resolve()
        return PassesImages(weakref.proxy(self))

    def get_aov_image(self, aov_name):
        try:
            return self.render_targets.get_image(aov_name)
        except KeyError:
            logging.error("No such AOV %s" % aov_name, self, 'get_aov_image', tag='render.scene')
            return None

    def get_frame_buffer(self, aov_name):
        return self.render_targets.get_frame_buffer(aov_name)

    def resolve(self):
        self.render_targets.resolve()


class RenderThread(threading.Thread):

    def __init__(self):
        super().__init__()

        self.terminate_event = threading.Event()
        self.terminate_event.clear()

    def terminate(self):
        self.terminate_event.set()

    def run(self):
        logging.debug(self, 'run', tag='render.scene')
        while not self.terminate_event.wait(timeout=0.0001):
            self.renderer.render_proc()
        logging.debug(self, 'run complete', tag='render.scene')


class UpdateBlock:

    def __init__(self, value=None, has_value=True, equal=operator.eq):
        self.value = value
        self.has_value = has_value
        self.equal = equal

    def __str__(self):
        return "UpdateBlock(value=%s)" % (self.value,)

    @call_logger.logged
    def set_value(self, value):
        self.has_value = True
        self.value = value

    @call_logger.logged
    def pop_value(self):
        self.has_value = False
        return self.value

    def del_value(self):
        self.has_value = False


class UpdateData:

    def __init__(self):
        self.render_region = UpdateBlock(value=None, equal=np.array_equal)
        self.render_resolution = UpdateBlock(has_value=False, equal=np.array_equal)
        self.aov = UpdateBlock(has_value=False,
                               equal=lambda old, new: old is not None and old == new)
        self.render_camera = UpdateBlock(has_value=False, equal=lambda old, new: old is not None and old.is_same(new))

    def update_block(self, block, block_value_current, block_value_new):
        """ """
        equal = block.equal

        if block.has_value:
            # if update queued already has same data - skip it
            if equal(block.value, block_value_new):
                return

        # if value is already set - skip and clear update data
        if equal(block_value_current, block_value_new):
            # optimization - skip update value that was queued(but not applied yet) and is overriden by new value
            if block.has_value:
                block.del_value()
            return

        block.set_value(block_value_new)


class SceneRendererThreaded:

    def __init__(self, scene_renderer):
        self.scene_renderer = scene_renderer  # type: SceneRenderer

        self._need_scene_redraw = False

        self.thread = None  # type: RenderThread
        self.update_lock = threading.Lock()
        self.image_lock = threading.Lock()
        self.render_completed_event = threading.Event()

        self.update_data_lock = threading.Lock()
        self.update_data = UpdateData()
        self.render_resolution = None
        self.aov = None
        self.render_region = None
        self.render_camera = None

        self.scene_synced = None

    @call_logger.logged
    def __del__(self):
        self.stop()

    def _set_need_scene_redraw(self, value):

        self.render_completed_event.clear()
        self._need_scene_redraw = value

    need_scene_redraw = property(fset=_set_need_scene_redraw)

    def log_debug(self, *args):
        logging.debug(*args, tag='render.proc')

    def is_render_completed(self):
        # in case render crashed
        if not self.is_alive():
            return True
        return self.render_completed_event.is_set()

    def is_alive(self):
        # in case render crashed
        return self.thread.is_alive()

    sleep_delay_interactive = 0.01
    sleep_delay_noninteractive = 0.0

    def start(self):
        self.sleep_delay = self.sleep_delay_interactive
        self._start()

    def start_noninteractive(self):
        self.sleep_delay = self.sleep_delay_noninteractive
        self.need_scene_redraw = True
        self._start()

    @call_logger.logged
    def _start(self):
        self.stop_requested = False
        self.thread = RenderThread()
        self.thread.renderer = self
        self.thread.start()

    @call_logger.logged
    def stop(self):
        self.stop_requested = True
        if self.thread:
            self.thread.terminate()
            self.thread.join()
            self.thread = None #break reference cycle
            self.log_debug(self, 'thread stopped')

    def render_proc(self):
        render_iter = self.scene_renderer.render_proc()

        with self.update_lock:
            self.check_updates()

            if not self._need_scene_redraw:
                return
            self._need_scene_redraw = False
            self.render_completed_event.clear()

        while not self.stop_requested:
            try:
                with self.update_lock:
                    self.check_updates()

                    if self._need_scene_redraw:
                        self.log_debug('render_proc inner loop break - need_scene_redraw')
                        return
                    next(render_iter)

                    #s = cProfile.runctx("next(render_iter)", globals(), locals(), sort='cumulative')

                time.sleep(self.sleep_delay)
            except StopIteration:
                break

        logging.debug('render completed', tag='render.proc')
        self.render_completed_event.set()

    def render_proc_noninteractive(self):
        self.render_completed_event.clear()

        for _ in self.scene_renderer.render_proc():
            if self.stop_requested:
                break
            time.sleep(0)
        self.render_completed_event.set()

        logging.debug('render completed', tag='render.proc')

    def check_updates(self):
        with self.update_data_lock:
            if self.update_data.aov.has_value:
                self.aov = self.update_data.aov.pop_value()
                self.scene_renderer.update_aov(self.aov)
                self.need_scene_redraw = True

            if self.update_data.render_region.has_value:
                logging.debug('render_region changed to ', self.update_data.render_region,  tag='render.proc.update')
                self.render_region = self.update_data.render_region.pop_value()
                self.scene_renderer.update_render_region(self.render_region)
                self.need_scene_redraw = True

            if self.update_data.render_camera.has_value:
                logging.debug('render_camera changed to ', self.update_data.render_camera,  tag='render.proc.update')
                self._set_render_camera(self.update_data.render_camera.pop_value())
                self.need_scene_redraw = True

    @call_logger.logged
    def set_render_resolution(self, render_resolution):
        self.render_resolution = render_resolution
        self.scene_renderer.update_render_resolution(self.render_resolution)

    @call_logger.logged
    def update_render_resolution(self, render_resolution):
        self.update_block(self.update_data.render_resolution, self.render_resolution, render_resolution)

    @call_logger.logged
    def set_render_region(self, render_region):
        self.render_region = render_region
        self.scene_renderer.update_render_region(self.render_region)

    @call_logger.logged
    def update_render_region(self, render_region):
        self.update_block(self.update_data.render_region, self.render_region, render_region)

    @call_logger.logged
    def set_aov(self, aov):
        self.scene_renderer.update_aov(aov)

    @call_logger.logged
    def update_aov(self, aov):
        self.update_block(self.update_data.aov, self.aov, aov)

    def _set_render_camera(self, camera):
        self.render_camera = camera
        self.scene_synced.set_render_camera(camera)
        if self.scene_synced.camera_zoom is not None:
            self.scene_renderer.tile_image = (
                self.scene_synced.camera_zoom,
                self.scene_synced.camera_zoom)
        else:
            self.scene_renderer.tile_image = (1, 1)

    def update_render_camera(self, render_camera):
        self.update_block(self.update_data.render_camera, self.render_camera, render_camera)

    def update_block(self, block, block_value_current, block_value_new):
        with self.update_data_lock:
            self.update_data.update_block(block, block_value_current, block_value_new)

    def set_scene_synced(self, scene_synced):
        self.scene_synced = scene_synced
