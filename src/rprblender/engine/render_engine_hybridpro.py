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
from . import render_engine
from . import context_hybridpro

from rprblender.operators.world import FOG_KEY

from rprblender.utils import logging
log = logging.Log(tag='render_engine_hybridpro')


class RenderEngine(render_engine.RenderEngine):
    _RPRContext = context_hybridpro.RPRContext

    def depsgraph_objects(self, depsgraph, with_camera=False):
        for obj in super().depsgraph_objects(depsgraph, with_camera):
            if obj.name == FOG_KEY:
                continue

            yield obj

    def _update_athena_data(self, data):
        data['Quality'] = "hybridpro"
