import bpy

from rprblender import properties


class TestRenderingLimits:
    def test_time(self):
        bpy.types.Scene.my_render_limits = bpy.props.PointerProperty(type=properties.RenderingLimits)
        p = bpy.context.scene.my_render_limits

        assert p.enable
        assert 'ITER' == p.type
        assert 50 == p.iterations

        p.type = 'TIME'
        assert 0 == p.minutes

        p.seconds = 63
        assert 3 == p.seconds
        assert 1 == p.minutes

        p.hours = 100
        p.seconds = 7261
        assert 1 == p.seconds
        assert 2 == p.minutes
        assert 102 == p.hours

        p.hours = 1
        assert 3721 == p.time
