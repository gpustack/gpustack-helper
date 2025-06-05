import subprocess
import os
import logging
import winreg
import win32service
import shutil
from typing import Dict, Tuple, Callable, Any, List
from PySide6.QtCore import QThread

from gpustack_helper.defaults import nssm_binary_path
from gpustack_helper.services.abstract_service import AbstractService
from gpustack_helper.config import HelperConfig

logger = logging.getLogger(__name__)

service_name = 'gpustack'
default_registry_path = r'SYSTEM\CurrentControlSet\Services\GPUStack'

config_key_mapping: Dict[str, Tuple[Tuple[str, int, Callable],...]] = {
    'ProgramArguments': (
        (r'Parameters\AppParameters', winreg.REG_EXPAND_SZ, lambda x: ' '.join(x[1:]) if isinstance(x, (list, tuple)) and len(x) > 1 else x),
        (r'Parameters\Application', winreg.REG_EXPAND_SZ, lambda x: x[0] if isinstance(x, (list, tuple)) else x),
    ),
    'EnvironmentVariables': (
        (r'Parameters\AppEnvironmentExtra', winreg.REG_MULTI_SZ, lambda x: [f"{k}={v}" for k, v in x.items()] if len(x) > 0 else None),
    ),
    'StandardOutPath': (
        (r'Parameters\AppStdout', winreg.REG_EXPAND_SZ, lambda x: x),
    ),
    'StandardErrorPath': (
        (r'Parameters\AppStderr', winreg.REG_EXPAND_SZ, lambda x: x),
    ),
    'RunAtLoad': (
        ('Start', winreg.REG_DWORD, lambda x: win32service.SERVICE_AUTO_START if x else win32service.SERVICE_DEMAND_START),
    ),
    'AppDirectory': (
        (r'Parameters\AppDirectory', winreg.REG_EXPAND_SZ, lambda x: x),
    ),
}
windows_service_default_params: Tuple[Tuple[str, int, Any],...] = (
    ('DisplayName', winreg.REG_SZ, 'GPUStack'),
    ('ObjectName', winreg.REG_SZ, 'LocalSystem'),
    ('Description', winreg.REG_SZ, 'GPUStack aims to get you started with managing GPU devices, running LLMs and performing inference in a simple yet scalable manner.'),
    ('ImagePath', winreg.REG_SZ ,str(nssm_binary_path)),
    ('Type', winreg.REG_DWORD ,win32service.SERVICE_WIN32_OWN_PROCESS),
    ('DelayedAutostart', winreg.REG_DWORD, 0),
    ('ErrorControl', winreg.REG_DWORD, win32service.SERVICE_ERROR_NORMAL),
    ('FailureActionsOnNonCrashFailures', winreg.REG_DWORD, 1),
    ('Parameters\\AppExit\\', winreg.REG_SZ, 'Restart'),
)

def parse_registry(cfg: HelperConfig) -> List[Tuple[str, int, Any]]:
    service_data: List[Tuple[str, int, Any]] = list(windows_service_default_params)
    data = cfg.model_dump()
    if not hasattr(data, 'ProgramArguments'):
        data['ProgramArguments'] = cfg.program_args_defaults()
    if not hasattr(data, 'AppDirectory'):
        data['AppDirectory'] = cfg.active_data_dir

    for key, value in data.items():
        if key not in config_key_mapping:
            continue
        function_map = config_key_mapping[key]
        if function_map is None:
            continue
        for (sub_key, reg_type, func) in function_map:
            service_data.append((sub_key, reg_type, func(value)))
    
    return service_data

def parse_service(data: List[Tuple[str, int, Any]]) -> Dict[str, Any]:
    """
    Parses the service data from the registry into a dictionary.
    """
    parsed_data = {}
    for key, reg_type, value in data:
        # skip expended setting. there won't be any expended setting for native service
        if reg_type == winreg.REG_MULTI_SZ or reg_type == winreg.REG_EXPAND_SZ:
            continue
        # skip parameters as it is not needed for native service
        elif key.startswith('Parameters\\'):
            continue
        else:
            parsed_data[key] = value
    return parsed_data

