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
from . import viewport_engine
from . import context_hybridpro

from rprblender.operators.world import FOG_KEY

from rprblender.utils import logging
log = logging.Log(tag='viewport_engine_hybridpro')


class ViewportEngine(viewport_engine.ViewportEngine):
    _RPRContext = context_hybridpro.RPRContext

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)

        self.render_image = None

    def _resolve(self):
        self.render_image = self.rpr_context.get_image()

    def _get_render_image(self):
        return self.render_image

    def depsgraph_objects(self, depsgraph, with_camera=False):
        for obj in super().depsgraph_objects(depsgraph, with_camera):
            if obj.name == FOG_KEY:
                continue

            yield obj
