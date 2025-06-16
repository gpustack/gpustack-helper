import subprocess
import logging
import re
import os
from os.path import exists, abspath, dirname, islink
from typing import Dict, Any, List, Tuple
from PySide6.QtCore import QProcess
from gpustack_helper.config import HelperConfig
from gpustack_helper.services.abstract_service import AbstractService

logger = logging.getLogger(__name__)

service_id = "system/ai.gpustack"
plist_path = "/Library/LaunchDaemons/ai.gpustack.plist"


def parse_service_status() -> Dict[str, Any]:
    data = {}
    current_section = None
    try:
        result = subprocess.run(
            ["launchctl", "print", service_id],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 113:
            return data
        elif result.returncode != 0:
            logger.error(f"命令执行失败: {result.stderr}")
            return data
        output = result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"命令执行失败: {e.stderr}")
        return data

    for line in output.splitlines():
        if line.strip().endswith("= {"):
            current_section = line.strip().split("=")[0].strip().strip('"')
            data[current_section] = {}
        elif "=" in line and current_section:
            key, value = re.split(r"\s*=\s*", line.strip(), 1)
            data[current_section][key] = value
        elif line.strip() == "}":
            current_section = None
    return data


def get_start_script(cfg: HelperConfig, restart: bool = False) -> str:
    gpustack_config = cfg.user_gpustack_config
    target_path = abspath(cfg.active_config_path)
    # update to ensure the config is up-to-date
    cfg.update_with_lock()
    gpustack_config.update_with_lock()

    files_copy: List[Tuple[str, str]] = [(abspath(cfg.filepath), target_path)]
    if gpustack_config.filepath != gpustack_config.active_config_path:
        files_copy.append(
            (
                abspath(gpustack_config.filepath),
                abspath(gpustack_config.active_config_path),
            ),
        )

    # 过滤掉不存在的源文件
    def files_different(pair: Tuple[str, str]) -> bool:
        src, dst = pair
        if not exists(src):
            return False
        if not exists(dst):
            return True
        with open(src, "rb") as fsrc, open(dst, "rb") as fdst:
            return fsrc.read() != fdst.read()

    files_copy = list(filter(files_different, files_copy))
    copy_script = ";".join(
        f"cp -f '{src}' '{dst}'; chmod 0644 '{dst}'; chown root:whel '{dst}'"
        for src, dst in files_copy
    )
    copy_script = (
        f"mkdir -p '{dirname(target_path)}'; {copy_script}"
        if len(files_copy) != 0
        else None
    )
    link_script = (
        f"rm -f '{plist_path}'; ln -sf '{target_path}' '{plist_path}'"
        if not exists(plist_path)
        or not islink(plist_path)
        or os.readlink(plist_path) != target_path
        or copy_script is not None
        else None
    )
    stop_command = f"launchctl bootout {service_id}" if restart else None
    wait_for_stopped = (
        f"while true; do launchctl print {service_id} >/dev/null 2>&1; [ $? -eq 113 ] && break; sleep 0.5; done"
        if restart
        else None
    )
    register_command = f"launchctl bootstrap system {plist_path}"
    start_command = f"launchctl kickstart {service_id}"
    joined_script = ";".join(
        filter(
            None,
            [
                copy_script,
                link_script,
                stop_command,
                wait_for_stopped,
                register_command,
                start_command,
            ],
        )
    )
    logger.debug(f"准备以admin权限运行该shell脚本 :\n{joined_script}")
    return f"""do shell script "{joined_script}" with prompt "GPUStack 需要启动后台服务" with administrator privileges"""


def launch_service(cfg: HelperConfig, restart: bool = False) -> QProcess:
    """
    prompt sudo privileges to run following command
    1. remove /Library/LaunchDaemons/ai.gpustack.plist if not a symlink or not targetting the right path
    2. create a symlink to /Library/LaunchDaemons/ai.gpustack.plist pointing to cfg.filepath
    3. launch service with launchctl bootstrap system /Library/LaunchDaemons/ai.gpustack.plist
    the commands will be put into an AppleScript to run with administrator privileges
    """
    applescript = get_start_script(cfg, restart=restart)
    qprocess_launch = QProcess()
    qprocess_launch.setProgram("osascript")
    qprocess_launch.setArguments(["-e", applescript])
    qprocess_launch.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
    logger.debug(f"Prepare to launch service {service_id}")
    return qprocess_launch


class DarwinService(AbstractService):
    @classmethod
    def start(self, cfg: HelperConfig) -> QProcess:
        return launch_service(cfg, restart=False)

    @classmethod
    def stop(self, cfg: HelperConfig) -> QProcess:
        # prompt sudo privileges to run following command
        # 1. run launchctl bootout system /Library/LaunchDaemons/ai.gpustack.plist
        script = f"""
    do shell script "\
    launchctl bootout {service_id}\
    " with prompt "GPUStack 需要停止后台服务" with administrator privileges
    """
        qprocess_stop = QProcess()
        qprocess_stop.setProgram("osascript")
        qprocess_stop.setArguments(["-e", script])
        qprocess_stop.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        return qprocess_stop

    @classmethod
    def restart(self, cfg: HelperConfig) -> QProcess:
        return launch_service(cfg, restart=True)

    @classmethod
    def get_current_state(self, cfg: HelperConfig) -> AbstractService.State:
        output = parse_service_status()
        is_running = False
        current_plist_path = None
        if output is not None:
            common: Dict[str, any] = output.get(service_id, {})
            is_running = common.get("state", "") == "running"
            current_plist_path = common.get("path", "")
        is_sync = current_plist_path is not None and current_plist_path == abspath(
            cfg.active_config_path
        )

        if not is_running:
            return AbstractService.State.STOPPED
        elif not is_sync:
            return AbstractService.State.TO_SYNC
        else:
            return AbstractService.State.STARTED

    @classmethod
    def migrate(self, cfg: HelperConfig) -> None:
        # TODO
        pass
