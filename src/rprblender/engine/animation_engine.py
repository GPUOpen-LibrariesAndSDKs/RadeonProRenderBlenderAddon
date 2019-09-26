from .render_engine import RenderEngine
from .context import RPRContext
from .image_filter import ImageFilter


class AnimationEngine(RenderEngine):

    rpr_context: RPRContext = None
    image_filter: ImageFilter = None

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)

        self.is_last_frame = False

    def _init_rpr_context(self, scene):
        if not AnimationEngine.rpr_context:
            AnimationEngine.rpr_context = RPRContext()
            scene.rpr.init_rpr_context(AnimationEngine.rpr_context)
            AnimationEngine.rpr_context.scene.set_name(scene.name)

        self.rpr_context = AnimationEngine.rpr_context

    def sync(self, depsgraph):
        super().sync(depsgraph)

        self.is_last_frame = depsgraph.scene.frame_current >= depsgraph.scene.frame_end

    def render(self):
        try:
            super().render()

        finally:
            if self.is_last_frame or self.rpr_engine.test_break():
                self.rpr_context = AnimationEngine.rpr_context = None
                self.image_filter = AnimationEngine.image_filter = None
            else:
                self.rpr_context.clear_scene()

    def setup_image_filter(self, settings):
        self.image_filter = AnimationEngine.image_filter
        super().setup_image_filter(settings)
        AnimationEngine.image_filter = self.image_filter
