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
import bpy

from rprblender.export import object
from .viewport_engine import (
    ViewportEngine, ViewportSettings, ShadingData, FinishRenderException
)
from rprblender.utils import gl
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
        super().stop_render()

        self.resolve_event.set()
        self.resolve_thread.join()

    def _do_render(self):
        iteration = 0
        time_begin = 0.0
        update_iterations = 1

        def render_update(progress):
            if self.restart_render_event.is_set():
                self.rpr_context.abort_render()
                return

            # don't need to do intermediate update for 0, 1 iteration and
            # at render finish when progress == 1.0
            if iteration <= 1 or progress == 1.0:
                return

            self.resolve_event.set()

            time_render = time.perf_counter() - time_begin
            self.notify_status(f"Time: {time_render:.1f} sec | Iteration "
                               f"{iteration + update_iterations}/{self.render_iterations}" +
                               "." * int(progress / 0.2), "Render")

        self.rpr_context.set_render_update_callback(render_update)

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

                    if vs.width != self.rpr_context.width or vs.height != self.rpr_context.height:
                        with self.render_lock:
                            with self.resolve_lock:
                                self.rpr_context.resize(vs.width, vs.height)

                        if self.image_filter:
                            image_filter_settings = self.image_filter.settings.copy()
                            image_filter_settings['resolution'] = vs.width, vs.height
                            self.setup_image_filter(image_filter_settings)

                    vs.export_camera(self.rpr_context.scene.camera)
                    iteration = 0

                    self.rpr_context.sync_auto_adapt_subdivision()
                    self.rpr_context.sync_portal_lights()
                    time_begin = time.perf_counter()
                    log(f"Restart render [{vs.width}, {vs.height}]")

                if self.restart_render_event.is_set():
                    continue

                # rendering
                self.rpr_context.set_parameter(pyrpr.CONTEXT_FRAMECOUNT, iteration)
                update_iterations = 1 if iteration <= 1 else \
                    min(32, self.render_iterations - iteration)
                self.rpr_context.set_parameter(pyrpr.CONTEXT_ITERATIONS, update_iterations)

                with self.render_lock:
                    self.rpr_context.render(restart=(iteration == 0))

                if self.restart_render_event.is_set():
                    continue

                iteration += update_iterations
                self.is_last_iteration = iteration >= self.render_iterations

                if self.is_last_iteration:
                    break

                self.resolve_event.set()

                time_render = time.perf_counter() - time_begin
                self.notify_status(f"Time: {time_render:.1f} sec | Iteration {iteration}/"
                                   f"{self.render_iterations}", "Render")

            if not self.is_last_iteration:
                continue

            # notifying viewport that rendering is finished
            self._resolve()

            time_render = time.perf_counter() - time_begin
            if self.image_filter:
                self.notify_status(f"Time: {time_render:.1f} sec | Iteration: {iteration}"
                                   f" | Denoising...", "Render")

                # applying denoising
                self.update_image_filter_inputs()
                self.image_filter.run()
                self.rendered_image = self.image_filter.get_data()

                time_render = time.perf_counter() - time_begin
                self.notify_status(f"Time: {time_render:.1f} sec | Iteration: {iteration}"
                                   f" | Denoised", "Rendering Done")

            else:
                self.notify_status(f"Time: {time_render:.1f} sec | Iteration: {iteration}",
                                   "Rendering Done")

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
                self.rendered_image = self.rpr_context.get_image()

        log("Finish _do_resolve")

    def draw(self, context):
        log("Draw")

        if not self.is_synced or self.is_finished:
            return

        # initializing self.viewport_settings and requesting first self.restart_render_event
        if not self.viewport_settings:
            self.viewport_settings = ViewportSettings(context)
            self.restart_render_event.set()
            return

        # checking for viewport updates: setting camera position and resizing
        viewport_settings = ViewportSettings(context)
        if viewport_settings.width * viewport_settings.height == 0:
            return

        if self.viewport_settings != viewport_settings:
            self.viewport_settings = viewport_settings
            self.restart_render_event.set()
            self.rendered_image = None
            self.rpr_engine.update_stats("Render", "Syncing...")
            return

        im = self.rendered_image
        if im is None:
            return

        self.gl_texture.set_image(im)
        self.draw_texture(self.gl_texture.texture_id, context.scene)

    def sync(self, context, depsgraph):
        super().sync(context, depsgraph)
        self.resolve_thread = threading.Thread(target=self._do_resolve)
        self.resolve_thread.start()

    def _sync_update_before(self):
        self.restart_render_event.set()

    def _sync_update_after(self):
        self.rpr_engine.update_stats("Render", "Syncing...")
