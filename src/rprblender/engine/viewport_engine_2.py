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
import time
import threading

import pyrpr

from .viewport_engine import ViewportEngine, ViewportSettings, FinishRenderException
from .context import RPRContext2

from rprblender.utils import logging
log = logging.Log(tag='viewport_engine_2')


class ViewportEngine2(ViewportEngine):
    _RPRContext = RPRContext2

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)

        self.is_last_iteration = False
        self.rendered_image = None

        self.resolve_event = threading.Event()
        self.resolve_thread = None
        self.resolve_lock = threading.Lock()

    def stop_render(self):
        self.is_finished = True
        self.restart_render_event.set()
        self.resolve_event.set()
        self.sync_render_thread.join()
        self.resolve_thread.join()

        self.rpr_context.set_render_update_callback(None)
        self.rpr_context = None
        self.image_filter = None
        self.upscale_filter = None

    def _resolve(self):
        self.rpr_context.resolve(None if self.image_filter and self.is_last_iteration else
                                 (pyrpr.AOV_COLOR,))
        
    def _resize(self, width, height):
        if self.width == width and self.height == height:
            self.is_resized = False
            return

        with self.render_lock:
            with self.resolve_lock:
                self.rpr_context.resize(width, height)

        self.width = width
        self.height = height

        if self.image_filter:
            image_filter_settings = self.image_filter.settings.copy()
            image_filter_settings['resolution'] = self.width, self.height
            self.setup_image_filter(image_filter_settings)

        if self.background_filter:
            background_filter_settings = self.background_filter.settings.copy()
            background_filter_settings['resolution'] = self.width, self.height
            self.setup_background_filter(background_filter_settings)

        if self.upscale_filter:
            upscale_filter_settings = self.upscale_filter.settings.copy()
            upscale_filter_settings['resolution'] = self.width, self.height
            self.setup_upscale_filter(upscale_filter_settings)

        self.is_resized = True

    def _do_render(self):
        iteration = 0
        time_begin = 0.0
        update_iterations = 1
        is_set_callback = False

        def render_update(progress):
            if self.restart_render_event.is_set():
                self.rpr_context.abort_render()
                return

            # don't need to do intermediate update when progress == 1.0
            if progress == 1.0:
                return

            self.resolve_event.set()

            time_render = time.perf_counter() - time_begin
            self.notify_status(f"Time: {time_render:.1f} sec | Iteration "
                               f"{iteration + update_iterations}/{self.render_iterations}" +
                               "." * int(progress / 0.2), "Render")

        self.notify_status("Starting...", "Render")

        # Infinite cycle, which starts when scene has to be re-rendered.
        # It waits for restart_render_event be enabled.
        # Exit from this cycle is implemented through raising FinishRender
        # when self.is_finished be enabled from main thread.
        while True:
            self.restart_render_event.wait()

            if self.is_finished:
                raise FinishRenderException

            # preparations to start rendering
            iteration = 0
            time_begin = 0.0
            time_render = 0.0
            self.is_last_iteration = False

            # this cycle renders each iteration
            while True:
                if self.is_finished:
                    raise FinishRenderException

                if self.restart_render_event.is_set():
                    # clears restart_render_event, prepares to start rendering
                    self.restart_render_event.clear()

                    vs = self.viewport_settings
                    if vs is None:
                        continue

                    if self.user_settings.adapt_viewport_resolution:
                        self._adapt_resize(*self._get_resolution(vs),
                                           self.user_settings.min_viewport_resolution_scale * 0.01)
                    else:
                        self._resize(*self._get_resolution(vs))

                    self.is_resolution_adapted = not self.user_settings.adapt_viewport_resolution

                    if self.width * self.height == 0:
                        self.notify_status("", "Rendering Done")
                        break

                    vs.export_camera(self.rpr_context.scene.camera)
                    iteration = 0

                    self.rpr_context.sync_auto_adapt_subdivision()
                    self.rpr_context.sync_portal_lights()
                    time_begin = time.perf_counter()
                    log(f"Restart render [{vs.width}, {vs.height}]")

                if self.restart_render_event.is_set():
                    continue

                self.rpr_context.set_parameter(pyrpr.CONTEXT_FRAMECOUNT, iteration)
                update_iterations = 1
                if iteration > 1:
                    update_iterations = min(32, self.render_iterations - iteration)
                self.rpr_context.set_parameter(pyrpr.CONTEXT_ITERATIONS, update_iterations)

                # unsetting render update callback for first iteration and set it back
                # starting from second iteration
                if iteration == 0:
                    self.rpr_context.set_render_update_callback(None)
                    self.rpr_context.set_parameter(pyrpr.CONTEXT_PREVIEW, 3)
                    is_set_callback = False
                elif iteration == 1:
                    if self.is_resolution_adapted:
                        self.rpr_context.clear_frame_buffers()
                        self.rpr_context.set_parameter(pyrpr.CONTEXT_PREVIEW, 0)
                elif not is_set_callback:
                    self.rpr_context.set_render_update_callback(render_update)
                    is_set_callback = True

                # rendering
                with self.render_lock:
                    try:
                        self.rpr_context.render(restart=(iteration == 0))

                    except pyrpr.CoreError as e:
                        if e.status != pyrpr.ERROR_ABORTED:     # ignoring ERROR_ABORTED
                            raise

                if iteration > 0 and self.restart_render_event.is_set():
                    continue

                if iteration == 1 and not self.is_resolution_adapted:
                    time_render_prev = time_render
                    time_render = time.perf_counter() - time_begin
                    iteration_time = time_render - time_render_prev

                    target_time = 1.0 / self.user_settings.viewport_samples_per_sec
                    self.requested_adapt_ratio = target_time / iteration_time

                    self._adapt_resize(*self._get_resolution(self.viewport_settings),
                                       self.user_settings.min_viewport_resolution_scale * 0.01,
                                       self.requested_adapt_ratio)

                    iteration = 0
                    self.is_resolution_adapted = True
                    continue

                iteration += update_iterations
                self.is_last_iteration = iteration >= self.render_iterations

                if self.is_last_iteration:
                    break

                # getting render results only for first iteration, for other iterations
                if iteration == 1:
                    with self.resolve_lock:
                        self._resolve()
                        self.rendered_image = self.rpr_context.get_image()
                else:
                    self.resolve_event.set()

                time_render = time.perf_counter() - time_begin
                self.notify_status(f"Time: {time_render:.1f} sec | Iteration {iteration}/"
                                   f"{self.render_iterations}", "Render")

            if not self.is_last_iteration:
                continue

            # notifying viewport that rendering is finished
            with self.resolve_lock:
                self._resolve()

            time_render = time.perf_counter() - time_begin
            with self.render_lock:
                if self.image_filter:
                    self.notify_status(f"Time: {time_render:.1f} sec | Iteration: {iteration}"
                                       f" | Denoising...", "Render")

                    # applying denoising
                    self.update_image_filter_inputs()
                    self.image_filter.run()
                    image = self.image_filter.get_data()

                    time_render = time.perf_counter() - time_begin
                    status_str = f"Time: {time_render:.1f} sec | Iteration: {iteration} | Denoised"
                else:
                    image = self.rpr_context.get_image()
                    status_str = f"Time: {time_render:.1f} sec | Iteration: {iteration}"

                if self.background_filter:
                    with self.resolve_lock:
                        self.rendered_image = self.resolve_background_aovs(self.rendered_image)
                else:
                    self.rendered_image = image

                if self.upscale_filter:
                    self.upscale_filter.update_input('color', self.rendered_image)
                    self.upscale_filter.run()
                    self.rendered_image = self.upscale_filter.get_data()
                    status_str += " | Upscaled"

            self.notify_status(status_str, "Rendering Done")

    def _do_resolve(self):
        while True:
            self.resolve_event.wait()
            self.resolve_event.clear()
            if self.is_finished:
                break

            if self.restart_render_event.is_set():
                continue

            if self.is_last_iteration:
                continue

            with self.resolve_lock:
                self._resolve()
                image = self.rpr_context.get_image()

                if self.background_filter:
                    image = self.resolve_background_aovs(image)
                    self.rendered_image = image
                else:
                    self.rendered_image = image

        log("Finish _do_resolve")

    def resolve_background_aovs(self, color_image):
        settings = self.background_filter.settings
        self.rpr_context.resolve((pyrpr.AOV_OPACITY,))
        alpha = self.rpr_context.get_image(pyrpr.AOV_OPACITY)
        if settings['use_shadow']:
            self.rpr_context.resolve((pyrpr.AOV_SHADOW_CATCHER,))
        if settings['use_reflection']:
            self.rpr_context.resolve((pyrpr.AOV_REFLECTION_CATCHER,))
        if settings['use_shadow'] or settings['use_reflection']:
            self.rpr_context.resolve((pyrpr.AOV_BACKGROUND,))
        self.update_background_filter_inputs(color_image=color_image, opacity_image=alpha)
        self.background_filter.run()
        return self.background_filter.get_data()

    def draw(self, context):
        log("Draw")

        if not self.is_synced or self.is_finished:
            return

        # initializing self.viewport_settings and requesting first self.restart_render_event
        if not self.viewport_settings:
            self.viewport_settings = ViewportSettings(context)
            self._resize(*self._get_resolution())
            self.restart_render_event.set()
            return

        # checking for viewport updates: setting camera position and resizing
        viewport_settings = ViewportSettings(context)
        if viewport_settings.width * viewport_settings.height == 0:
            return

        if self.viewport_settings != viewport_settings:
            self.viewport_settings = viewport_settings
            self.restart_render_event.set()

        im = self.rendered_image
        if im is None:
            return

        self.gl_texture.set_image(im)
        self.draw_texture(self.gl_texture.texture_id, context.scene)

    def sync(self, context, depsgraph):
        super().sync(context, depsgraph)

        self.resolve_thread = threading.Thread(target=self._do_resolve)
        self.resolve_thread.start()

        def sync_time(timems):
            log(f"sync_time: {timems * 0.001:.3f}")

        def delta_render_time(timems):
            log(f"delta_render_time: {timems * 0.001:.3f}")

        def first_iteration_time(timems):
            log(f"first_iteration_time: {timems * 0.001:.3f}")

        self.rpr_context.set_time_callback(pyrpr.CONTEXT_UPDATE_TIME_CALLBACK_FUNC, sync_time)
        self.rpr_context.set_time_callback(pyrpr.CONTEXT_RENDER_TIME_CALLBACK_FUNC, delta_render_time)
        self.rpr_context.set_time_callback(pyrpr.CONTEXT_FIRST_ITERATION_TIME_CALLBACK_FUNC, first_iteration_time)

    def _sync_update_after(self):
        self.rpr_engine.update_stats("Render", "Syncing...")
