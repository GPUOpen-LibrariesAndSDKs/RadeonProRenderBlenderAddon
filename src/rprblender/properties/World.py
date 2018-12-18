import bpy
import mathutils
import numpy

from . import RPR_Panel, RPR_Operator, RPR_Properties
from rprblender import logging


def log(*args):
    logging.info(*args, tag='World')


class RPR_WORLD_OT_convert_cycles_environment(RPR_Operator):
    bl_idname = 'rpr.convert_cycles_environment'
    bl_label = "Convert Cycles Environment lightning settings"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return super().poll(context) and context.scene.world

    def execute(self, context: bpy.types.Context):
        log("Converting Cycles environment settings {}".format(context))

        return {'FINISHED'}


class RPR_WORLD_OP_create_environment_gizmo(bpy.types.Operator):
    bl_idname = "rpr.op_create_environment_gizmo"
    bl_label = "Create Environment Gizmo"

    rotation: bpy.props.FloatVectorProperty(
        name='Rotation', description='Rotation',
        subtype='EULER', size=3,
    )
    object_name: str = 'EnvObject'
    collection_name: str = 'SupportObjectsCollection'

    def execute(self, context):
        obj = bpy.data.objects.new(self.object_name, None)
        obj.empty_display_size = 3.0
        obj.empty_display_type = 'PLAIN_AXES'
        obj.location = (0, 0, 0)

        rpr_collection = context.scene.collection.children.get(self.collection_name)
        if not rpr_collection:
            rpr_collection = bpy.data.collections.new(self.collection_name)
            context.scene.collection.children.link(rpr_collection)
        rpr_collection.objects.link(obj)

        obj.rotation_euler = self.rotation

        context.scene.world.rpr.gizmo = obj.name
        return {'FINISHED'}


class RPR_WORLD_PROP_environment_ibl(RPR_Properties):
    bl_label = "RPR IBL Settings"

    ibl_type: bpy.props.EnumProperty(
        name="IBL Type",
        items=(('COLOR', "Color", "Use solid color for lighting"),
               ('IBL', "IBL Map", "Use IBL Map for lighting"),
               ),
        description="IBL Type",
        default='COLOR',
    )
    color: bpy.props.FloatVectorProperty(
        name='Color',
        description="Color to use when as a constant environment light",
        subtype='COLOR', min=0.0, max=1.0, size=3,
        default=(0.5, 0.5, 0.5)
    )
    intensity: bpy.props.FloatProperty(
        name="Intensity",
        description="Intensity",
        min=0.0, default=1.0,
    )
    ibl_map: bpy.props.StringProperty(
        name='Image-Base Lighting Map',
        description='Image-Base Lighting Map',
        subtype='FILE_PATH'
    )

    def sync(self, rpr_context):
        ibl = rpr_context.create_light('Environment', 'environment')
        ibl.set_group_id(0)

        # TODO As soon as portal light type ready support it here
        # for obj_key in self.portal_lights_meshes:
        #     ibl.attach_portal(self.core_scene, self.get_synced_obj(obj_key).core_obj)

        if self.ibl_type == 'COLOR':
            image = rpr_context.create_image_data(numpy.full((2, 2, 4), tuple(self.color) + (1,), dtype=numpy.float32))
            ibl.set_image(image)
        elif self.ibl_type == 'IBL':
            try:
                image = rpr_context.create_image_file(self.ibl_map)
            except Exception as e:
                log("Cant's read environment image: {} reason: {}".format(self.ibl_map, str(e)))
                image = rpr_context.create_image_data(numpy.full((2, 2, 4), (1, 0, 1, 1), dtype=numpy.float32))

            ibl.set_image(image)
            ibl.set_intensity_scale(self.intensity)

        rpr_context.scene.attach(ibl)
        return ibl

    def draw(self, layout):

        layout.row().prop(self, 'ibl_type', expand=True)
        if self.ibl_type == 'COLOR':
            layout.row().prop(self, 'color')
        else:
            layout.row().prop(self, 'ibl_map')
            layout.row().prop(self, 'intensity')


class RPR_WORLD_PROP_environment_sun_sky(RPR_Properties):
    bl_label = "RPR Sun&Sky Settings"

    def sync(self, rpr_context):
        log("RPR_WORLD_PROP_environment_sun_sky.sync()")

    def draw(self, layout):
        pass


