import subprocess
import logging
import re
import os
from os.path import exists, islink
from typing import Dict, Any, List, Tuple
from PySide6.QtCore import QProcess
from gpustack_helper.config import (
    user_helper_config,
    active_helper_config,
    user_gpustack_config,
    active_gpustack_config,
    legacy_gpustack_config,
    all_config_sync,
)
from gpustack_helper.services.abstract_service import AbstractService
from gpustack_helper.defaults import (
    get_dac_filename,
    resource_path,
    runtime_plist_path as plist_path,
)

logger = logging.getLogger(__name__)

service_id = "system/ai.gpustack"


def bash_escape_spaces(s: str) -> str:
    return re.sub(r' ', r'\\ ', s)


def is_plist_synced(active_plist_path: str) -> bool:
    return (
        exists(plist_path)
        and islink(plist_path)
        and os.readlink(plist_path) == active_plist_path
    )


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


def get_start_script(restart: bool = False) -> str:
    helper_user = user_helper_config()
    helper_user.update_with_lock()
    helper_active = active_helper_config()

    gpustack_user = user_gpustack_config()
    gpustack_user.update_with_lock()
    gpustack_active = active_gpustack_config()

    files_copy: List[Tuple[str, str]] = [
        (user.config_path, active.config_path)
        for (user, active) in (
            (helper_user, helper_active),
            (gpustack_user, gpustack_active),
        )
    ]

    # 过滤掉不存在的源文件
    def files_different(pair: Tuple[str, str]) -> bool:
        src, dst = pair
        if src == dst:
            return False
        if not exists(src):
            return False
        if not exists(dst):
            return True
        with open(src, "rb") as fsrc, open(dst, "rb") as fdst:
            return fsrc.read() != fdst.read()

    files_copy = list(filter(files_different, files_copy))
    # migrate the legacy data dir
    old_gpustack_config = legacy_gpustack_config()
    migrate = (
        f"mkdir -p '{gpustack_active.data_dir}';"
        f"for f in {bash_escape_spaces(old_gpustack_config.data_dir)}/*;"
        "do case \\\"$f\\\" in *.sh) continue ;; esac;"
        f"mv -f \\\"$f\\\" '{gpustack_active.data_dir}';done"
        if old_gpustack_config
        else None
    )
    copy_files = ";".join(
        f"cp -f '{src}' '{dst}'; chmod 0644 '{dst}'; chown root:wheel '{dst}'"
        for src, dst in files_copy
    )
    copy_files = (
        f"mkdir -p '{gpustack_active.data_dir}'; {copy_files}"
        if len(files_copy) != 0
        else None
    )
    link_plist = (
        f"rm -f '{plist_path}'; ln -sf '{helper_active.config_path}' '{plist_path}'"
        if not is_plist_synced(helper_active.config_path) or copy_files is not None
        else None
    )
    # link target should be resources path of gpustack_helper and name would be dac filename
    # link source should be the dac filename in the gpustack_active.data_dir/root dir
    target_home = os.path.join(
        gpustack_active.data_dir, "root", '.cache', 'descript', 'dac'
    )
    dac_filename = get_dac_filename()
    source_filename = os.path.join(resource_path, dac_filename)
    target_filename = os.path.join(target_home, dac_filename)
    link_dac = (
        f"rm -f '{target_filename}'; mkdir -p '{target_home}'; ln -s '{source_filename}' '{target_filename}'"
        if exists(source_filename)
        and (
            not exists(target_filename)
            or not islink(target_filename)
            or os.readlink(target_filename) != source_filename
        )
        else None
    )
    service_exists = parse_service_status().get(service_id, None) is not None
    restart = service_exists or restart
    stop = f"launchctl bootout {service_id}" if restart else None
    wait_for_stopped = (
        f"while true; do launchctl print {service_id} >/dev/null 2>&1; [ $? -eq 113 ] && break; sleep 0.5; done"
        if restart
        else None
    )
    register_service = f"launchctl bootstrap system {plist_path}"
    start = f"launchctl kickstart {service_id}"
    joined_script = ";".join(
        filter(
            None,
            [
                stop,
                wait_for_stopped,
                migrate,
                copy_files,
                link_plist,
                link_dac,
                register_service,
                start,
            ],
        )
    )
    logger.debug(f"准备以admin权限运行该shell脚本 :\n{joined_script}")
    return f"""do shell script "{joined_script}" with prompt "GPUStack 需要启动后台服务" with administrator privileges"""


def launch_service(restart: bool = False) -> QProcess:
    """
    prompt sudo privileges to run following command
    1. remove /Library/LaunchDaemons/ai.gpustack.plist if not a symlink or not targetting the right path
    2. create a symlink to /Library/LaunchDaemons/ai.gpustack.plist pointing to active_gpustack_config.config_path
    3. launch service with launchctl bootstrap system /Library/LaunchDaemons/ai.gpustack.plist
    the commands will be put into an AppleScript to run with administrator privileges
    """
    applescript = get_start_script(restart=restart)
    qprocess_launch = QProcess()
    qprocess_launch.setProgram("osascript")
    qprocess_launch.setArguments(["-e", applescript])
    qprocess_launch.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
    logger.debug(f"Prepare to launch service {service_id}")
    return qprocess_launch


class DarwinService(AbstractService):
    @classmethod
    def start(self) -> QProcess:
        return launch_service(restart=False)

    @classmethod
    def stop(self) -> QProcess:
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
    def restart(self) -> QProcess:
        return launch_service(restart=True)

    @classmethod
    def get_current_state(self) -> AbstractService.State:
        helper_active = active_helper_config()
        if not is_plist_synced(helper_active.config_path):
            return AbstractService.State.TO_MIGRATE | AbstractService.State.STOPPED

        output = parse_service_status()
        is_running = False
        if output is not None:
            common: Dict[str, any] = output.get(service_id, {})
            is_running = common.get("state", "") == "running"
        # if current_plist_path is None, it means the service is not registered.
        is_sync = not is_running or all_config_sync()
        state = (
            AbstractService.State.STARTED
            if is_running
            else AbstractService.State.STOPPED
        )
        if not is_sync:
            state |= AbstractService.State.TO_SYNC

        return state
