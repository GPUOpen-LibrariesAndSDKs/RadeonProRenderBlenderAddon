from . import render_engine
from . import context_hybrid

from rprblender.utils import logging
log = logging.Log(tag='render_engine_hybrid')


class RenderEngine(render_engine.RenderEngine):
    _RPRContext = context_hybrid.RPRContext

    def sync(self, depsgraph):
        super().sync(depsgraph)

        depsgraph.scene.rpr.export_render_quality(self.rpr_context)
        log('Finish sync')
