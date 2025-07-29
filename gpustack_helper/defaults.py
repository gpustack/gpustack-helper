import sys
import os
from os.path import join, abspath, dirname
from typing import List, Literal, Dict, Callable, Tuple
import subprocess
from platformdirs import (
    user_data_dir,
    site_data_dir,
)

app_name = "GPUStack"
service_app_name = "GPUStackService"
helper_name = app_name + "Helper"
gpustack_config_name = "config.yaml"
helper_config_file_name = "ai.gpustack.plist"
runtime_plist_path = (
    f"/Library/LaunchDaemons/{helper_config_file_name}"
    if sys.platform == "darwin"
    else None
)

frozen_base = (
    join(dirname(sys.executable), '../Resources')
    if sys.platform == "darwin"
    else join(dirname(sys.executable), '_internal')
)

resource_path = abspath(
    frozen_base
    if getattr(sys, "frozen", False)
    else join(dirname(abspath(__file__)), "..")
)
icon_path = join(resource_path, "tray_icon.png")
translation_path = join(resource_path, "translations")

data_dir = user_data_dir(helper_name, appauthor=False, roaming=True)
global_data_dir = site_data_dir(app_name, appauthor=False)

log_file_path = (
    "/var/log/gpustack.log"
    if sys.platform == "darwin"
    else join(global_data_dir, "log", "gpustack.log")
)

gpustack_binary_name = "gpustack" if sys.platform == "darwin" else "gpustack.exe"


def is_running_in_app() -> bool:
    if '.app/Contents/MacOS' in sys.executable:
        return True
    return False


def locate_gpustack() -> str:
    if sys.platform == "windows" or not getattr(sys, "frozen", False):
        return join(dirname(sys.executable), gpustack_binary_name)
    # in other case, it is built by pyinstaller and runs on MacOS.
    if is_running_in_app():
        svc_app_path = None
        for svc_app in [
            join(frozen_base, f"{service_app_name}.app"),
            join(dirname(sys.executable), f"../../{service_app_name}.app"),
        ]:
            if os.path.exists(svc_app):
                svc_app_path = svc_app
                break
        if svc_app_path is not None:
            # if it has GPUStackService.app sub app, we need to point to the binary
            # in GPUStackService.app/Contents/MacOS/gpustack
            # otherwise, it is built by pyinstaller but runs in app.
            return abspath(
                join(
                    svc_app_path,
                    f'Contents/MacOS/{gpustack_binary_name}',
                )
            )

    # otherwise, it is built by pyinstaller but runs in app.
    return abspath(join(dirname(sys.executable), '../gpustack', gpustack_binary_name))


gpustack_binary_path = locate_gpustack()

nssm_binary_path = (
    join(resource_path, "nssm.exe")
    if os.getenv("NSS_BINARY_PATH", None) is None
    else os.getenv("NSS_BINARY_PATH")
)


def open_and_select_file(file_path: str, selected: bool = True) -> None:
    if sys.platform != "darwin" and sys.platform != "win32":
        raise NotImplementedError("Unsupported platform for opening file explorer")
    file_explorer = "open" if sys.platform == "darwin" else "explorer"
    path_func: Dict[
        Literal["darwin", "win32"], Dict[bool, Callable[[str], List[str]]]
    ] = {
        "darwin": {
            True: lambda path: [file_explorer, "-R", path],
            False: lambda path: [file_explorer, dirname(path)],
        },
        "win32": {
            True: lambda path: [file_explorer, f"/select,{path}"],
            False: lambda path: [file_explorer, dirname(path)],
        },
    }
    args = path_func[sys.platform][selected](file_path)
    subprocess.Popen(args)


def open_with_app(file_path: str) -> None:
    if sys.platform != "darwin" and sys.platform != "win32":
        raise NotImplementedError("Unsupported platform for opening file with app")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    app_command = (
        ["open", "-a", "Console"] if sys.platform == "darwin" else ["notepad.exe"]
    )
    app_command.append(file_path)
    subprocess.Popen(app_command)


def _default_dac_parameters() -> Tuple[str, str, str]:
    """
    refer to dac default parameters
    """
    __MODEL_LATEST_TAGS__ = {
        ("44khz", "8kbps"): "0.0.1",
        ("24khz", "8kbps"): "0.0.4",
        ("16khz", "8kbps"): "0.0.5",
        ("44khz", "16kbps"): "1.0.0",
    }
    default_model_type = '44khz'
    default_model_bitrate = '8kbps'
    tag = 'latest'
    tag = __MODEL_LATEST_TAGS__.get(
        (default_model_type, default_model_bitrate), tag
    )  # default to 44khz, 8kbps if not found
    return (
        default_model_type,
        tag,
        default_model_bitrate,
    )


def dac_download_link() -> str:
    """
    copy hardcode url from dac to avoid unnecessary import
    """

    __MODEL_URLS__ = {
        (
            "44khz",
            "0.0.1",
            "8kbps",
        ): "https://github.com/descriptinc/descript-audio-codec/releases/download/0.0.1/weights.pth",
        (
            "24khz",
            "0.0.4",
            "8kbps",
        ): "https://github.com/descriptinc/descript-audio-codec/releases/download/0.0.4/weights_24khz.pth",
        (
            "16khz",
            "0.0.5",
            "8kbps",
        ): "https://github.com/descriptinc/descript-audio-codec/releases/download/0.0.5/weights_16khz.pth",
        (
            "44khz",
            "1.0.0",
            "16kbps",
        ): "https://github.com/descriptinc/descript-audio-codec/releases/download/1.0.0/weights_44khz_16kbps.pth",
    }
    return __MODEL_URLS__.get(_default_dac_parameters(), None)


def get_dac_filename() -> str:
    model_type_default, tag, model_bitrate_default = _default_dac_parameters()
    return f"weights_{model_type_default}_{model_bitrate_default}_{tag}.pth"


def get_legacy_data_dir():
    app_name = "gpustack"
    if os.name == "nt":  # Windows
        data_dir = os.path.join(os.environ["APPDATA"], app_name)
    elif os.name == "posix":
        data_dir = f"/var/lib/{app_name}"
    else:
        raise Exception("Unsupported OS")

    return os.path.abspath(data_dir)


if __name__ == "__main__":
    print(f"Icon Path: {icon_path}")
    print(f"Data Directory: {data_dir}")
    print(f"Global Data Directory: {global_data_dir}")
    print(f"Log File Path: {log_file_path}")
    print(f"GPUStack Binary Path: {gpustack_binary_path}")
    print(f"executable: {sys.executable}")
