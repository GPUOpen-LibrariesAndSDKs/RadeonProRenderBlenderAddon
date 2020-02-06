import bpy

import platform

from rprblender.utils.logging import Log
log = Log(tag="install_libs")


PYTHON_PATH = bpy.app.binary_path_python


def run_python_call(*args) -> bool:
    """
    Run Blender Python with arguments on user access level
    """
    import subprocess

    log(f"Running the subprocess.call '{args} --user'")

    try:
        subprocess.check_call([PYTHON_PATH, '-m', *args, '--user'])
        return True
    except subprocess.CalledProcessError as e:
        log.warn(f"\nSubprocess call '{args}' failed:\n\t{e}")

    return False


def run_pip(*args):
    """
    Run 'pip install' with current user access level
    """
    return run_python_call('pip', 'install', *args)


def ensure_boto3() -> None:
    """
    Try to install boto3 library at the addon launch time
    """
    # use this snippet to install boto3 library with all the dependencies if absent at the addon launch time
    # note: still it will be available at the next Blender launch only
    try:
        import boto3
    except (ImportError, ModuleNotFoundError):
        log.info("Installing boto3 library...")
        running_os = platform.system()
        if running_os == 'Linux':  # Blender for linux has ensurepip module but no pip
            if run_python_call('ensurepip', '--upgrade') and run_pip("--upgrade", "pip") and run_pip('boto3'):
                log.info("Library boto3 installed and ready to use.")
                return
        elif running_os == 'Windows':  # Blender for Windows has pip and no ensurepip module
            if run_pip("--upgrade", "pip") and run_pip("boto3"):
                # Note: at this point library can be loaded by direct path usage, for example:
                # hardcoded_path = "C:\\Users\\<user_name>\\AppData\\Roaming\\Python\\Python37\\site-packages"
                # importlib.sys.path.append(hardcoded_path)
                # globals()['boto3'] = importlib.import_module('boto3')

                # after Blender restart no path modification would be needed. Report and let it be.
                log.info("Library boto3 should be available after Blender restart.")
                return
        else:
            if run_pip("--upgrade", "pip") and run_pip("boto3"):
                # Mac is fine.
                log.info("Library boto3 installed and ready to use.")
                return

        log.warn("Something went wrong, unable to install boto3 library.")
