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

    def execute(self, context):
        # enable use_nodes compositing if not already
        bpy.context.scene.use_nodes = True
        nt = bpy.context.scene.node_tree
        view_layer = context.view_layer

        # add compositor node
        denoiser_node = next((node for node in nt.nodes if isinstance(node, bpy.types.CompositorNodeDenoise)), None)
        if not denoiser_node:
            denoiser_node = nt.nodes.new(type="CompositorNodeDenoise")

        denoiser_node.mute = False

        # adds nescessary AOVS
        view_layer.rpr.enable_aov_by_name('Shading Normal')
        view_layer.rpr.enable_aov_by_name('Diffuse Albedo')

        # find render output node
        output_node = next((node for node in nt.nodes if isinstance(node, bpy.types.CompositorNodeComposite)), None)

        # find render result node
        render_node = next((node for node in nt.nodes if isinstance(node, bpy.types.CompositorNodeRLayers)), None)

        # hook up nodes
        if output_node is None or render_node is None:
            return {'FINISHED'}
        nt.links.new(render_node.outputs['Image'], denoiser_node.inputs['Image'])
        nt.links.new(render_node.outputs['Shading Normal'], denoiser_node.inputs['Normal'])
        nt.links.new(render_node.outputs['Diffuse Albedo'], denoiser_node.inputs['Albedo'])

        nt.links.new(denoiser_node.outputs['Image'], output_node.inputs['Image'])

        return {'FINISHED'}
