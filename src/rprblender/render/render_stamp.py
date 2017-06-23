import platform

if 'Windows' == platform.system():
    from .render_stamp_windows import render_stamp

    render_stamp_supported = True
else:
    def render_stamp(text, context, image, image_width, image_height, channels, iter, frame_time):
        pass
    render_stamp_supported = False
