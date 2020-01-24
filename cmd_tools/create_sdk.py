from pathlib import Path
import subprocess
import platform
import shutil


OS = platform.system()
sdk_dir = Path(".sdk")


def install_name_tool(*args):
    args_str = tuple(str(a) for a in args)
    subprocess.check_call(['install_name_tool', *args_str])


def recreate_sdk():
    if sdk_dir.is_dir():
        shutil.rmtree(str(sdk_dir))

    sdk_dir.mkdir()

    copy_rpr_sdk()
    copy_rif_sdk()


def copy_rpr_sdk():
    rpr_dir = Path("RadeonProRenderSDK/RadeonProRender")

    # creating rpr dir
    sdk_rpr_dir = sdk_dir / "rpr"
    sdk_rpr_dir.mkdir()

    # copying inc files
    shutil.copytree(str(rpr_dir / "inc"), str(sdk_rpr_dir / "inc"))

    # copying rprTools files
    shutil.copytree(str(rpr_dir / "rprTools"), str(sdk_rpr_dir / "rprTools"))

    if OS == 'Darwin':
        # fixing stddef.h include for OSX
        rpr_h = sdk_rpr_dir / "inc/RadeonProRender.h"
        rpr_h_text = rpr_h.read_text()
        rpr_h_text = rpr_h_text.replace("<cstddef>", "<stddef.h>")
        rpr_h.write_text(rpr_h_text)

    # copying bin lib files
    bin_glob = {
        'Windows': "binWin64/*.dll",
        'Linux': "binUbuntu18/*.so",
        'Darwin': "binMacOS/*.dylib"
    }[OS]

    sdk_bin_dir = sdk_rpr_dir / "bin"
    sdk_bin_dir.mkdir()

    for lib in rpr_dir.glob(bin_glob):
        shutil.copy(str(lib), str(sdk_bin_dir))

    if OS == 'Windows':
        # copying .lib files
        sdk_lib_dir = sdk_rpr_dir / "lib"
        sdk_lib_dir.mkdir()

        for lib in rpr_dir.glob("libWin64/*.lib"):
            shutil.copy(str(lib), str(sdk_lib_dir))


def copy_rif_sdk():
    rif_dir = Path("RadeonProImageProcessingSDK")

    # creating rpr dir
    sdk_rif_dir = sdk_dir / "rif"
    sdk_rif_dir.mkdir()

    # copying models
    shutil.copytree(str(rif_dir / "models"), str(sdk_rif_dir / "models"))

    # getting rif_os_dir
    os_str = {
        'Windows': "Windows",
        'Linux': "Ubuntu18",
        'Darwin': "OSX"
    }[OS]
    rif_os_dir = next(rif_dir.glob(f"radeonimagefilters-*-{os_str}-rel"))

    # copying inc files
    shutil.copytree(str(rif_os_dir / "include"), str(sdk_rif_dir / "inc"))

    # copying bin lib files
    sdk_bin_dir = sdk_rif_dir / "bin"
    sdk_bin_dir.mkdir()
    bin_dir = rif_os_dir / "bin"

    if OS == 'Windows':
        for lib in bin_dir.glob("*.dll"):
            shutil.copy(str(lib), str(sdk_bin_dir))

        # copying .lib files
        sdk_lib_dir = sdk_rif_dir / "lib"
        sdk_lib_dir.mkdir()

        for lib in bin_dir.glob("*.lib"):
            shutil.copy(str(lib), str(sdk_lib_dir))

    elif OS == 'Linux':
        shutil.copy(str(bin_dir / "libRadeonImageFilters64.so.1.4.3"),
                    str(sdk_bin_dir / "libRadeonImageFilters64.so"))
        shutil.copy(str(bin_dir / "libRadeonML-MIOpen.so.1.5.2"),
                    str(sdk_bin_dir / "libRadeonML-MIOpen.so"))
        shutil.copy(str(bin_dir / "libOpenImageDenoise.so.0.9.0"),
                    str(sdk_bin_dir / "libOpenImageDenoise.so"))
        shutil.copy(str(bin_dir / "libMIOpen.so.2.0.1"),
                    str(sdk_bin_dir / "libMIOpen.so.2"))

    elif OS == 'Darwin':
        shutil.copy(str(bin_dir / "libRadeonImageFilters64.1.4.3.dylib"),
                    str(sdk_bin_dir / "libRadeonImageFilters64.dylib"))
        shutil.copy(str(bin_dir / "libOpenImageDenoise.0.9.0.dylib"),
                    str(sdk_bin_dir / "libOpenImageDenoise.dylib"))

        # adjusting id of RIF libs
        install_name_tool('-id', "@rpath/libRadeonImageFilters64.dylib", sdk_bin_dir / "libRadeonImageFilters64.dylib")
        install_name_tool('-id', "@rpath/libOpenImageDenoise.dylib", sdk_bin_dir / "libOpenImageDenoise.dylib")

    else:
        raise KeyError("Unsupported OS", OS)


if __name__ == "__main__":
    recreate_sdk()
