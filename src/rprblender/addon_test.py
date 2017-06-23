import bpy

from rprblender.addon import Addon


def test_register_decorator_order():
    my_addon = Addon()

    register_order = []
    unregister_order = []

    @my_addon.register_class
    class A(bpy.types.Operator):
        bl_label = 'addon_test_register'
        bl_idname = 'rpr.addon_test_register_a'

        @classmethod
        def register(cls):
            register_order.append('A')

        @classmethod
        def unregister(cls):
            unregister_order.append('A')

    @my_addon.register_class
    class B(bpy.types.Operator):
        bl_label = 'addon_test_register'
        bl_idname = 'rpr.addon_test_register_b'

        @classmethod
        def register(cls):
            register_order.append('B')

        @classmethod
        def unregister(cls):
            unregister_order.append('B')

    my_addon.register_all()
    assert ['A', 'B'] == register_order

    my_addon.unregister_all()
    assert ['B', 'A'] == unregister_order
