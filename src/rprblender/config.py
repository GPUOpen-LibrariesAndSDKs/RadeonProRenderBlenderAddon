pyrpr_log_calls = False
pyrprx_log_calls = False

from . import logging
logging.limit_log('', level_show_min=logging.INFO)

debug = False

rpr_image_loading = True
node_thumbnail_enabled = True
preview_enable = True

material_library_path = None

cycles_convert_enabled = True

image_cache_blender = True
image_cache_core = True

try:
    # configdev.py example for logging setup:
    # from . import logging
    # # display log records from 'rpr.default' or below unless they have INFO level or higher(always show them)
    # logging.limit_log('default', logging.INFO)
    # from . import config
    # # log all core calls
    # config.pyrpr_log_calls = True

    from . import configdev
    logging.info('loaded configdev', tag='')
except ImportError:
    pass