def diff_registry(input: List[Tuple[str, int, Any]], path: str = default_registry_path) -> List[Tuple[str, int, Any]]:
    """
    比较输入的键值对与 Windows 注册表中的键值对，返回差异部分
    """
    data: Dict[str, List[Tuple[str, int, Any]]] = dict()
    for (key, reg_type, value) in input:
        # e.g. Parameters\AppExit\ -> ['Parameters', 'AppExit', '']
        # the key will be '' and the full path will be SYSTEM\CurrentControlSet\Services\GPUStack\Parameters\AppExit
        level = key.split('\\')
        key = level[-1]
        inner_path = '\\'.join([path] + level[:-1])

        current_list = data.get(inner_path, [])
        if inner_path not in data:
            data[inner_path] = current_list
        current_list.append((key, reg_type, value))
    data = dict(sorted(data.items()))
    result: List[Tuple[str, int, Any]] = []
    for inner_path, values in data.items():
        # restore the path to the original path
        # e.g. SYSTEM\CurrentControlSet\Services\GPUStack\Parameters AppParameters value 
        # will be Parameters\AppParameters to value
        trimmed_path = inner_path.removeprefix(path).removeprefix("\\")
        if trimmed_path != '':
            trimmed_path += '\\'
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, inner_path, 0, winreg.KEY_QUERY_VALUE) as key:
            for (name, reg_type, v) in values:
                try:
                    existing_value, existing_type = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    existing_value, existing_type = None, reg_type
                except Exception as e:
                    logger.error(f"Error querying registry key {inner_path}, for {name}: {e}")
                    raise e
                if existing_value != v or existing_type != reg_type:
                    result.append((trimmed_path+name, reg_type, v))
    return result

def set_in_registry(input: List[Tuple[str, int, Any]], path: str = default_registry_path) -> None:
    """
    设置 Windows 注册表中的键值对
    """
    data:Dict[str, List[Tuple[str, int, Any]]] = dict()
    for (key, reg_type, value) in input:
        # e.g. Parameters\AppExit\ -> ['Parameters', 'AppExit', '']
        # the key will be '' and the full path will be SYSTEM\CurrentControlSet\Services\GPUStack\Parameters\AppExit
        level = key.split('\\')
        key = level[-1]
        inner_path = '\\'.join([path] + level[:-1])

        current_list = data.get(inner_path, [])
        if inner_path not in data:
            data[inner_path] = current_list
        current_list.append((key, reg_type, value))
    data = dict(sorted(data.items()))
    for path, values in data.items():
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            for (name, reg_type, v) in values:
                try:
                    if v is None:
                        winreg.DeleteValue(key, name)
                    else:
                        winreg.SetValueEx(key, name, 0, reg_type, v)
                except Exception as e:
                    logger.error(f"Error setting registry key {path}, for {name} and {v}: {e}")
                    raise e

def service_exists(service_name: str) -> bool:
    try:
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
        service = win32service.OpenService(scm, service_name, win32service.SERVICE_QUERY_STATUS)
        win32service.CloseServiceHandle(service)
        return True
    except Exception:
        return False
    finally:
        if scm is not None:
            win32service.CloseServiceHandle(scm)

class ThreadWrapper(QThread):
    cfg: HelperConfig
    target: Callable[[HelperConfig], None]
    def __init__(self, cfg: HelperConfig,  func: Callable[[], None]) -> None:
        super().__init__()
        self.cfg = cfg
        self.target = func
    def run(self) -> None:
        if self.cfg.debug:
            try:
                import debugpy
                debugpy.debug_this_thread()
            except ImportError:
                logger.error("debugpy is not installed, skipping debug mode.")
        return self.target(self.cfg)

