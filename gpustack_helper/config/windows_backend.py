from typing import Dict, Tuple, Callable, Any, List, Optional
from pydantic import BaseModel
import winreg
import logging
import win32service
from gpustack_helper.defaults import nssm_binary_path
from gpustack_helper.config.backends import ModelBackend
from gpustack_helper.databinder import set_nested_data
from gpustack_helper.config.config import (
    HelperConfig,
)

service_name = "GPUStack"
logger = logging.getLogger(__name__)
registry_path = r"SYSTEM\CurrentControlSet\Services\GPUStack"

config_key_mapping: Dict[str, Tuple[Tuple[str, int, Callable], ...]] = {
    "ProgramArguments": (
        (
            r"Parameters\AppParameters",
            winreg.REG_EXPAND_SZ,
            lambda x: (
                " ".join(x[1:]) if isinstance(x, (list, tuple)) and len(x) > 1 else x
            ),
        ),
        (
            r"Parameters\Application",
            winreg.REG_EXPAND_SZ,
            lambda x: x[0] if isinstance(x, (list, tuple)) else x,
        ),
    ),
    "EnvironmentVariables": (
        (
            r"Parameters\AppEnvironmentExtra",
            winreg.REG_MULTI_SZ,
            lambda x: [f"{k}={v}" for k, v in x.items()] if len(x) > 0 else None,
        ),
    ),
    "StandardOutPath": ((r"Parameters\AppStdout", winreg.REG_EXPAND_SZ, lambda x: x),),
    "StandardErrorPath": (
        (r"Parameters\AppStderr", winreg.REG_EXPAND_SZ, lambda x: x),
    ),
    "RunAtLoad": (
        (
            "Start",
            winreg.REG_DWORD,
            lambda x: (
                win32service.SERVICE_AUTO_START
                if x
                else win32service.SERVICE_DEMAND_START
            ),
        ),
    ),
    "AppDirectory": ((r"Parameters\AppDirectory", winreg.REG_EXPAND_SZ, lambda x: x),),
    "NSSMPath": (
        (
            "ImagePath",
            winreg.REG_SZ,
            lambda x: x,
        ),
    ),
}
windows_service_default_params: Tuple[Tuple[str, int, Any], ...] = (
    ("DisplayName", winreg.REG_SZ, "GPUStack"),
    ("ObjectName", winreg.REG_SZ, "LocalSystem"),
    (
        "Description",
        winreg.REG_SZ,
        "GPUStack aims to get you started with managing GPU devices, running LLMs and performing inference in a simple yet scalable manner.",
    ),
    ("Type", winreg.REG_DWORD, win32service.SERVICE_WIN32_OWN_PROCESS),
    ("DelayedAutostart", winreg.REG_DWORD, 0),
    ("ErrorControl", winreg.REG_DWORD, win32service.SERVICE_ERROR_NORMAL),
    ("FailureActionsOnNonCrashFailures", winreg.REG_DWORD, 1),
    ("Parameters\\AppExit\\", winreg.REG_SZ, "Restart"),
)


def parse_registry(
    data: Dict[str, Any], exclude_defaults: bool = False
) -> List[Tuple[str, int, Any]]:
    service_data: List[Tuple[str, int, Any]] = list(
        windows_service_default_params if not exclude_defaults else ()
    )
    for key, value in data.items():
        if key not in config_key_mapping:
            continue
        function_map = config_key_mapping[key]
        if function_map is None:
            continue
        for sub_key, reg_type, func in function_map:
            service_data.append((sub_key, reg_type, func(value)))

    return service_data


