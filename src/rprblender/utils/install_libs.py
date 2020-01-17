
from rprblender.utils.logging import Log
log = Log(tag="install_libs")


def ensure_boto3() -> None:
    """
    WIP "try to install boto3 library at the addon launch time" for zip archive distribution type
    """
    # TODO: test on MacOS
    # TODO: test on Ubuntu
    # TODO: test if no Python present at all on Windows
    # use this snippet to install boto3 library with all the dependencies if absent at the addon launch time
    # note: still it will be available at the next Blender launch only
    # TODO: check if scene reload works as well (note: even then it couldn't be used at all; just to be sure on how it works)
    try:
        import boto3
        log.info("boto3 is already available")
    except ImportError:
        log.info("Installing boto3 library...")
        import subprocess
        # subprocess.call([bpy.app.binary_path_python, "-m", "ensurepip"])  # seems to be working fine without it
        subprocess.call([bpy.app.binary_path_python, "-m", "pip", "install", "--upgrade", "pip", "--user"])
        subprocess.call([bpy.app.binary_path_python, "-m", "pip", "install", "boto3", "--user"])
        log.info("Library boto3 should be available after Blender restart")