class RPR_WORLD_PROP_environment(RPR_Properties):
    bl_idname = "rpr_world_prop_environment"
    bl_label = "RPR Environment Settings"

    enabled: bpy.props.BoolProperty(default=True)
    # environment
    light_type: bpy.props.EnumProperty(
        name="IBL Type",
        items=(('IBL', "IBL Map", "Use IBL environment light"),
               ('SUN_SKY', "Sun & Sky", "Use Sun&Sky"),
               ),
        description="Environment light type",
        default='IBL',
    )
    ibl: bpy.props.PointerProperty(type=RPR_WORLD_PROP_environment_ibl)
    sun_sky: bpy.props.PointerProperty(type=RPR_WORLD_PROP_environment_sun_sky)
    # overrides

    # environment transform gizmo
    def update_gizmo_rotation(self, context):
        if self.gizmo in bpy.data.objects:
            obj = bpy.data.objects[self.gizmo]
            obj.rotation_euler = self.gizmo_rotation

    def update_gizmo(self, context):
        if self.gizmo in bpy.data.objects:
            obj = bpy.data.objects[self.gizmo]
            self['gizmo_rotation'] = obj.rotation_euler

    gizmo_rotation: bpy.props.FloatVectorProperty(
        name='Rotation', description='Rotation',
        subtype='EULER', size=3,
        update=update_gizmo_rotation
    )

    gizmo: bpy.props.StringProperty(
        name="Gizmo",
        description="Environment Helper",
        update=update_gizmo
    )

    def sync(self, rpr_context):
        log("Environment synchronization")
        if self.enabled:
            if self.light_type == 'IBL':
                ibl = self.ibl.sync(rpr_context)
                if self.gizmo:
                    self.update_gizmo(None)
                rotation = self.gizmo_rotation
                rotation_updated = (rotation[0], rotation[1], rotation[2] + numpy.pi)
                self.set_rotation(ibl, rotation_updated)

    @staticmethod
    def set_rotation(ibl, rotation_gizmo):
        rotation_gizmo = (-rotation_gizmo[0], -rotation_gizmo[1], -rotation_gizmo[2])
        euler = mathutils.Euler(rotation_gizmo)
        rotation_matrix = numpy.array(euler.to_matrix(), dtype=numpy.float32)
        fixup = numpy.array([[1, 0, 0],
                          [0, 0, 1],
                          [0, 1, 1]], dtype=numpy.float32)
        matrix = numpy.identity(4, dtype=numpy.float32)
        matrix[:3, :3] = numpy.dot(fixup, rotation_matrix)

        ibl.set_transform(matrix, False)

    def draw(self, layout):
        layout.row().prop(self, 'light_type', expand=True)
        if self.light_type == 'IBL':
            self.ibl.draw(layout)
        else:
            self.sun_sky.draw(layout)

    @classmethod
    def register(cls):
        bpy.types.World.rpr = bpy.props.PointerProperty(
            name="RPR World Settings",
            description="RPR Environment Settings",
            type=cls,
        )

    @classmethod
    def unregister(cls):
        del bpy.types.World.rpr


class RPR_WORLD_PT_environment(RPR_Panel):
    bl_idname = "rpr_world_pt_environment"
    bl_label = "RPR Environment Light"
    bl_space_type = "PROPERTIES"
    bl_context = 'world'

    @classmethod
    def poll(cls, context):
        return super().poll(context)  # and context.scene.world.rpr

    def sync(self, rpr_context):
        pass

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        environment = scene.world.rpr

        if context.scene.world.rpr.enabled:
            environment.draw(layout)
            self.draw_environment_gizmo(layout.column(), context)

    def draw_header(self, context):
        self.layout.prop(context.scene.world.rpr, 'enabled', text="")

    def draw_environment_gizmo(self, column, context):
        box = column.box()
        column1, column2, is_row = self.create_ui_autosize_column(context, box)
        column1.label(text='Object:')
        row = column1.row(align=True)
        row.prop_search(context.scene.world.rpr, 'gizmo', bpy.data, 'objects', text='')
        if not context.scene.world.rpr.gizmo:
            gizmo = row.operator("rpr.op_create_environment_gizmo", icon='ZOOM_IN', text="")
            if gizmo:
                gizmo.rotation = context.scene.world.rpr.gizmo_rotation
        column2.prop(context.scene.world.rpr, 'gizmo_rotation')


classes_to_register = (RPR_WORLD_OP_create_environment_gizmo,
                       RPR_WORLD_PROP_environment_ibl, RPR_WORLD_PROP_environment_sun_sky,
                       RPR_WORLD_PROP_environment,
                       RPR_WORLD_PT_environment,)
