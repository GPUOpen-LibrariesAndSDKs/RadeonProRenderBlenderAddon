from . import render_engine
from . import context_hybrid

from rprblender.operators.world import FOG_KEY

from rprblender.utils import logging
log = logging.Log(tag='render_engine_hybrid')


class RenderEngine(render_engine.RenderEngine):
    _RPRContext = context_hybrid.RPRContext

    def sync(self, depsgraph):
        super().sync(depsgraph)

        depsgraph.scene.rpr.export_render_quality(self.rpr_context)
        log('Finish sync')

    def depsgraph_objects(self, depsgraph, with_camera=False):
        for obj in super().depsgraph_objects(depsgraph, with_camera):
            if obj.name == FOG_KEY:
                continue

            yield obj