class RegistryModel(ModelBackend):
    _registry_path: str
    helper_config: HelperConfig = None

    def __init__(
        self,
        model: BaseModel,
        registry_path: str = registry_path,
    ):
        if not isinstance(model, HelperConfig):
            raise TypeError("Model must be an instance of HelperConfig")
        super().__init__(model)
        self._registry_path = registry_path
        self.helper_config = model

    def _parse_data(
        self, registry_data: Dict[str, Any], config_data: Dict[str, Any]
    ) -> None:
        binary_name: str = registry_data.get('Application')
        parameters: str = registry_data.get('AppParameters', 'start')
        config_data["ProgramArguments"] = [binary_name] + parameters.split()
        env_list = registry_data.get("AppEnvironmentExtra", [])
        if isinstance(env_list, list):
            env_dict = {}
            for item in env_list:
                if "=" in item:
                    k, v = item.split("=", 1)
                    env_dict[k] = v
            config_data["EnvironmentVariables"] = env_dict
        else:
            config_data["EnvironmentVariables"] = {}
        stdout = registry_data.get("AppStdout", None)
        if stdout is not None and stdout != "":
            config_data["StandardOutPath"] = registry_data.get("AppStdout")
        stderr = registry_data.get("AppStderr", None)
        if stderr is not None and stderr != "":
            config_data["StandardErrorPath"] = registry_data.get("AppStderr")

    def update_with_lock(self, **kwargs):
        with self._lock:
            config_data = {}
            data_dir = kwargs.pop('data_dir', None)
            if data_dir:
                config_data['AppDirectory'] = data_dir
            nssm_path = kwargs.pop('nssm_path', None)
            if nssm_path:
                config_data['NSSMPath'] = nssm_path
            if not ensure_service():
                self.reload()
            else:
                # in create service case, the AppDirectory is not set
                config_data['AppDirectory'] = self.helper_config.data_dir
                config_data['NSSMPath'] = str(nssm_binary_path)
            if len(config_data) != 0:
                set_in_registry(config_data)
            set_nested_data(self.helper_config, kwargs)
            self.save()

    def reload(self):
        exists, _ = service_exists()
        if not exists:
            return
        registry_data: Dict[str, Any] = {}
        config_data: Dict[str, Any] = {}
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                self._registry_path + r"\Parameters",
                0,
                winreg.KEY_READ,
            ) as key:
                i = 0
                while True:
                    try:
                        attr, value, _ = winreg.EnumValue(key, i)
                        registry_data[attr] = value
                        i += 1
                    except OSError:
                        break
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, self._registry_path, 0, winreg.KEY_READ
            ) as key:
                start_type, _ = winreg.QueryValueEx(key, "Start")
                config_data['RunAtLoad'] = start_type == win32service.SERVICE_AUTO_START
        except Exception as e:
            raise RuntimeError(f"Failed to reload registry model: {e}")

        self._parse_data(registry_data, config_data)

        set_nested_data(self.helper_config, config_data)

    def save(self):
        set_in_registry(self.helper_config.model_dump())


def legacy_helper_config() -> Optional[HelperConfig]:
    exists, _ = service_exists()
    if not exists:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, registry_path, 0, winreg.KEY_READ
        ) as key:
            value, _ = winreg.QueryValueEx(key, "ImagePath")
            if value == str(nssm_binary_path):
                return None
        return HelperConfig(
            backend=lambda x: RegistryModel(x),
        )
    except Exception as e:
        logger.warning(f"Failed to read legacy helper config from registry: {e}")
        return None


def service_exists() -> Tuple[bool, bool]:
    """
    return service exist and running status
    """
    try:
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
        service = win32service.OpenService(
            scm, service_name, win32service.SERVICE_QUERY_STATUS
        )
        status = win32service.QueryServiceStatus(service)[1]
        win32service.CloseServiceHandle(service)
        return True, status == win32service.SERVICE_RUNNING
    except Exception:
        return False, False
    finally:
        if scm is not None:
            win32service.CloseServiceHandle(scm)


def ensure_service() -> bool:
    exists, _ = service_exists()
    if exists:
        return False
    try:
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
        service_handle = win32service.CreateService(
            scm,
            service_name,
            service_name,
            win32service.SERVICE_START,
            win32service.SERVICE_WIN32_OWN_PROCESS,
            win32service.SERVICE_AUTO_START,
            win32service.SERVICE_ERROR_NORMAL,
            nssm_binary_path,
            None,
            0,
            None,
            "LocalSystem",
            None,
        )
    except Exception as e:
        logger.error(f"Failed to create service: {e}")
        raise RuntimeError(f"Failed to create service: {e}")
    finally:
        if 'service_handle' in locals() and service_handle is not None:
            win32service.CloseServiceHandle(service_handle)
        if 'scm' in locals() and scm is not None:
            win32service.CloseServiceHandle(scm)
    return True


def set_in_registry(config: Dict[str, Any], exclude_defaults: bool = False) -> None:
    register_data = parse_registry(config, exclude_defaults)
    data: Dict[str, List[Tuple[str, int, Any]]] = dict()
    for key, reg_type, value in register_data:
        # e.g. Parameters\AppExit\ -> ['Parameters', 'AppExit', '']
        # the key will be '' and the full path will be SYSTEM\CurrentControlSet\Services\GPUStack\Parameters\AppExit
        level = key.split("\\")
        key = level[-1]
        inner_path = "\\".join([registry_path] + level[:-1])

        current_list = data.get(inner_path, [])
        if inner_path not in data:
            data[inner_path] = current_list
        current_list.append((key, reg_type, value))
    data = dict(sorted(data.items()))
    for path, values in data.items():
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            for name, reg_type, v in values:
                try:
                    if v is None:
                        winreg.DeleteValue(key, name)
                    else:
                        winreg.SetValueEx(key, name, 0, reg_type, v)
                except FileNotFoundError:
                    logger.warning(
                        f"Registry value '{name}' not found in key '{path}', skipping delete."
                    )
                    continue
                except Exception as e:
                    logger.error(
                        f"Error setting registry key {path}, for {name} and {v}: {e}"
                    )
                    raise e
