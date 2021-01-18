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
import threading
import time

import pyrpr

from .render_engine import RenderEngine
from .context import RPRContext2

from rprblender.utils import logging
log = logging.Log(tag='RenderEngine2')


class RenderEngine2(RenderEngine):
    _RPRContext = RPRContext2

    def _update_athena_data(self, data):
        data['Quality'] = "rpr2"

    def _render(self):
        resolve_event = threading.Event()
        is_finished = False
        time_begin = 0.0

        def render_update_callback(progress):
            if progress == 1.0:
                return

            if self.rpr_engine.test_break():
                self.rpr_context.abort_render()
                return

            update_samples = min(self.render_update_samples,
                                 self.render_samples - self.current_sample)
            full_progress = max(
                (self.current_sample + update_samples * progress) / self.render_samples,
                self.current_render_time / self.render_time if self.render_time else 0
            )

            self.current_render_time = time.perf_counter() - time_begin
            info_str = f"Render Time: {self.current_render_time:.1f}"
            if self.render_time:
                info_str += f"/{self.render_time}"
            info_str += f" sec | Samples: {self.current_sample + update_samples}" \
                        f"/{self.render_samples}" + '.' * int(progress / 0.2)

            self.notify_status(full_progress, info_str)

            resolve_event.set()

        def do_resolve():
            log('Start do_resolve')
            while True:
                resolve_event.wait()
                resolve_event.clear()

                if is_finished or self.rpr_engine.test_break():
                    break

                self.rpr_context.resolve()
                self.update_render_result((0, 0), (self.width, self.height),
                                          layer_name=self.render_layer_name)

            log('Finish do_resolve')

        self.rpr_context.set_render_update_callback(render_update_callback)
        resolve_thread = threading.Thread(target=do_resolve)
        resolve_thread.start()

        time_begin = time.perf_counter()
        try:
            super()._render()

        except pyrpr.CoreError as e:
            if e.status != pyrpr.ERROR_ABORTED:     # ignoring ERROR_ABORTED
                raise

        finally:
            is_finished = True
            self.rpr_context.set_render_update_callback(None)
            resolve_event.set()
            resolve_thread.join()

    def set_motion_blur_mode(self, scene):
        flag = not bool(scene.rpr.motion_blur_in_velocity_aov)
        self.rpr_context.set_parameter(pyrpr.CONTEXT_BEAUTY_MOTION_BLUR, flag)
