import pyrpr

from . import RPR_Panel


class RPR_RENDER_PT_devices(RPR_Panel):
    bl_label = "Render Devices"
    bl_context = 'render'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        rpr_scene = context.scene.rpr
        col = layout.column()
        col.prop(rpr_scene, 'devices')
        layout.separator()

        def draw_cpu():
            col = layout.column(align=True)
            col.label(text=pyrpr.Context.cpu_device['name'])
            col.prop(rpr_scene, 'cpu_threads')

        def draw_gpu():
            col = layout.column(align=True)
            col.use_property_split = False
            if len(pyrpr.Context.gpu_devices) > 1:
                for i in range(len(rpr_scene.gpu_states)):
                    col.prop(rpr_scene, 'gpu_states', index=i, text=pyrpr.Context.gpu_devices[i]['name'])
            else:
                col.label(text=pyrpr.Context.gpu_devices[0]['name'])

        if rpr_scene.devices == 'CPU':
            draw_cpu()
        elif rpr_scene.devices == 'GPU':
            draw_gpu()
        else:
            draw_cpu()
            layout.separator()
            draw_gpu()


class RPR_RENDER_PT_limits(RPR_Panel):
    bl_label = "Render Limits"
    bl_context = 'render'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        limits = context.scene.rpr.limits

        col = self.layout.column()
        col.prop(limits, 'type')
        if limits.type == 'ITERATIONS':
            col1 = col.column(align=True)
            col1.prop(limits, 'iterations')
            col1.prop(limits, 'iteration_samples')
        else:
            col.prop(limits, 'seconds')


class RPR_RENDER_PT_viewport_limits(RPR_Panel):
    bl_label = "Viewport Render Limits"
    bl_parent_id = 'RPR_RENDER_PT_limits'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        col = self.layout.column()

        limits = context.scene.rpr.viewport_limits

        col = self.layout.column()
        col.prop(limits, 'type')
        if limits.type == 'ITERATIONS':
            col.prop(limits, 'iterations')
        else:
            col.prop(limits, 'seconds')


class RPR_RENDER_PT_quality(RPR_Panel):
    bl_label = "Render Quality"
    bl_context = 'render'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        # This is a parent Panel for (RPR_RENDER_PT_max_ray_depth, RPR_RENDER_PT_light_clamping)
        pass


class RPR_RENDER_PT_max_ray_depth(RPR_Panel):
    bl_label = "Max Ray Depth"
    bl_parent_id = 'RPR_RENDER_PT_quality'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr_scene = context.scene.rpr

        self.layout.prop(rpr_scene, 'max_ray_depth', slider=True)

        col = self.layout.column(align=True)
        col.prop(rpr_scene, 'diffuse_depth', slider=True)
        col.prop(rpr_scene, 'glossy_depth', slider=True)
        col.prop(rpr_scene, 'refraction_depth', slider=True)
        col.prop(rpr_scene, 'glossy_refraction_depth', slider=True)
        col.prop(rpr_scene, 'shadow_depth', slider=True)

        self.layout.prop(rpr_scene, 'ray_cast_epsilon', slider=True)


class RPR_RENDER_PT_light_clamping(RPR_Panel):
    bl_label = "Clamping"
    bl_parent_id = 'RPR_RENDER_PT_quality'

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr, 'use_clamp_radiance', text="")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        rpr_scene = context.scene.rpr

        col = self.layout.column()
        col.enabled = rpr_scene.use_clamp_radiance
        col.prop(rpr_scene, 'clamp_radiance')


class RPR_RENDER_PT_effects(RPR_Panel):
    bl_label = "Render Effects"
    bl_context = 'render'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        rpr_scene = context.scene.rpr
        col = layout.column()
        col.prop(rpr_scene, 'use_render_stamp')
        col.prop(rpr_scene, 'render_stamp', text="")


class RPR_RENDER_PT_help_about(RPR_Panel):
    bl_label = "Help/About"
    bl_context = 'render'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        layout.label(text="Help/About page")
