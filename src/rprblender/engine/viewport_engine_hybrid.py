from . import viewport_engine
from . import context_hybrid

from rprblender.operators.world import FOG_KEY

from rprblender.utils import logging
log = logging.Log(tag='viewport_engine_hybrid')


class ViewportEngine(viewport_engine.ViewportEngine):
    _RPRContext = context_hybrid.RPRContext

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)

        self.render_image = None

    def sync(self, context, depsgraph):
        super().sync(context, depsgraph)

        depsgraph.scene.rpr.export_render_quality(self.rpr_context)
        log('Finish sync')

    def update_render(self, scene, view_layer):
        restart = scene.rpr.export_render_quality(self.rpr_context)
        restart |= super().update_render(scene, view_layer)

        return restart

    def _resolve(self):
        self.render_image = self.rpr_context.get_image()

    def _get_render_image(self):
        return self.render_image

    def depsgraph_objects(self, depsgraph, with_camera=False):
        for obj in super().depsgraph_objects(depsgraph, with_camera):
            if obj.name == FOG_KEY:
                continue

            yield obj
