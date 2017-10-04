#!python3
import bpy
import os
import json
import tempfile
import threading
import time
import traceback
import urllib.request, urllib.error

from . import rpraddon
from . import logging
from .nodes import RPRPanel
from . import config
from . import versions
from . import helpers


class DownloadAddonJsonThread(threading.Thread):
    def __init__(self):
        self.json_obj = None
        super().__init__()

    def run(self):
        self.json_obj = None
        logging.info('DownloadAddonJsonThread started...')
        try:
            url = config.url_json_version
            logging.info('Download from: ', url)

            with urllib.request.urlopen(url, timeout=60) as url_handle:
                data = url_handle.read()
                str = data.decode("utf-8")
                self.json_obj = json.loads(str)
                logging.info('thread json_obj: ', self.json_obj)
            # time.sleep(5)
        except:
            logging.error("Can't download json file. ")
            #print("Unexpected exception: " + traceback.format_exc())
        finally:
            logging.info('DownloadAddonJsonThread finished.')


class DownloadAddonMsiThread(threading.Thread):
    def __init__(self, url):
        self.url = url
        super().__init__()
        self.downloaded = 0
        self.total_size = 0
        self.terminate = False
        self.msi_file_name = ''

    def run(self):
        logging.info('DownloadAddonMsiThread started...')
        try:
            block_size = 32768
            tmp_file = tempfile.NamedTemporaryFile(prefix='rpr_', suffix='.msi', delete=False)
            logging.info('Save to temporary file: ', tmp_file.name)
            logging.info('Download from: ', self.url)

            with urllib.request.urlopen(self.url, timeout=60) as response:
                self.total_size = int(response.getheader("Content-Length"))
                logging.info('file_size: ', self.total_size)
                self.downloaded = 0
                while True:
                    if self.terminate:
                        logging.info('   DownloadAddonMsiThread was terminated')
                        break
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    tmp_file.write(buffer)
                    self.downloaded += len(buffer)

            tmp_file.close()

            if self.terminate:
                os.unlink(tmp_file.name)
            else:
                self.msi_file_name = tmp_file.name
        except:
            logging.error("Can't download Msi file. ")
            #print("Unexpected exception: " + traceback.format_exc())
        finally:
            logging.info('DownloadAddonMsiThread finished.')



@rpraddon.register_class
class RPRRender_PT_Update(RPRPanel, bpy.types.Panel):
    bl_label = "RPR Update Addon"

    json_obj = None
    json_thread = None

    def check_updates(self):
        # need check delay
        if not self.json_thread:
            self.json_thread = DownloadAddonJsonThread()
            self.json_thread.start()
        elif not self.json_thread.isAlive():
            self.json_obj = self.json_thread.json_obj

    @classmethod
    def poll(cls, context):
        cls.check_updates(cls)

        # check update version
        if cls.json_obj:
            current_version = versions.get_addon_version()
            update_version = cls.json_obj['version']
            v = tuple(int(p) for p in update_version.split('.'))
            if not versions.is_older_than_version(current_version, v):
                return False

        # hide all menus
        if cls.json_obj and cls.is_notify(cls):
            RPRPanel.hide_rpr_ui = cls.json_obj['mustUpdate'] == 'true'
        else:
            RPRPanel.hide_rpr_ui = False

        rd = context.scene.render
        return cls.json_obj and rd.engine in cls.COMPAT_ENGINES

    def is_notify(self):
        settings = helpers.get_user_settings()
        if not settings.notify_update_addon and not OpRemindUpdateAddon.remind_later:
            OpRemindUpdateAddon.remind_later = True
        return settings.notify_update_addon and not OpRemindUpdateAddon.remind_later

    def draw(self, context):
        layout = self.layout
        rpr = context.scene.rpr

        col = layout.column()
        must_update = self.json_obj['mustUpdate']

        split = col.split(percentage=0.5)
        col1 = split.column()
        split = split.split()
        col2 = split.column(align=True)

        col1.label('New Version available:')
        if must_update:
            col2.label('Critical update', icon='ERROR')
        else:
            col2.label('')

        col1.label('Version: ')
        col2.label(self.json_obj['version'])
        col1.label('Date: ')
        col2.label(self.json_obj['date'])

        col.label(self.json_obj['changes'])

        if OpUpdateAddon.thread:
            if OpUpdateAddon.thread.is_alive():
                percent = 0
                if OpUpdateAddon.thread.total_size:
                    percent = OpUpdateAddon.thread.downloaded /OpUpdateAddon.thread.total_size * 100.0

                downloaded_mb = OpUpdateAddon.thread.downloaded / (1024 * 1024)
                s = str('Downloaded: %.1f%% (%.2fmb)' % (percent, downloaded_mb))

                split = col.row().split(percentage=0.66)
                split.column().label(s)
                split.column().operator("rpr.op_update_addon", text='Cancel', icon='CANCEL').op = 'cancel'
            else:
                if OpUpdateAddon.thread.msi_file_name:
                    col.operator("rpr.op_update_addon", text='Install').op = 'install'
                    col.label('Please close Blender after running installer', icon='ERROR')
                else:
                    OpUpdateAddon.thread = None
        else:
            h = col.operator("rpr.op_update_addon", text='Update Addon')
            h.op = 'download'
            if self.json_obj:
                h.url = self.json_obj['url']

            if must_update and self.is_notify():
                row = col.row()
                row.operator("rpr.op_remind", text='Remind me later').op = 'later'
                #row.operator("rpr.op_remind", text='Never remind').op = 'never'

            settings = helpers.get_user_settings()
            col.prop(settings, 'notify_update_addon')


@rpraddon.register_class
class OpRemindUpdateAddon(bpy.types.Operator):
    bl_idname = "rpr.op_remind"
    bl_label = "Remind Update Addon"

    remind_later = False
    op = bpy.props.StringProperty()

    def execute(self, context):
        if self.op == 'later':
            OpRemindUpdateAddon.remind_later = True
        return {'FINISHED'}


@rpraddon.register_class
class OpUpdateAddon(bpy.types.Operator):
    bl_idname = "rpr.op_update_addon"
    bl_label = "Update Addon"

    thread = None

    op = bpy.props.StringProperty()
    url = bpy.props.StringProperty()

    def execute(self, context):
        logging.info('OpUpdateAddon op:', self.op)
        if self.op == 'download':
            if not OpUpdateAddon.thread:
                logging.info('create download thread...')
                # self.url = '...'
                OpUpdateAddon.thread = DownloadAddonMsiThread(self.url)
                OpUpdateAddon.thread.start()
                #OpUpdateAddon.thread.msi_file_name = '...'
        elif self.op == 'install':
            if OpUpdateAddon.thread.msi_file_name:
                cmd = str('msiexec /i %s' % OpUpdateAddon.thread.msi_file_name)
                logging.info('cmd: ', cmd)
                import subprocess
                subprocess.Popen(cmd)
        else:
            if OpUpdateAddon.thread:
                if OpUpdateAddon.thread.is_alive():
                    logging.info('Cancel downloading...')
                    OpUpdateAddon.thread.terminate = True

        return {'FINISHED'}


