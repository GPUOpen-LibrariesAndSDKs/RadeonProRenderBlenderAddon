import bpy
import threading
import time

from rprblender import config
from rprblender import utils
from .engine import Engine
from rprblender.properties import SyncError
from rprblender.export import world, camera, object, instance
from rprblender.utils import render_stamp
import pyrpr

from rprblender.utils import logging
log = logging.Log(tag='RenderEngine')


class RenderEngine(Engine):
    """ Final render engine """

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)

        self.render_lock = threading.Lock()
        self.is_synced = False
        self.render_event = threading.Event()
        self.finish_render = False
        self.render_layer_name = None

        self.render_iterations = 0
        self.current_iteration = 0
        self.render_time = 0
        self.current_render_time = 0
        self.render_update_samples = 1

        self.status_title = ""

    def notify_status(self, progress, info):
        self.rpr_engine.update_progress(progress)
        self.rpr_engine.update_stats(self.status_title, info)

        if config.notifier_log_calls:
            log("%d - %s" % (int(progress*100), info))

    def _do_update_result(self, result):
        while not self.finish_render:
            self.render_event.wait()
            self.render_event.clear()

            self.rpr_context.resolve()

            log("Updating render result")
            self.rpr_context.resolve_extras()
            self.set_render_result(result.layers[0].passes)
            self.rpr_engine.update_result(result)

            time.sleep(config.render_update_result_interval)

    def _do_render(self):
        ''' This is the main render loop.  
            Renders can be limited by max samples AND time.  Stop at whatever comes first
            A render will be N number of calls to rpr_context.render() 
            Where max_samples = N * samples_per_update 
            up to max time.  Note max samples is always > 0 '''

        self.finish_render = False
        try:
            self.current_iteration = 0
            time_begin = time.perf_counter()

            is_initial_render = True

            while True:
                if self.rpr_engine.test_break():
                    break

                self.current_render_time = time.perf_counter() - time_begin
                
                # if less that update_samples left, use the remainder
                update_samples = min(self.render_update_samples, self.render_iterations - self.current_iteration)
                
                # if initial render, use min_samples unless min is > max
                if is_initial_render:
                    update_samples = min(self.render_iterations, self.min_samples)
                    is_initial_render = False

                # we report time/iterations left as fractions if limit enabled
                render_time_string = "%.1f/%d" % (self.current_render_time, self.render_time) if self.render_time \
                                        else "%.1f" % self.current_render_time
                render_iterations_string = "%d/%d" % (self.current_iteration, self.render_iterations)

                # percent done is one of percent iterations or percent time so pick whichever is greater
                percent_iterations = self.current_iteration / self.render_iterations
                percent_time = self.current_render_time / self.render_time if self.render_time else 0
                percent_done = max(percent_iterations, percent_time)

                self.notify_status(percent_done,
                                       "Render Time: %s sec | Iteration: %s" %
                                       (render_time_string, render_iterations_string))
                self.rpr_context.set_parameter('iterations', update_samples)

                self.rpr_context.render()
                self.render_event.set()

                self.current_iteration += update_samples
                
                # stop at whichever comes first, max samples or max time if enabled
                if self.current_iteration >= self.render_iterations:
                    break
                
                if self.render_time:
                    if self.current_render_time >= self.render_time:
                        break

        finally:
            self.finish_render = True

    def _do_render_tile(self, n, m, samples):
        # TODO: This is a prototype of tile render
        #  currently it produces core error, needs to be checked

        self.finish_render = False
        try:
            self.rpr_context.set_parameter('iterations', samples)

            for i, tile in enumerate(utils.get_tiles(self.rpr_context.width, self.rpr_context.height, n, m)):
                if self.rpr_engine.test_break():
                    break

                self.notify_status(i / (n * m), "Tile: %d/%d" % (i, n * m))

                self.rpr_context.render(tile)

                self.render_event.set()
        finally:
            self.finish_render = True

    def render(self):
        if not self.is_synced:
            return

        log("Start render")

        self.notify_status(0, "Start render")

        result = self.rpr_engine.begin_result(0, 0, self.rpr_context.width, self.rpr_context.height, layer=self.render_layer_name)
        self.rpr_context.clear_frame_buffers()
        self.rpr_context.sync_auto_adapt_subdivision()
        self.render_event.clear()

        update_result_thread = threading.Thread(target=RenderEngine._do_update_result, args=(self, result))
        update_result_thread.start()

        self._do_render()
        # self._do_render_tile(20, 20)

        update_result_thread.join()

        if self.render_event.is_set():
            log('Getting final render result')
            self.rpr_context.resolve()
            self.rpr_context.resolve_extras()
            self.set_render_result(result.layers[0].passes)

        self.rpr_engine.end_result(result)
        self.notify_status(1, "Finish render")
        log('Finish render')

    def apply_render_stamp(self, image, channels):
        """
        Apply render stamp to image if enabled.
        :param image: source image
        :type image: np.Array
        :param channels: image depth in bytes per pixel
        :type channels: int
        :return: image with applied render stamp text if text allowed, unchanged source image otherwise
        :rtype: np.Array
        """
        if bpy.context.scene.rpr.use_render_stamp and render_stamp.render_stamp_supported:
            image = render_stamp.render_stamp(bpy.context.scene.rpr.render_stamp, image,
                                              self.rpr_context.width, self.rpr_context.height, channels,
                                              self.current_iteration, self.current_render_time)
        return image

    @staticmethod
    def is_object_allowed_for_motion_blur(obj: bpy.types.Object) -> bool:
        """Check if object could have motion blur effect: meshes, area lights and cameras can"""
        
        return obj.rpr.motion_blur and (obj.type == 'MESH' or (obj.type == 'LIGHT' and obj.data.type == 'AREA'))

    def collect_motion_blur_info(self, depsgraph):
        """
        Calculate motion blur velocities objects present in both current and previous frames(by frame_step)
        :param depsgraph: scene dependencies graph
        :return: dict of collected info for objects
        :rtype: dict of utils.MotionBlurInfo
        """
        if not depsgraph.scene.rpr.motion_blur:
            return {}

        motion_blur_info = {}

        prev_frame_matrices = {}
        next_frame_matrices = {}

        current_frame = depsgraph.scene.frame_current
        previous_frame = current_frame - depsgraph.scene.frame_step

        # collect previous frame matrices at start of the frame
        self.rpr_engine.frame_set(previous_frame, 0.0)

        # getting previous frame matrices
        for obj in self.depsgraph_objects(depsgraph):
            if self.is_object_allowed_for_motion_blur(obj):
                prev_frame_matrices[object.key(obj)] = obj.matrix_world.copy()

        for inst in self.depsgraph_instances(depsgraph):
            if self.is_object_allowed_for_motion_blur(inst.parent):
                prev_frame_matrices[instance.key(inst)] = inst.matrix_world.copy()

        # restore current frame and collect matrices at start of the frame
        self.rpr_engine.frame_set(current_frame, 0.0)

        # getting current frame matrices
        for obj in self.depsgraph_objects(depsgraph):
            if self.is_object_allowed_for_motion_blur(obj):
                next_frame_matrices[object.key(obj)] = obj.matrix_world.copy()

        for inst in self.depsgraph_instances(depsgraph):
            if self.is_object_allowed_for_motion_blur(inst.parent):
                next_frame_matrices[instance.key(inst)] = inst.matrix_world.copy()

        # calculating motion blur info
        for obj_key, prev in prev_frame_matrices.items():
            # User can animate the object's "motion_blur" flag.
            # Ignore such objects at ON-OFF/OFF-ON frames. Calculate difference for anything else
            this = next_frame_matrices.get(obj_key, None)
            if not this:
                continue

            # calculate velocities
            info = utils.MotionBlurInfo(prev, this)

            motion_blur_info[obj_key] = info

        return motion_blur_info

    def sync(self, depsgraph):
        log('Start syncing')

        # Preparations for syncing
        self.is_synced = False

        scene = depsgraph.scene
        view_layer = depsgraph.view_layer

        self.render_layer_name = view_layer.name
        self.status_title = "%s: %s" % (scene.name, self.render_layer_name)

        self.notify_status(0, "Start syncing")

        # Initializing rpr_context
        scene.rpr.init_rpr_context(self.rpr_context)
        self.rpr_context.resize(
            int(scene.render.resolution_x * scene.render.resolution_percentage / 100),
            int(scene.render.resolution_y * scene.render.resolution_percentage / 100)
        )
        self.rpr_context.scene.set_name(scene.name)

        frame_motion_blur_info = self.collect_motion_blur_info(depsgraph)

        world.sync(self.rpr_context, scene.world)

        # exporting objects
        objects_len = len(depsgraph.objects)
        for i, obj in enumerate(self.depsgraph_objects(depsgraph)):
            self.notify_status(0, "Syncing object (%d/%d): %s" % (i, objects_len, obj.name))

            obj_motion_blur_info = frame_motion_blur_info.get(object.key(obj), None)

            try:
                object.sync(self.rpr_context, obj, motion_blur_info=obj_motion_blur_info)

            except SyncError as e:
                log.warn("Object syncing error", e)   # TODO: Error to UI log

            if self.rpr_engine.test_break():
                log.warn("Syncing stopped by user termination")
                return

        # exporting instances
        instances_len = len(depsgraph.object_instances)
        for i, inst in enumerate(self.depsgraph_instances(depsgraph)):
            obj = inst.object
            self.notify_status(0, "Syncing instance (%d/%d): %s" % (i, instances_len - objects_len, obj.name))

            obj_motion_blur_info = frame_motion_blur_info.get(instance.key(inst), None)

            try:
                instance.sync(self.rpr_context, inst, motion_blur_info=obj_motion_blur_info)

            except SyncError as e:
                log.warn("Object syncing error", e)   # TODO: Error to UI log

            if self.rpr_engine.test_break():
                log.warn("Syncing stopped by user termination")
                return

        camera_key = object.key(scene.camera)

        # it's possible that depsgraph.object_instances doesn't contain camera,
        # in this case we need to sync it separately
        if camera_key not in self.rpr_context.objects:
            camera.sync(self.rpr_context, scene.camera)

        rpr_camera = self.rpr_context.objects[camera_key]

        if scene.camera.rpr.motion_blur:
            rpr_camera.set_exposure(scene.camera.data.rpr.motion_blur_exposure)

            if camera_key in frame_motion_blur_info:
                camera_motion_blur = frame_motion_blur_info[camera_key]
                rpr_camera.set_angular_motion(*camera_motion_blur.angular_momentum)
                rpr_camera.set_linear_motion(*camera_motion_blur.linear_velocity)

        self.rpr_context.scene.set_camera(rpr_camera)

        view_layer.rpr.export_aovs(view_layer, self.rpr_context, self.rpr_engine)

        if scene.rpr.viewport_limits.noise_threshold > 0.0:
            # if adaptive is enable turn on aov and settings
            self.rpr_context.enable_aov(pyrpr.AOV_VARIANCE)
            scene.rpr.viewport_limits.set_adaptive_params(self.rpr_context)

        self.rpr_context.sync_shadow_catcher()
        view_layer.rpr.denoiser.export_denoiser(self.rpr_context)

        self.rpr_context.set_parameter('preview', False)
        scene.rpr.export_ray_depth(self.rpr_context)

        self.render_iterations, self.render_time = (scene.rpr.limits.max_samples, scene.rpr.limits.seconds)
        self.render_update_samples = scene.rpr.limits.update_samples
        self.min_samples = scene.rpr.limits.min_samples

        self.is_synced = True
        self.notify_status(0, "Finish syncing")
        log('Finish sync')
