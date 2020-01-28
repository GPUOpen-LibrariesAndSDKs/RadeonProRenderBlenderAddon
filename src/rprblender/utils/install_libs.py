
from rprblender.utils.logging import Log
log = Log(tag="install_libs")


def run_pip(*args):
    """ Run pip install with current user access level """
    import bpy
    import subprocess

    log(f"Running the subprocess.call 'py -m pip install {args} --user'")

    try:
        res = subprocess.call([bpy.app.binary_path_python, "-m", "pip", "install", *args, "--user"])
        # note: success retcode is 0. No info on where the lib was installed
        return True
    # catch any exception, for debug
    except Exception as e:
        log.warn(f"Subprocess call failed: {e}")

    return False


def ensure_boto3() -> None:
    """
    Try to install boto3 library at the addon launch time
    """
    # use this snippet to install boto3 library with all the dependencies if absent at the addon launch time
    # note: still it will be available at the next Blender launch only
    try:
        import boto3
    except ImportError:
        log.info("Installing boto3 library...")
        if run_pip("--upgrade", "pip") and run_pip("boto3"):
            # at this point library can be loaded by direct path usage, for example:
            # hardcoded_path = "C:\\Users\\<user_name>\\AppData\\Roaming\\Python\\Python37\\site-packages"
            # importlib.sys.path.append(hardcoded_path)
            # now the "import boto3" or "globals()['boto3'] = importlib.import_module('boto3')" can be used to load it
            # the path will also be added by Blender once it reloaded, after that no path modification would be needed.

            # now there is a question - how to adjust the sys.path at the firstmost install correctly for all OSs?
            log.info("Library boto3 should be available right now. At least in install_libs module scope")
        else:
            log.warn("Something went wrong, unable to install boto3 library.")
