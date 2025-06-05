import sys
import os
import pathlib
from os.path import join, abspath, dirname
from typing import List, Literal, Dict, Callable
import subprocess
from platformdirs import (
    user_data_dir,
    site_data_dir,
)

app_name = "GPUStack"
gpustack_config_name = "config.yaml"

base_path = abspath(join(dirname(sys.executable),"../Resources") if getattr(sys, 'frozen', False) else join(dirname(abspath(__file__)),".."))
icon_path = join(base_path, 'tray_icon.png')

data_dir = user_data_dir(app_name, appauthor=False, roaming=True)
global_data_dir = site_data_dir(app_name, appauthor=False)
config_path = join(data_dir, gpustack_config_name)

legacy_data_dir = "/var/lib/gpustack" if sys.platform == 'darwin' else join(data_dir, 'log', 'gpustack.log')
log_file_path = "/var/log/gpustack.log" if sys.platform == 'darwin' else join(global_data_dir, 'log', "gpustack.log")

gpustack_binary_name = "gpustack" if sys.platform == 'darwin' else "gpustack.exe"
gpustack_binary_path = join(dirname(sys.executable), gpustack_binary_name)

nssm_binary_path = join(dirname(sys.executable), "nssm.exe") if os.getenv('NSS_BINARY_PATH', None) is None else os.getenv('NSS_BINARY_PATH')

def open_and_select_file(file_path: str, selected: bool = True) -> None:
    if sys.platform != 'darwin' and sys.platform != 'win32':
        raise NotImplementedError("Unsupported platform for opening file explorer")
    file_explorer = "open" if sys.platform == 'darwin' else "explorer"
    path_func: Dict[Literal['darwin', 'win32'], Dict[bool, Callable[[str], List[str]]]] = {
        'darwin': {
            True: lambda path: [file_explorer, "-R", path],
            False: lambda path: [file_explorer, dirname(path)]
        },
        'win32': {
            True: lambda path: [file_explorer, f'/select,{path}'],
            False: lambda path: [file_explorer, dirname(path)]
        }
    } 
    args = path_func[sys.platform][selected](file_path)
    subprocess.Popen(args)

def open_with_app(file_path: str) -> None:
    if sys.platform != 'darwin' and sys.platform != 'win32':
        raise NotImplementedError("Unsupported platform for opening file with app")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    app_command = ['open', '-a', 'Console'] if sys.platform == 'darwin' else ["notepad.exe"]
    app_command.append(file_path)
    subprocess.Popen(app_command)

def get_lagecy_env_file() -> str:
    if sys.platform == 'darwin':
        return "/etc/default/gpustack"
    elif sys.platform == 'win32':
        return join(os.environ["APPDATA"], app_name, f"{app_name.lower()}.env")
    else:
        raise NotImplementedError("Unsupported platform")

if __name__ == "__main__":
    print(f"Icon Path: {icon_path}")
    print(f"Data Directory: {data_dir}")
    print(f"Global Data Directory: {global_data_dir}")
    print(f"Config Path: {config_path}")
    print(f"Lagecy Data Directory: {legacy_data_dir}")
    print(f"Log File Path: {log_file_path}")
    print(f"GPUStack Binary Path: {gpustack_binary_path}")
    print(f"Lagecy Env File: {get_lagecy_env_file()}")
    print(f'executable: {sys.executable}')
