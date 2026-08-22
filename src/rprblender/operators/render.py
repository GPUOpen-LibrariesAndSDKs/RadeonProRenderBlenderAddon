#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
import webbrowser
import bpy
import shutil

from . import RPR_Operator
from rprblender.utils import BLENDER_VERSION, get_compositor_node_tree


class RPR_RENDER_OP_open_web_page(RPR_Operator):
    '''
    Operator to open web pages. Available page types:
    - 'main_site'
    - 'documentation'
    - 'downloads'
    - 'community'
    - 'bug_reports'
    '''

    bl_idname = "rpr.op_open_web_page"
    bl_label = "Open Web Page"
    bl_description = "Open web page in browser"

    page: bpy.props.StringProperty(name="Page")

    def execute(self, context):
        url = {
            'main_site':     "https://www.amd.com/en/technologies/radeon-prorender",
            'documentation': "https://radeon-pro.github.io/RadeonProRenderDocs/plugins/blender/about.html",
            'downloads':     "https://www.amd.com/en/technologies/radeon-prorender-downloads",
            'community':     "https://community.amd.com/t5/blender-discussions/bd-p/blender-discussions",
            'bug_reports':   "https://github.com/GPUOpen-LibrariesAndSDKs/RadeonProRenderBlenderAddon/issues",
        }[self.page]

        webbrowser.open(url)
        return {'FINISHED'}


class RPR_RENDER_OP_clear_cache(RPR_Operator):
    '''
    Clear texture cache dir
    '''

    bl_idname = "rpr.op_clear_tex_cache"
    bl_label = "Clear Cache"
    bl_description = "Clear Texture Cache"

    def execute(self, context):
        shutil.rmtree(context.scene.rpr.texture_cache_dir)
        return {'FINISHED'}


class RPR_RENDER_OP_add_denoiser_node(RPR_Operator):
    '''
    Operator to add blender denoiser compositor node
    also enables needed AOVs
    '''

    bl_idname = "rpr.add_denoiser_node"
    bl_label = "Add Compositor Denoise Node"
    bl_description = "Adds a denoiser node in compositor and hooks up for RPR."

    def get_compositor_tree(self, context):
        """
        Return the scene compositor node tree together with its output socket, creating whatever is
        missing. Blender 5.0 turned the compositing node tree into a standalone data-block reached
        through 'compositing_node_group' and dropped the Composite node in favour of Group Output.
        """
        scene = context.scene

        if BLENDER_VERSION < "5.0":
            # enable use_nodes compositing if not already, it also fills the tree with the
            # Render Layers and Composite nodes
            scene.use_nodes = True
            nt = get_compositor_node_tree(scene)
            output_node = next(
                (node for node in nt.nodes if isinstance(node, bpy.types.CompositorNodeComposite)), None)
            return nt, output_node.inputs['Image'] if output_node else None

        nt = get_compositor_node_tree(scene)
        if not nt:
            nt = bpy.data.node_groups.new("Compositing Nodetree", "CompositorNodeTree")
            scene.compositing_node_group = nt

        output_node = next(
            (node for node in nt.nodes if isinstance(node, bpy.types.NodeGroupOutput)), None)
        if not output_node:
            output_node = nt.nodes.new(type="NodeGroupOutput")

        # the first Group Output input has to be a Color socket to receive the rendered image
        if not any(getattr(item, 'in_out', None) == 'OUTPUT' for item in nt.interface.items_tree):
            nt.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')

        return nt, output_node.inputs[0]

    def execute(self, context):
        view_layer = context.view_layer

        nt, output_socket = self.get_compositor_tree(context)

        # add compositor node
        denoiser_node = next((node for node in nt.nodes if isinstance(node, bpy.types.CompositorNodeDenoise)), None)
        if not denoiser_node:
            denoiser_node = nt.nodes.new(type="CompositorNodeDenoise")

        denoiser_node.mute = False

        # adds nescessary AOVS
        view_layer.rpr.enable_aov_by_name('Shading Normal')
        view_layer.rpr.enable_aov_by_name('Diffuse Albedo')

        # find render result node
        render_node = next((node for node in nt.nodes if isinstance(node, bpy.types.CompositorNodeRLayers)), None)
        if not render_node and BLENDER_VERSION >= "5.0":
            # a freshly created 5.x tree is empty, 4.x got this node from use_nodes
            render_node = nt.nodes.new(type="CompositorNodeRLayers")

        # hook up nodes
        if output_socket is None or render_node is None:
            return {'FINISHED'}
        nt.links.new(render_node.outputs['Image'], denoiser_node.inputs['Image'])
        nt.links.new(render_node.outputs['Shading Normal'], denoiser_node.inputs['Normal'])
        nt.links.new(render_node.outputs['Diffuse Albedo'], denoiser_node.inputs['Albedo'])

        nt.links.new(denoiser_node.outputs['Image'], output_socket)

        return {'FINISHED'}
