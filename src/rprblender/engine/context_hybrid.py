import pyrpr
import pyhybrid

from . import context

from rprblender.utils import logging
log = logging.Log(tag='context_hybrid')


class RPRContext(context.RPRContext):
    """ Manager of pyhybrid and pyrpr calls """

    _Context = pyhybrid.Context
    _Scene = pyhybrid.Scene

    _MaterialNode = pyhybrid.MaterialNode

    _PointLight = pyhybrid.PointLight
    _DirectionalLight = pyhybrid.DirectionalLight
    _SpotLight = pyhybrid.SpotLight
    _IESLight = pyhybrid.IESLight
    _AreaLight = pyhybrid.AreaLight
    _EnvironmentLight = pyhybrid.EnvironmentLight

    _Camera = pyhybrid.Camera
    _Shape = pyhybrid.Shape
    _Mesh = pyhybrid.Mesh
    _Instance = pyhybrid.Instance
    _Curve = pyhybrid.Curve
    _HeteroVolume = pyhybrid.HeteroVolume

    _PostEffect = pyhybrid.PostEffect

    def init(self, context_flags, context_props):
        context_flags -= {pyrpr.CREATION_FLAGS_ENABLE_GL_INTEROP}
        if context_props[0] == pyrpr.CONTEXT_SAMPLER_TYPE:
            context_props = context_props[2:]
        super().init(context_flags, context_props)

    def resolve(self):
        pass

    def enable_aov(self, aov_type):
        if aov_type == pyrpr.AOV_VARIANCE:
            log("Unsupported RPRContext.enable_aov(AOV_VARIANCE)")
            return

        if self.is_aov_enabled(aov_type):
            return

        fbs = {}
        fbs['aov'] = pyrpr.FrameBuffer(self.context, self.width, self.height)
        fbs['aov'].set_name("%d_aov" % aov_type)
        fbs['res'] = fbs['aov']
        self.context.attach_aov(aov_type, fbs['aov'])

        self.frame_buffers_aovs[aov_type] = fbs

    def create_material_node(self, material_type):
        if material_type not in pyhybrid.SUPPORTED_MATERIAL_NODES:
            log.warn("Unsupported RPRContext.create_material_node", material_type)
            return pyhybrid.EmptyMaterialNode(material_type)

        return super().create_material_node(material_type)

    def create_buffer(self, data, dtype):
        return None

    def get_parameter(self, name):
        return self.context.parameters.get(name, 0)

    def sync_catchers(self):
        pass
