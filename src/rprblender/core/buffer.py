import bpy
import numpy as np

import pyrpr

from rprblender import config, logging
from rprblender.helpers import CallLogger

logged = CallLogger(tag="core.buffer").logged


@logged
def create_core_buffer_from_color_ramp(context, color_ramp):
    ''' creates a core buffer object ''' 

    logging.debug("create_core_buffer_from_color_ramp:", color_ramp, tag="core.image")

    data = extract_buffer_from_blender_color_ramp(color_ramp)

    desc = pyrpr.ffi.new("rpr_buffer_desc*")
    desc.nb_element = len(data);
    desc.element_type = pyrpr.BUFFER_ELEMENT_TYPE_FLOAT32;
    desc.element_channel_size = len(data[0]);

    handle = pyrpr.Buffer()
    pyrpr.ContextCreateBuffer(context, desc, 
                              pyrpr.ffi.cast("float *", data.ctypes.data), 
                              handle._handle_ptr)
    return handle

@logged
def extract_buffer_from_blender_color_ramp(color_ramp):
    ''' creates a c array from ramp '''
    
    logging.debug("extract_buffer_from_blender_color_ramp:", color_ramp, tag="core.image")
    data = []
    buffer_size = config.ramp_buffer_size
    for i in range(0,buffer_size):
        data.append(color_ramp.evaluate(float(i/(buffer_size - 1))))

        
    data = np.array(data, dtype=np.float32)
    return np.ascontiguousarray(data)


