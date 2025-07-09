import logging
import win32service
import shutil
import glob
import os
from typing import Callable
from PySide6.QtCore import QThread

from gpustack_helper.defaults import nssm_binary_path
from gpustack_helper.services.abstract_service import AbstractService
from gpustack_helper.config import (
    active_helper_config,
    legacy_helper_config,
    user_gpustack_config,
    active_gpustack_config,
    legacy_gpustack_config,
    all_config_sync,
)
from gpustack_helper.config.windows_backend import (
    service_name,
    service_exists,
)

logger = logging.getLogger(__name__)


class ThreadWrapper(QThread):
    target: Callable[[], None]

    def __init__(self, func: Callable[[], None]) -> None:
        super().__init__()
        self.target = func

    def run(self) -> None:
        if active_helper_config()._debug:
            try:
                import debugpy

                debugpy.debug_this_thread()
            except ImportError:
                logger.error("debugpy is not installed, skipping debug mode.")
        return self.target()


def _relocate_legacy_files() -> None:
    gpustack_active = active_gpustack_config()
    gpustack_legacy = legacy_gpustack_config()
    if gpustack_legacy:
        # migrate legacy data files
        if gpustack_legacy.data_dir != gpustack_active.static_data_dir:
            logger.info(
                f"Migrating legacy data files from {gpustack_legacy.data_dir} to {gpustack_active.static_data_dir}"
            )
            try:
                for file in glob.glob(gpustack_legacy.data_dir + "/*"):
                    if file.endswith(".ps1"):
                        continue
                    target_file = os.path.join(
                        gpustack_active.static_data_dir, os.path.basename(file)
                    )
                    if os.path.exists(target_file):
                        logger.warning(
                            f"File {target_file} already exists, removing it before migration."
                        )
                        if os.path.isfile(target_file):
                            os.remove(target_file)
                        elif os.path.isdir(target_file):
                            shutil.rmtree(target_file)
                    shutil.move(file, gpustack_active.static_data_dir)
            except Exception as e:
                logger.error(f"Failed to migrate data files: {e}")


def _sync_configs() -> None:
    # apply config as we run as root in windows
    gpustack_user = user_gpustack_config()
    gpustack_user.reload()
    gpustack_active = active_gpustack_config()
    os.makedirs(os.path.dirname(gpustack_active.config_path), exist_ok=True)
    shutil.copy(gpustack_user.config_path, gpustack_active.config_path)
    gpustack_active.reload()
    _relocate_legacy_files()
    helper_legacy = legacy_helper_config()
    config_data = active_helper_config().model_dump()
    helper_active = active_helper_config()
    if helper_legacy:
        config_data["ProgramArguments"] = helper_active.default_program_arguments
        config_data["data_dir"] = active_helper_config().data_dir
        config_data["nssm_path"] = str(nssm_binary_path)
    elif helper_active.ProgramArguments != helper_active.default_program_arguments:
        config_data["ProgramArguments"] = helper_active.default_program_arguments
    helper_active.update_with_lock(**config_data)


def _ensure_log_dir() -> None:
    helper_active = active_helper_config()
    for path in [
        helper_active.StandardOutPath,
        helper_active.StandardErrorPath,
    ]:
        if not os.path.exists(os.path.dirname(path)):
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create log directory {path}: {e}")
                raise


def _wait_for_service_status_with_timeout(
    service_handle, expected_status, timeout=10
) -> None:
    import time

    start_time = time.time()
    while True:
        status = win32service.QueryServiceStatus(service_handle)[1]
        if status == expected_status:
            break
        if time.time() - start_time > timeout:
            logger.warning(f"Timeout waiting for service {service_name} to stop.")
            raise TimeoutError(f"Timeout waiting for service {service_name} to stop.")
        time.sleep(0.5)
    logger.info(
        f"Service {service_name} is now in the expected status: {expected_status}."
    )


def _start_windows_service() -> None:
    _sync_configs()
    _ensure_log_dir()
    try:
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
        service_handle = win32service.OpenService(
            scm,
            service_name,
            win32service.SERVICE_START | win32service.SERVICE_QUERY_STATUS,
        )

        # Start service
        win32service.StartService(service_handle, None)
        _wait_for_service_status_with_timeout(
            service_handle, win32service.SERVICE_RUNNING, timeout=10
        )
        win32service.CloseServiceHandle(service_handle)
    except Exception as e:
        logger.error(f"Exception occurred: {e}")
    finally:
        if scm is not None:
            win32service.CloseServiceHandle(scm)


def _stop_windows_service(timeout=10) -> None:
    scm = None
    service_handle = None
    try:
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
        service_handle = win32service.OpenService(
            scm,
            service_name,
            win32service.SERVICE_STOP | win32service.SERVICE_QUERY_STATUS,
        )
        status = win32service.QueryServiceStatus(service_handle)[1]
        if status == win32service.SERVICE_STOPPED:
            logger.info(f"Service {service_name} is already stopped.")
            win32service.CloseServiceHandle(service_handle)
            return
        logger.info(f"Stopping service {service_name}...")
        win32service.ControlService(service_handle, win32service.SERVICE_CONTROL_STOP)
        _wait_for_service_status_with_timeout(
            service_handle, win32service.SERVICE_STOPPED, timeout=timeout
        )
    except Exception as e:
        logger.error(f"Failed to stop service: {e}")
    finally:
        if service_handle is not None:
            win32service.CloseServiceHandle(service_handle)
        if scm is not None:
            win32service.CloseServiceHandle(scm)


def _restart_windows_service() -> None:
    try:
        _stop_windows_service()
        _start_windows_service()
        logger.info(f"Service {service_name} restarted.")
    except Exception as e:
        logger.error(f"Failed to restart service: {e}")


class WindowsService(AbstractService):
    @classmethod
    def start(self) -> QThread:
        return ThreadWrapper(_restart_windows_service)

    @classmethod
    def stop(self) -> QThread:
        return ThreadWrapper(_stop_windows_service)

    @classmethod
    def restart(self) -> QThread:
        return ThreadWrapper(_restart_windows_service)

    @classmethod
    def get_current_state(self) -> AbstractService.State:
        cfg = legacy_helper_config()
        if cfg is not None:
            return AbstractService.State.TO_MIGRATE | AbstractService.State.STOPPED
        # 调用 nssm status gpustack 获取服务状态
        exists, is_running = service_exists()
        if not exists or not is_running:
            return AbstractService.State.STOPPED

        is_sync = not is_running or all_config_sync()
        state = (
            AbstractService.State.STARTED
            if is_running
            else AbstractService.State.STOPPED
        )
        if not is_sync:
            state |= AbstractService.State.TO_SYNC

        return state
