import logging
from PySide6.QtWidgets import (
    QMenu,
    QMessageBox,
)
import socket
import subprocess
import re
import os
from os.path import abspath, dirname, exists, islink
from enum import Enum
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtCore import QTimer, Slot, Signal, QProcess
from typing import Dict, Any, Optional, List, Tuple
from gpustackhelper.config import HelperConfig
from gpustackhelper.common import create_menu_action, show_warning

logger = logging.getLogger(__name__)
service_id = 'system/ai.gpustack'
plist_path = "/Library/LaunchDaemons/ai.gpustack.plist"

def get_service_status(service: str) -> Dict[str, Any]:
    data = {}
    current_section = None
    try:
        result = subprocess.run(
            ["launchctl", "print", service],
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

class state(Enum):
    STOPPED = ("stopped", "停止")
    STOPPING = ("stopping", "停止中")
    RESTARTING = ("restarting", "重新启动中")
    STARTING = ("starting", "启动中")
    TO_SYNC = ("to_sync", "需要同步")
    UNKNOWN = ("unknown", "未知")
    STARTED = ("started", "运行中")
    def __init__(self, state, display_text):
        self.state = state  # 内部状态值
        self.display_text = display_text  # 显示文本

    @classmethod
    def get_display_text(cls, state):
        return next((status.display_text for status in cls if status.state == state), "未知状态")

class Status(QMenu):
    status_signal = Signal(state)
    cfg: HelperConfig
    start_or_stop: QAction
    restart: QAction
    
    _status: state = state.UNKNOWN
    @property
    def status(self) -> state:
        return self._status
    @status.setter
    def status(self, value: state) -> None:
        self._status = value
        self.status_signal.emit(value)

    group: QActionGroup

    manual: QAction
    foreground: QAction
    daemon: QAction
    timer: QTimer
    qprocess_launch: Optional[QProcess] = None
    qprocess_stop: Optional[QProcess] = None

    def __init__(self, parent: QMenu, cfg: HelperConfig):
        self.cfg = cfg
        # --- status
        super().__init__(f'状态({self.status.display_text})',parent)
        parent.addMenu(self)
        
        self.start_or_stop = create_menu_action("启动", self)
        self.start_or_stop.triggered.connect(self.start_or_stop_action)
        self.start_or_stop.setDisabled(True)


        self.addSeparator()
        self.restart = create_menu_action("重新启动", self)
        self.restart.setDisabled(True)
        self.restart.triggered.connect(self.restart_action)

        self.update_menu_status()
        self.update_title()
        # functions
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_menu_status)
        self.status_signal.connect(self.on_status_changed)
        # QProcess 实例
        self.qprocess_launch = None
        self.qprocess_stop = None
        
    @Slot(state)
    def on_status_changed(self, status: state):
        """状态改变时的处理函数"""
        self.update_title(status)
        self.start_or_stop.setText("启动" if status == state.STOPPED else "停止")
        
        # need to use launchctl to create service
        if status == state.STARTING or status == state.RESTARTING:
            self.launch_service(restart=status == state.RESTARTING)
        elif status == state.STOPPING:
            self.stop_service()
        # self.open_gpustack.setEnabled(status == _state.STARTED or status == _state.TO_SYNC)
        if status == state.TO_SYNC or status == state.STARTED:
            self.restart.setEnabled(True)
        else:
            self.start_or_stop.setDisabled(False)
            self.restart.setEnabled(False)


    def update_title(self, status: Optional[state] = None):
        if status is None:
            status = self.status
        self.setTitle(f'状态({status.display_text})')

    @Slot()
    def start_or_stop_action(self):
        self.start_or_stop.setDisabled(True)
        if self.status == state.STOPPED and not self.is_port_available():
            config = self.cfg.user_gpustack_config
            port = config.port
            host = config.host
            show_warning(self, "端口不可用", f"无法启动服务，因为端口 {host}:{port} 已被占用。请检查是否有其他服务在运行。")
        else:
            self.status = state.STARTING if self.status == state.STOPPED else state.STOPPING
        self.start_or_stop.setEnabled(True)

    @Slot()
    def restart_action(self):
        self.restart.setDisabled(True)
        self.status = state.RESTARTING

    def start_load_status(self):
        self.timer.start(2000)
    
    @Slot()
    def update_menu_status(self):
        """根据服务状态更新菜单项状态"""
        logger.debug("准备查询服务状态")
        if not self.start_or_stop.isEnabled():
            self.start_or_stop.setEnabled(True)
        if self.qprocess_launch is not None and self.qprocess_launch.state() == QProcess.Running:
            logger.debug("正在等待服务状变更")
            return
        output = get_service_status(service_id)
        is_running = False
        current_plist_path = None
        if output is not None:
            common:Dict[str, any] = output.get(service_id, {})
            is_running = common.get('state','') == "running"
            current_plist_path = common.get('path', '')
        is_sync = current_plist_path is not None and current_plist_path == abspath(self.cfg.active_config_path)
        
        if not is_running:
            self.status = state.STOPPED
        elif not is_sync:
            self.status = state.TO_SYNC
        else:
            self.status = state.STARTED

    def launch_service(self, restart: bool = False) -> None:
        """
        prompt sudo privileges to run following command
        1. remove /Library/LaunchDaemons/ai.gpustack.plist if not a symlink or not targetting the right path
        2. create a symlink to /Library/LaunchDaemons/ai.gpustack.plist pointing to self.cfg.filepath
        3. launch service with launchctl bootstrap system /Library/LaunchDaemons/ai.gpustack.plist
        the commands will be put into an AppleScript to run with administrator privileges
        """
        applescript = get_start_script(self.cfg,restart=restart)
        if self.qprocess_launch is not None:
            self.qprocess_launch.deleteLater()
        self.qprocess_launch = QProcess(self)
        self.qprocess_launch.finished.connect(lambda code, status: self._on_launch_service_finished(code, status, restart))
        self.qprocess_launch.setProgram("osascript")
        self.qprocess_launch.setArguments(['-e', applescript])
        self.qprocess_launch.setProcessChannelMode(QProcess.MergedChannels)
        self.qprocess_launch.start()

    def _on_launch_service_finished(self, exitCode, exitStatus, restart):
        if exitCode == 0:
            logger.info(f"服务已通过 AppleScript {'启动' if not restart else '重新启动'}")
            self.status = state.STARTED
        else:
            stderr = bytes(self.qprocess_launch.readAllStandardOutput()).decode()
            logger.error(f"通过 AppleScript 启动服务失败: {stderr}")
            self.status = state.STOPPED
        self.qprocess_launch.deleteLater()
        self.qprocess_launch = None

    def stop_service(self) -> None:
        # prompt sudo privileges to run following command
        # 1. run launchctl bootout system /Library/LaunchDaemons/ai.gpustack.plist
        script = f"""
do shell script "\
launchctl bootout {service_id}\
" with prompt "GPUStack 需要停止后台服务" with administrator privileges
        """
        if self.qprocess_stop is not None:
            self.qprocess_stop.deleteLater()
        self.qprocess_stop = QProcess(self)
        self.qprocess_stop.finished.connect(self._on_stop_service_finished)
        self.qprocess_stop.setProgram("osascript")
        self.qprocess_stop.setArguments(["-e", script])
        self.qprocess_stop.setProcessChannelMode(QProcess.MergedChannels)
        self.qprocess_stop.start()

    def _on_stop_service_finished(self, exitCode, exitStatus):
        if exitCode == 0:
            logger.info("服务已通过 AppleScript 停止")
            self.status = state.STOPPED
        else:
            stderr = bytes(self.qprocess_stop.readAllStandardError()).decode()
            logger.error(f"通过 AppleScript 停止服务失败: {stderr}")
            self.status = state.UNKNOWN
        self.qprocess_stop.deleteLater()
        self.qprocess_stop = None
    
    def wait_for_process_finish(self):
        """
        等待当前的 QProcess 实例完成
        """
        if self.qprocess_launch is not None:
            self.qprocess_launch.waitForFinished()
        if self.qprocess_stop is not None:
            self.qprocess_stop.waitForFinished()
    def is_port_available(self) -> bool:
        config = self.cfg.user_gpustack_config
        port = config.port
        host = config.host
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return True
            except OSError:
                return False
        

