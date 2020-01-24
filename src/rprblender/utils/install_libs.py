
from rprblender.utils.logging import Log
log = Log(tag="install_libs")


def ensure_boto3() -> None:
    """
    Try to install boto3 library at the addon launch time
    """
    # use this snippet to install boto3 library with all the dependencies if absent at the addon launch time
    # note: still it will be available at the next Blender launch only
    # TODO: check if scene reload works as well (note: even then it couldn't be used at all; just to be sure on how it works)
    try:
        import boto3
    except ImportError:
        log.info("Installing boto3 library...")
        import bpy
        import subprocess
        # subprocess.call([bpy.app.binary_path_python, "-m", "ensurepip"])  # seems to be working fine without it
        subprocess.call([bpy.app.binary_path_python, "-m", "pip", "install", "--upgrade", "pip", "--user"])
        subprocess.call([bpy.app.binary_path_python, "-m", "pip", "install", "boto3", "--user"])
        log.info("Library boto3 should be available after Blender restart")