def _start_windows_service(cfg: HelperConfig) -> None:
    registry_data = parse_registry(cfg)
    try:
        diff_registry_data = diff_registry(registry_data)
        gpustack_config = cfg.user_gpustack_config
        if not os.path.exists(cfg.filepath):
            cfg.update_with_lock()
        if not os.path.exists(gpustack_config.filepath):
            gpustack_config.update_with_lock()

        ## set helper config to registry
        set_in_registry(diff_registry_data)
        ## copy 
        config_sync = gpustack_config.filepath == gpustack_config.active_config_path
        if not config_sync:
            if os.path.exists(gpustack_config.active_config_path):
                with open(gpustack_config.active_config_path, 'rb') as f:
                    active_content = f.read()
                with open(gpustack_config.filepath, 'rb') as f:
                    new_content = f.read()
                config_sync = active_content == new_content
                
        if not config_sync:
            os.makedirs(os.path.dirname(gpustack_config.active_config_path), exist_ok=True)
            shutil.copy(gpustack_config.filepath, gpustack_config.active_config_path)
        
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
        service_handle = None
        if not service_exists(service_name):
            service = parse_service(registry_data)
            service_handle = win32service.CreateService(
                scm,
                service_name,
                service_name,
                win32service.SERVICE_START,
                service.get('Type', win32service.SERVICE_WIN32_OWN_PROCESS),
                service.get('Start', win32service.SERVICE_AUTO_START),
                service.get('ErrorControl', win32service.SERVICE_ERROR_NORMAL),
                service.get('ImagePath', ''),
                None, 0, None, service.get('ObjectName', 'LocalSystem'), None
            )
        else:
            service_handle = win32service.OpenService(scm, service_name, win32service.SERVICE_START)

        # 启动服务
        win32service.StartService(service_handle, None)
        win32service.CloseServiceHandle(service_handle)
    except Exception as e:
        logger.error(f"Exception occurred: {e}")
    finally:
        if scm is not None:
            win32service.CloseServiceHandle(scm)

def _stop_windows_service(cfg: HelperConfig) -> None:
    try:
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
        service_handle = win32service.OpenService(scm, service_name, win32service.SERVICE_STOP)
        win32service.ControlService(service_handle, win32service.SERVICE_CONTROL_STOP)
        win32service.CloseServiceHandle(service_handle)
        win32service.CloseServiceHandle(scm)
        logger.info(f"Service {service_name} stopped.")
    except Exception as e:
        logger.error(f"Failed to stop service: {e}")


def _restart_windows_service(cfg: HelperConfig) -> None:
    try:
        _stop_windows_service(cfg)
        import time
        time.sleep(2)  # 等待服务完全停止
        _start_windows_service(cfg)
        logger.info(f"Service {service_name} restarted.")
    except Exception as e:
        logger.error(f"Failed to restart service: {e}")

class WindowsService(AbstractService):
    @classmethod
    def start(self, cfg: HelperConfig) -> QThread:
        return ThreadWrapper(cfg, _start_windows_service)
    
    @classmethod
    def stop(self, cfg: HelperConfig) -> QThread:
        return ThreadWrapper(cfg, _stop_windows_service)
    
    @classmethod
    def restart(self, cfg: HelperConfig) -> QThread:
        return ThreadWrapper(cfg, _restart_windows_service)

    @classmethod
    def get_current_state(self, cfg: HelperConfig) -> AbstractService.State:
        # 调用 nssm status gpustack 获取服务状态
        try:
            result = subprocess.run([
                str(nssm_binary_path), 'status', service_name
            ], capture_output=True, text=True, check=True)
            output = result.stdout.encode('latin1').decode('utf-16le').strip()
        except subprocess.CalledProcessError as e:
            # 服务不存在或命令失败，返回 Stop
            return AbstractService.State.Stop

        # nssm 输出通常为: 'SERVICE_RUNNING', 'SERVICE_STOPPED', 等
        # 统一映射到 AbstractService.State
        if 'RUNNING' in output:
            result = diff_registry(parse_registry(cfg))
            if len(result) > 0:
                return AbstractService.State.TO_SYNC
            return AbstractService.State.STARTED
        elif 'STOPPED' in output:
            return AbstractService.State.STOPPED
        else:
            # 其他状态统一为 Stop
            return AbstractService.State.STOPPED
    
    @classmethod
    def migrate(self, cfg: HelperConfig) -> None:
        # TODO
        pass
