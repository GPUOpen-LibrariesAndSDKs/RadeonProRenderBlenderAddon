from .utils import logging

logging.limit_log('', level_show_min=logging.INFO)

pyrpr_log_calls = False
pyrprx_log_calls = False
pyrprimagefilters_log_calls = False
pyrprgltf_log_calls = False

use_gl_interop = True

material_library_path = None

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