def get_start_script(cfg: HelperConfig, restart: bool = False) -> str:
    gpustack_config = cfg.user_gpustack_config
    target_path = abspath(cfg.active_config_path)
    if not os.path.exists(cfg.filepath):
        cfg.update_with_lock()
    if not os.path.exists(gpustack_config.filepath):
        gpustack_config.update_with_lock()
    files_copy: List[Tuple[str, str]] = [(abspath(cfg.filepath), target_path)]
    if gpustack_config.filepath != gpustack_config.active_config_path:
        files_copy.append((abspath(gpustack_config.filepath), abspath(gpustack_config.active_config_path)),)
    # 过滤掉不存在的源文件
    def files_different(pair: Tuple[str, str]) -> bool:
        src, dst = pair
        if not exists(src):
            return False
        if not exists(dst):
            return True
        with open(src, 'rb') as fsrc, open(dst, 'rb') as fdst:
            return fsrc.read() != fdst.read()
        
    files_copy = list(filter(files_different, files_copy))
    copy_script = ";".join(
        f"cp -f '{src}' '{dst}'; chmod 0644 '{dst}'; chown root:whel '{dst}'" for src, dst in files_copy
    )
    copy_script = f"mkdir -p '{dirname(target_path)}'; {copy_script}" if len(files_copy) != 0 else None
    link_script = f"rm -f '{plist_path}'; ln -sf '{target_path}' '{plist_path}'" if not exists(plist_path) or not islink(plist_path) or os.readlink(plist_path) != target_path or copy_script is not None else None
    register_command = f"launchctl bootstrap system {plist_path}" if not restart else None
    start_command = f"launchctl kickstart {'-k ' if restart else ''}{service_id}"
    joined_script = ";".join(filter(None, [copy_script, link_script, register_command, start_command]))
    logger.debug(f"准备以admin权限运行该shell脚本 :\n{joined_script}")
    return f"""do shell script "{joined_script}" with prompt "GPUStack 需要启动后台服务" with administrator privileges"""
