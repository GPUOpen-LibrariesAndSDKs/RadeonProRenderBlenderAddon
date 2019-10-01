import bpy

import pyrpr
from .engine import Engine
from rprblender.export import object, camera, particle, world
from . import context

from rprblender.utils import logging
log = logging.Log(tag='PreviewEngine')


class PreviewEngine(Engine):
    """ Render engine for preview material, lights, environment """

    TYPE = 'PREVIEW'

    def __init__(self, rpr_engine):
        super().__init__(rpr_engine)

        self.is_synced = False
        self.render_samples = 0
        self.render_update_samples = 1

    def render(self):
        if not self.is_synced:
            return

        log(f"Start render [{self.rpr_context.width}, {self.rpr_context.height}]")
        sample = 0
        while sample < self.render_samples:
            if self.rpr_engine.test_break():
                break

            update_samples = min(self.render_update_samples, self.render_samples - sample)

            log(f"  samples: {sample} +{update_samples} / {self.render_samples}")
            self.rpr_context.set_parameter(pyrpr.CONTEXT_ITERATIONS, update_samples)
            self.rpr_context.render(restart=(sample == 0))
            self.rpr_context.resolve()
            self.update_render_result((0, 0), (self.rpr_context.width,
                                               self.rpr_context.height))

            sample += update_samples

        log('Finish render')

    def sync(self, depsgraph):
        log('Start syncing')
        self.is_synced = False

        scene = depsgraph.scene
        settings_scene = bpy.context.scene

        settings_scene.rpr.init_rpr_context(self.rpr_context, is_final_engine=False)
        self.rpr_context.resize(scene.render.resolution_x, scene.render.resolution_y)

        self.rpr_context.scene.set_name(scene.name)

        # export visible objects
        for obj in self.depsgraph_objects(depsgraph):
            object.sync(self.rpr_context, obj)

            if len(obj.particle_systems):
                # export particles
                for particle_system in obj.particle_systems:
                    particle.sync(self.rpr_context, particle_system, obj)

        # export camera
        camera.sync(self.rpr_context, depsgraph.objects[depsgraph.scene.camera.name])

        # export world only if active_material.use_preview_world is enabled
        preview_obj = next(obj for obj in self.depsgraph_objects(depsgraph)
                               if obj.name.startswith('preview_'))
        if preview_obj.active_material.use_preview_world:
            world.sync(self.rpr_context, settings_scene.world)

        self.rpr_context.enable_aov(pyrpr.AOV_COLOR)
        self.rpr_context.enable_aov(pyrpr.AOV_DEPTH)

        self.rpr_context.set_parameter(pyrpr.CONTEXT_PREVIEW, True)
        settings_scene.rpr.export_ray_depth(self.rpr_context)
        settings_scene.rpr.export_pixel_filter(self.rpr_context)

        self.render_samples = settings_scene.rpr.viewport_limits.preview_samples
        self.render_update_samples = settings_scene.rpr.viewport_limits.preview_update_samples

        self.is_synced = True
        log('Finish sync')
