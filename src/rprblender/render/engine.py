import datetime
import gc
import time
import traceback
import weakref
from pathlib import Path

import bpy
import numpy as np
import pyrpr
import sys
import viewportdraw

import rprblender.core.image
import rprblender.render
import rprblender.render.render_layers
import rprblender.render.render_stamp
import rprblender.render.scene
import rprblender.render.viewport
from rprblender import rpraddon, logging, config, sync, export
from rprblender.helpers import CallLogger, print_memory_usage
from rprblender.timing import TimedContext
import rprblender.versions as versions

call_logger = CallLogger(tag='render.engine')


@rpraddon.register_class
class RenderViewport(bpy.types.Operator):
    bl_idname = "rpr.view_render_start"
    bl_label = "RPR Start Viewport Render"

    def execute(self, context):
        start_viewport_rendering(context)
        return {'FINISHED'}


@call_logger.logged
def start_viewport_rendering(context):
    viewport_renderer = rprblender.render.viewport.ViewportRenderer()
    logging.debug('start: {},{}'.format(context.region.width, context.region.height), tag='render.viewport')
    viewport_renderer.set_render_aov(versions.get_render_passes_aov(bpy.context))
    viewport_renderer.set_render_resolution((context.region.width, context.region.height))

    #viewport_renderer.set_render_resolution((context.region.width, context.region.height))

    viewport_renderer.set_render_camera(sync.extract_viewport_render_camera(context, context.scene.rpr.render))
    viewport_renderer.start(context.scene)

    RPREngine.viewport_renderers[context.space_data] = viewport_renderer


