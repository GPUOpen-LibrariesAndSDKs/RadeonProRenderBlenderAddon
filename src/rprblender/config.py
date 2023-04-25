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
from .utils import logging

logging.limit_log('', level_show_min=logging.INFO)

pyrpr_log_calls = False
pyrprimagefilters_log_calls = False
pyrprgltf_log_calls = False
hybrid_unsupported_log_warn = False
hybridpro_unsupported_log_warn = False

material_library_path = None

use_opencl = False
enable_hybrid = True
enable_hybridpro = True

disable_athena_report = False
clean_athena_files = True


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

