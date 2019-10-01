from . import viewport_engine
from . import context_hybrid

from rprblender.utils import logging
log = logging.Log(tag='viewport_engine_hybrid')


class ViewportEngine(viewport_engine.ViewportEngine):
    _RPRContext = context_hybrid.RPRContext

    def sync(self, context, depsgraph):
        super().sync(context, depsgraph)

        depsgraph.scene.rpr.export_render_quality(self.rpr_context)
        log('Finish sync')

    def update_render(self, scene, view_layer):
        restart = scene.rpr.export_render_quality(self.rpr_context)
        restart |= super().update_render(scene, view_layer)

        return restart