@rpraddon.register_class
class RPREngine(bpy.types.RenderEngine):
    bl_idname = 'RPR'
    bl_label = 'Radeon ProRender'
    bl_use_preview = True
    bl_preview = True

    # bl_use_shading_nodes = True
    bl_use_shading_nodes_custom = True

    # when something bad happens in api call(render, view_update etc) this one is set instead of
    # just pasing exception to Blender(where it's swallowed though displayed in stderr but
    # RenderEngine is shutdown not nicely after this)
    error = None

    viewport_renderers = {}
    viewportrenderer_space_data = None

    instances = weakref.WeakSet()  # for tests

    def __init__(self):
        super().__init__()
        logging.debug(self, "__init__")
        self.im = None
        self.texture = None
        self.prev_sc = False

    @call_logger.logged
    def __del__(self):
        if self.viewportrenderer_space_data:
            viewport_renderer = self.viewport_renderers.pop(self.viewportrenderer_space_data)
            logging.debug('stopping:', viewport_renderer)
            viewport_renderer.stop()

    def update(self, data=None, scene=None):  # Export scene data for render
        if self.is_preview:
            logging.debug("create scene for preview render")
        else:
            logging.debug("create scene for normal render")

        logging.debug('update')

    def bake(self, scene, object, pass_type, pass_filter, object_id, pixel_array, num_pixels, depth,
             result):  # Bake passes
        logging.debug('bake')

    def render(self, scene):
        logging.debug('render', tag='render.engine')
        try:
            self._render(scene)
        except:
            self.report_render_error('render', "Exception: %s" % traceback.format_exc())
        logging.debug('render done', tag='render.engine')

    @staticmethod
    def init_preview_settings():
        pass

    def show_gpu_info(self):
        from . import helpers
        # import rprblender.helpers
        info = helpers.render_resources_helper.get_used_gpu_info()
        if info:
            self.report({'WARNING'}, info)
            logging.info('info: ', info)

    @call_logger.logged
    def _render(self, scene: bpy.types.Scene):
        logging.debug('render', 'preview' if self.is_preview else 'prod')

        if self.is_preview and not config.preview_enable:
            return

        if not self.is_preview:
            self.update_stats('starting render', 'Radeon ProRender')
            self.show_gpu_info()

        self.report({'INFO'}, "RPR: rendering " + ('PREVIEW' if self.is_preview else "PRODUCTION"))

        width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100.0)
        height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100.0)

        settings = bpy.context.scene.rpr.render_preview if self.is_preview else scene.rpr.render

        with rprblender.render.core_operations(raise_error=True):
            render_device = rprblender.render.get_render_device(is_production=True, persistent=True, has_denoiser=settings.denoiser.enable)
            scene_renderer = rprblender.render.scene.SceneRenderer(render_device, settings, not self.is_preview)  #

        # determine if scene has a shadow catcher
        for obj in scene.objects:
            if obj.rpr_object.shadowcatcher:
                scene_renderer.has_shadowcatcher = True
                break

        scene_renderer.has_denoiser = settings.denoiser.enable

        if settings.denoiser.enable:
            scene_renderer.filter_type = settings.denoiser.filter_type_values[settings.denoiser.filter_type]

        scene_synced = sync.SceneSynced(scene_renderer.render_device, settings)

        scene_renderer.production_render = True

        render_resolution = width, height

        border = rprblender.sync.extract_render_border_from_scene(scene)
        render_border_resolution = rprblender.sync.get_render_resolution_for_border(border, render_resolution)

        render_camera = sync.RenderCamera()
        sync.extract_render_camera_from_blender_camera(scene.camera, render_camera, render_resolution, 1, settings,
                                                       scene, border=border)

        scene_synced.set_render_camera(render_camera)

        passes_aov_list, active_index = bpy.context.scene.rpr.preview_aov if self.is_preview else versions.get_render_passes_aov_list(bpy.context)
        aov_settings = rprblender.render.render_layers.extract_settings_list(passes_aov_list, active_index)

        with rprblender.render.core_operations(raise_error=True):
            scene_synced.make_core_scene()
            scene_renderer.update_aov(aov_settings)

            scene_renderer.update_render_resolution(render_border_resolution)

            # if scene.render.use_border:
            #     region_relative = (
            #         scene.render.border_min_x, scene.render.border_max_x,
            #         scene.render.border_min_y, scene.render.border_max_y)
            #     aspect = render_border_resolution[0]/render_border_resolution[1]
            #
            #     region_relative = region_relative*np.array([1, 1, 1, 1])
            #
            #     region = tuple(np.uint32(region_relative*np.repeat(render_border_resolution, 2)))
            #
            #     scene_renderer.update_render_region(region)

        try:
            if not self.is_preview:
                self.update_stats('', 'exporting scene...')
            time_export_start = time.perf_counter()
            print_memory_usage("before export")
            scene_exporter = export.SceneExport(scene, scene_synced)
            scene_exporter.set_render_layer(scene.render.layers[0])
            try:

                # texture compression context param needs to be set before exporting textures
                pyrpr.ContextSetParameter1u(scene_renderer.get_core_context(), b"texturecompression",
                                            settings.texturecompression)

                if self.is_preview:
                    is_icon = width <= 32 and height <= 32

                    scene_exporter.export_preview(is_icon)

                    environment_light_image = rprblender.core.image.create_core_image_from_image_file(
                        scene_renderer.core_context, str(Path(rprblender.__file__).parent / 'img/env.hdr'))
                    environment_light = scene_synced.environment_light_create_from_core_image(
                        "preview_ibl", environment_light_image)
                    environment_light.attach()

                    if is_icon:
                        background_image = rprblender.core.image.create_core_image_from_image_file(
                            scene_renderer.core_context, str(Path(rprblender.__file__).parent / 'img/gray.jpg'))
                        background = scene_synced.background_create_from_core_image(
                            "preview_background", background_image)
                        background._enable()
                else:
                    settings_environment = scene.world.rpr_data.environment if scene.world else None
                    scene_exporter.sync_environment_settings(settings_environment)

                    for name in scene_exporter.export_iter():
                        print_memory_usage("export %s" % name)
                        if scene_synced.has_error:
                            self.report({'WARNING'},'Scene export completed with errors.\nPlease see the log for more details!')
                            scene_synced.has_error = False
                        if self.test_break():
                            return
                        logging.debug('exporting:', name, tag='sync')
                        self.update_stats("Exporting", str(name))

                    if not self.is_preview:
                        self.report({'INFO'},
                                    'RPR: scene export took {:.3f} seconds'.format(time.perf_counter() - time_export_start))
            finally:
                print_memory_usage("export done")

            scene_renderer_threaded = rprblender.render.scene.SceneRendererThreaded(scene_renderer)
            scene_renderer_threaded.start_noninteractive()

            
            if not self.is_preview and versions.is_blender_support_aov():
                self.add_passes(passes_aov_list)

            result = self.begin_result(0, 0, render_border_resolution[0], render_border_resolution[1])
            logging.debug("Passes in the result:", tag="render.engine.passes")
            # TODO: render to active layer or render all layers

            render_failed = False
            try:
                for render_layer_index, result_render_layer in enumerate(result.layers):

                    if 0 != render_layer_index:
                        scene_exporter.set_render_layer(scene.render.layers[render_layer_index])
                        with scene_renderer_threaded.update_lock:
                            scene_renderer_threaded.need_scene_redraw = True
                            self.update_stats("Sync layer:", str(render_layer_index))
                            scene_exporter.sync(refresh_render_layers=True)

                    for p in result_render_layer.passes:
                        logging.debug("    pass:", p.name, tag="render.engine.passes")

                    try:
                        iteration_displayed = None
                        while True:
                            render_completed = False

                            # update render stats few times before displaying intermediate results(long operation in Blender)
                            for i in range(10):
                                if not scene_renderer_threaded.is_alive():
                                    render_failed = True
                                    return
                                if self.test_break():
                                    return
                                self.update_scene_render_stats(self, scene_renderer, settings.rendering_limits)
                                if scene_renderer_threaded.render_completed_event.wait(timeout=0.1):
                                    render_completed = True
                                    break

                            iteration = self.get_rendered_iteration(scene_renderer)
                            if iteration_displayed != iteration:
                                self.set_render_to_result(result_render_layer, scene_renderer)

                                if not render_completed:
                                    iteration_displayed = iteration
                                    with TimedContext("update_result"):
                                        self.update_result(result)

                            if render_completed:
                                break
                    finally:
                        pass
            finally:
                scene_renderer_threaded.stop()
                del scene_renderer_threaded
                if not render_failed:
                    with TimedContext("end_result"):
                        logging.debug("end_result", tag="render.engine")
                        self.end_result(result)
                else:
                    self.report_render_error('render', 'render failed')

        finally:
            scene_synced.destroy()
            del scene_synced
            del scene_renderer
            del render_device
            #rprblender.render.free_render_devices()

    @staticmethod
    def update_scene_render_stats(engine, scene_renderer: rprblender.render.scene.SceneRenderer, limits):
        if not scene_renderer.cache_generated:
            engine.update_progress(0)
            # while rendering first iteration Core may stall to rebuild OpenCL cache and this takes time
            engine.update_stats('initializing', "This may take a few minutes!")
            return

        iteration_in_progress = scene_renderer.iteration_in_progress or 0
        iteration_divider = scene_renderer.iteration_divider or 1
        if limits.enable:
            time_render_passed = ((time.perf_counter() - scene_renderer.time_render_start)
                                  if scene_renderer.time_render_start is not None
                                  else 0)
            if 'TIME' == limits.type:
                if limits.time != 0:
                    if scene_renderer.time_render_start is not None:
                        limit = datetime.timedelta(seconds=limits.time)

                        if 0.0 < limit.total_seconds():
                            engine.update_progress(time_render_passed / limit.total_seconds())
                            done = limit <= datetime.timedelta(seconds=int(time_render_passed))
                            engine.update_stats(
                                'Remaining: {}'.format(limit - datetime.timedelta(seconds=int(time_render_passed)))
                                if not done else 'Done',
                                "Iteration: {}".format(iteration_in_progress + 1))
                    return

            elif 'ITER' == limits.type:
                if limits.iterations > 0:
                    if 0 < limits.iterations and iteration_in_progress is not None:
                        render_progress = (iteration_in_progress + 1) * (1 / iteration_divider) / limits.iterations
                        engine.update_progress(render_progress)
                        if 0.0 < render_progress:
                            estimated_total_time = time_render_passed / render_progress
                            estimated_time_remaining = estimated_total_time * (1 - render_progress)
                        else:
                            estimated_time_remaining = 0

                        engine.update_stats(
                            'Remaining: {}'.format(datetime.timedelta(seconds=int(estimated_time_remaining))),
                            "Iteration: {}/{}".format(int((iteration_in_progress + 1) * (1 / iteration_divider)),
                                                      limits.iterations))
                    return

        # if we haven't limits
        if iteration_in_progress is not None:
            engine.update_progress(0)
            engine.update_stats('iteration: {}/-'.format(iteration_in_progress + 1), 'rendering...')

    def get_rendered_iteration(self, scene_renderer):
        with TimedContext("scene_renderer.get_image"):
            if scene_renderer.get_image() is None:
                return None
            return scene_renderer.im_iteration

    def set_render_to_result(self, result_render_layer, scene_renderer):
        images = scene_renderer.get_images()
        with TimedContext("copy image to rect"):
            res = []
            for p in result_render_layer.passes:
                aov_name = rprblender.render.render_layers.pass_to_aov_name(p.name)

                if aov_name:
                    pass_image = images.get_image(aov_name)
                else:
                    pass_image = None

                if pass_image is None:
                    pass_image = np.ones(height * width * p.channels, dtype=np.float32)
                else:
                    width, height = pass_image.shape[1], pass_image.shape[0]
                    if p.channels != 4:
                        pass_image = pass_image[:, :, 0:p.channels]

                if bpy.context.scene.rpr.use_render_stamp:
                    rprblender.render.render_stamp.render_stamp(bpy.context.scene.rpr.render_stamp, bpy.context,
                                                                pass_image, scene_renderer.resolution[0],
                                                                scene_renderer.resolution[1], p.channels,
                                                                scene_renderer.iteration_in_progress,
                                                                scene_renderer.time_in_progress)

                res.append(pass_image.flatten())
        with TimedContext("set image to blender"):
            logging.debug("result_render_layer.passes.foreach_set:", len(res), tag="render.engine")
            result_render_layer.passes.foreach_set("rect", np.concatenate(res))


    def report_render_error(self, error_type, message):
        self.update_stats("ERROR", "Check log for details")
        self.report({'INFO'}, 'ERROR: Check log for details')
        self.error = error_type
        logging.critical('ERROR:', 'It is recommended to restart Blender\n', message, tag='render')

    def view_update(self, context):  # Update on data changes for viewport render
        logging.debug("view_update", tag='render')
        if self.error:
            return
        try:
            # cProfile.runctx("self._view_update(context)", globals(), locals(), sort='cumulative')
            self._view_update(context)
            self.tag_redraw()
        except:
            self.report_render_error('view_update', "view_update: Exception %s" % traceback.format_exc())

    @call_logger.logged
    def _view_update(self, context: bpy.types.Context):

        logging.debug('view_update', context,
                      'region_data.view_perspective:', context.region_data.view_perspective,
                      'space_data.lens:', context.space_data.lens,
                      'region_data.view_camera_zoom:', context.region_data.view_camera_zoom,
                      'region.width:', context.region.width,
                      'region.height:', context.region.height,
                      'region.x:', context.region.x,
                      'region.y:', context.region.y,
                      'region_data.view_matrix:', context.region_data.view_matrix, tag='render.viewport.update')

        if context.space_data not in self.viewport_renderers:
            self.update_stats("Exporting", "scene")
            self.viewportrenderer_space_data = context.space_data
            bpy.ops.rpr.view_render_start()
            self.tag_redraw()
            return

        viewport_renderer = self.viewport_renderers[context.space_data]

        if not viewport_renderer.scene_renderer_threaded.is_alive():
            self.report_render_error('view_update', "Render thread crashed")
            return

        for name in viewport_renderer.update_iter(context.scene):
            self.update_stats("Sync", name)
        self.tag_redraw()

    view_draw_get_image_fps_max = 100
    view_draw_get_image_timestamp = -1 / view_draw_get_image_fps_max

    def view_draw(self, context):  # Draw viewport render
        logging.debug("view_draw", tag='render')
        if self.error:
            return
        try:
            with TimedContext('_view_draw'):
                self._view_draw(context)
            # s = cProfile.runctx("self._view_draw(context)", globals(), locals(), sort='cumulative')

            self.tag_redraw()
        except:
            self.report_render_error('view_draw', "Exception: %s" % traceback.format_exc())

    @call_logger.logged
    def _view_draw(self, context):
        logging.debug('view_draw', context,
                      'region_data.view_perspective:', context.region_data.view_perspective,
                      'space_data.lens:', context.space_data.lens,

                      'space_data.use_render_border:', context.space_data.use_render_border,
                      'space_data.render_border_min_x:', context.space_data.render_border_min_x,
                      'space_data.render_border_max_x:', context.space_data.render_border_max_x,
                      'space_data.render_border_min_y:', context.space_data.render_border_min_y,
                      'space_data.render_border_max_y:', context.space_data.render_border_max_y,

                      'region_data.view_camera_zoom:', context.region_data.view_camera_zoom,
                      'region.width:', context.region.width,
                      'region.height:', context.region.height,
                      'region.x:', context.region.x,
                      'region.y:', context.region.y,
                      'region_data.view_matrix:', context.region_data.view_matrix, tag='render.viewport.draw')

        if context.space_data not in self.viewport_renderers:
            self.tag_redraw()
            return

        viewport_renderer = self.viewport_renderers[context.space_data]  # type: ViewportRenderer

        if not viewport_renderer.scene_renderer_threaded.is_alive():
            self.report_render_error('view_draw', "Render thread crashed")
            return

        time_view_draw_start = time.perf_counter()

        render_resolution = (context.region.width, context.region.height)

        if (1 / self.view_draw_get_image_fps_max) < (time_view_draw_start - self.view_draw_get_image_timestamp):
            self.view_draw_get_image_timestamp = time_view_draw_start
            logging.debug("get_image", tag='render.viewport.draw')

            viewport_renderer.update_render_aov(versions.get_render_passes_aov(bpy.context))
            viewport_renderer.update_render_resolution(render_resolution)

            region = self.get_view_render_region(context)
            logging.debug("region:", region, tag='render.viewport.draw.region')
            if region is None:
                viewport_renderer.update_render_region(None)
            else:
                # flip regon verticall for RPR and clip to fit framebuffer
                viewport_renderer.update_render_region(np.clip([region[0], [1-region[1][1], 1-region[1][0]]], 0, 1))

            viewport_renderer.update_render_camera(
                sync.extract_viewport_render_camera(context, viewport_renderer.scene_renderer.render_settings))

            logging.debug("pass:", viewport_renderer.render_aov.pass_displayed,
                          versions.get_render_passes_aov(bpy.context).pass_displayed,
                          tag='render.viewport.draw')

            self.is_shadowcatcher = False
            for obj in context.scene.objects:
                if obj.rpr_object.shadowcatcher:
                    self.is_shadowcatcher = True
                    viewport_renderer.scene_renderer.render_layers.enable_aov('opacity')
                    viewport_renderer.scene_renderer.render_layers.enable_aov('background')
                    viewport_renderer.scene_renderer.render_layers.enable_aov('shadow_catcher')
                    break

            viewport_renderer.scene_renderer.has_shadowcatcher = self.is_shadowcatcher

            if self.prev_sc != self.is_shadowcatcher:
                self.prev_sc = self.is_shadowcatcher
                viewport_renderer.scene_reset(context.scene)

            im = viewport_renderer.get_image(viewport_renderer.render_aov.pass_displayed)
            if im is not None:
                logging.debug("pass image retrieved", tag='render.viewport.draw')
                assert im.flags['C_CONTIGUOUS']
                self.im = im
            settings = bpy.context.scene.rpr.render
            self.update_scene_render_stats(self, viewport_renderer.scene_renderer, settings.rendering_limits)

            if self.im is not None:
                logging.debug("draw_image", tag='render.viewport.draw')
                # image from viewport_renderer can be older(before resolution was changed)
                # so that's why we are passing current resolution along with image itself(to scale)
                if not self.texture:
                    self.texture = viewportdraw.create_texture(self.im)
                else:
                    self.texture.update(self.im)

        if self.texture:
            zoom = viewport_renderer.scene_renderer.get_image_tile()
            viewportdraw.draw_image_texture(self.texture, render_resolution,
                                            zoom if zoom is not None else (1, 1))

    def get_view_render_region(self, context):
        if 'CAMERA' == context.region_data.view_perspective:
            border = rprblender.sync.extract_render_border_from_scene(context.scene)
            if border is not None:
                border = np.array(border)
                from bpy_extras import view3d_utils

                # get camera frame corners in blender region space
                camera_frame_point_in_region = []
                for v in bpy.context.scene.camera.data.view_frame(bpy.context.scene):
                    point_in_region_pixels = view3d_utils.location_3d_to_region_2d(
                        context.region,
                        context.space_data.region_3d,
                        bpy.context.scene.camera.matrix_world * v
                    )
                    camera_frame_point_in_region.append(
                        np.array(point_in_region_pixels) / (context.region.width, context.region.height))

                camera_frame_rect_in_region = np.transpose([
                    np.min(camera_frame_point_in_region, axis=0),
                    np.max(camera_frame_point_in_region, axis=0)])

                # camera border is in camera frame space - compute it int blender region space
                upper_bound = camera_frame_rect_in_region[..., 1][:, np.newaxis]
                lower_bound = camera_frame_rect_in_region[..., 0][:, np.newaxis]
                return (1-border) * lower_bound + border * upper_bound
        else:
            if context.space_data.use_render_border:
                return [
                    [context.space_data.render_border_min_x, context.space_data.render_border_max_x],
                    [context.space_data.render_border_min_y, context.space_data.render_border_max_y]]


    def add_passes(self, passes_aov_list):
        logging.debug("add_passes", tag="render.engine.passes")
        for layer_name, passes_aov in passes_aov_list:
            if not passes_aov.enable:
                continue

            for i, passes_item in enumerate(passes_aov.render_passes_items):
                if not passes_aov.passesStates[i]:
                    continue

                # not calling add_pass on 'default' (it's already there) and on 'depth' (it's added by use_pass_z=True)
                aov_name = passes_item[0]
                if aov_name == 'default' or aov_name == 'depth':
                    continue

                aov_data = rprblender.render.render_layers.aov_info[aov_name]

                logging.debug("    add_pass", aov_data, "layer=%s" % layer_name, tag="render.engine.passes")
                self.add_pass(aov_data['name'], len(aov_data['channel']), aov_data['channel'], layer_name)
