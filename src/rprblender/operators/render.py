import webbrowser
import bpy

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

    page: bpy.props.StringProperty(name="Page")

    def execute(self, context):
        url = {
            'main_site':     "https://pro.radeon.com/en/software/prorender/",
            'documentation': "https://pro.radeon.com/en/software/prorender/",
            'downloads':     "https://pro.radeon.com/en/software/prorender/blender/",
            'community':     "https://community.amd.com/community/prorender/",
            'bug_reports':   "https://community.amd.com/community/prorender/blender/",
        }[self.page]

        webbrowser.open(url)
        return {'FINISHED'}
