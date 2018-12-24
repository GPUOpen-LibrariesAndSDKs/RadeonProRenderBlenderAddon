import pyrpr

from . import RPR_Panel


class RPR_RENDER_PT_devices(RPR_Panel):
    bl_label = "RPR Render Devices"
    bl_context = 'render'

    def draw(self, context):
        devices = context.scene.rpr.devices

        if pyrpr.Context.cpu_device:
            row = self.layout.split(factor=0.25, align=True)
            col = row.column()
            col.prop(devices, 'use_cpu')
            col = row.column()
            box = col.box()
            box.enabled = devices.use_cpu
            box.label(text=pyrpr.Context.cpu_device['name'])
            box.prop(devices, 'cpu_threads')

        if len(pyrpr.Context.gpu_devices) > 0:
            row = self.layout.split(factor=0.25, align=True)
            col = row.column()
            col.prop(devices, 'use_gpu')
            col = row.column()
            box = col.box()
            box.enabled = devices.use_gpu
            for i in range(len(devices.gpu_states)):
                box.prop(devices, "gpu_states", index=i, text=pyrpr.Context.gpu_devices[i]['name'])


class RPR_RENDER_PT_sampling(RPR_Panel):
    bl_label = "RPR Sampling"
    bl_context = 'render'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.prop(context.scene.rpr.sampling, 'iterations')
        self.layout.prop(context.scene.rpr.sampling, 'iteration_samples')


class RPR_RENDER_PT_light_paths(RPR_Panel):
    bl_label = "RPR Light Paths"
    bl_context = 'render'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        # This is a parent Panel for (RPR_RENDER_PT_light_max_bounces, RPR_RENDER_PT_light_clamping)
        pass


class RPR_RENDER_PT_light_max_bounces(RPR_Panel):
    bl_label = "Max Ray Depth"
    bl_parent_id = 'RPR_RENDER_PT_light_paths'

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        light_paths = context.scene.rpr.light_paths

        self.layout.prop(light_paths, 'max_ray_depth', slider=True)

        col = self.layout.column(align=True)
        col.prop(light_paths, 'max_diffuse_depth', slider=True)
        col.prop(light_paths, 'max_glossy_depth', slider=True)
        col.prop(light_paths, 'max_refraction_depth', slider=True)
        col.prop(light_paths, 'max_glossy_refraction_depth', slider=True)
        col.prop(light_paths, 'max_shadow_depth', slider=True)

        self.layout.prop(light_paths, 'ray_epsilon', slider=True)


class RPR_RENDER_PT_light_clamping(RPR_Panel):
    bl_label = "Clamping"
    bl_parent_id = 'RPR_RENDER_PT_light_paths'

    def draw_header(self, context):
        self.layout.prop(context.scene.rpr.light_paths, 'use_clamp_radiance', text="")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        light_paths = context.scene.rpr.light_paths

        col = self.layout.column()
        col.enabled = light_paths.use_clamp_radiance
        col.prop(light_paths, 'clamp_radiance')
