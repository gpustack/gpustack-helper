import logging
from PySide6.QtWidgets import QMenu
import socket
from os.path import abspath
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtCore import Slot, Signal, QProcess, QThread
from typing import Dict, Optional, Tuple, Union
from gpustack_helper.config import HelperConfig
from gpustack_helper.common import create_menu_action, show_warning
from gpustack_helper.services.abstract_service import AbstractService as service
from gpustack_helper.services.factory import get_service_class

logger = logging.getLogger(__name__)

class Status(QMenu):
    status_signal = Signal(service.State)
    cfg: HelperConfig
    start_or_stop: QAction
    restart: QAction
    
    _status: service.State = None
    @property
    def status(self) -> service.State:
        return self._status
    @status.setter
    def status(self, value: service.State) -> None:
        self._status = value
        self.status_signal.emit(value)

    group: QActionGroup
    manual: QAction
    foreground: QAction
    daemon: QAction

    qprocess: Optional[Union[QProcess, QThread]] = None

    service_class: service = get_service_class()

    def __init__(self, parent: QMenu, cfg: HelperConfig):
        self.cfg = cfg
        self._status = service.State.UNKNOWN
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
        self.status_signal.connect(self.on_status_changed)
        # QProcess 实例
        self.qprocess = None
    
    def start_process(self, process: Union[QProcess, QThread], state_to_change: Tuple[service.State, service.State]):
        """
        Start process and connect its finished signal to handle the process completion.
        state_to_change is a tuple of (failed_state, sueccess_state) to change the status.
        """
        if self.qprocess is not None:
            self.qprocess.deleteLater()
        process.setParent(self)
        self.qprocess = process
        if isinstance(self.qprocess, QThread):
            def on_thread_finish():
                logger.info("服务线程已成功完成")
                self.status = state_to_change[1]
                self.qprocess.deleteLater()
                self.qprocess = None
            self.qprocess.finished.connect(on_thread_finish)
        elif isinstance(self.qprocess, QProcess):
            def on_process_finish(code: int, status: QProcess.ExitStatus):
                if code == 0:
                    logger.info("服务进程已成功完成")
                    self.status = state_to_change[1]
                else:
                    stderr = bytes(self.qprocess.readAllStandardError()).decode()
                    logger.error(f"服务进程失败: {stderr}")
                    self.status = state_to_change[0]
                self.qprocess.deleteLater()
                self.qprocess = None
            self.qprocess.finished.connect(on_process_finish)
        self.qprocess.start()
    

    @Slot(service.State)
    def on_status_changed(self, status: service.State):
        """状态改变时的处理函数"""
        self.update_title(status)
        self.start_or_stop.setText("启动" if status == service.State.STOPPED else "停止")
        # need to use launchctl to create service
        if status == service.State.STARTING:
            self.start_process(self.service_class.start(self.cfg),(service.State.STOPPED, service.State.STARTED))
        elif status == service.State.RESTARTING:
            self.start_process(self.service_class.restart(self.cfg),(service.State.STOPPED, service.State.STARTED))
        elif status == service.State.STOPPING:
            self.start_process(self.service_class.stop(self.cfg),(service.State.UNKNOWN, service.State.STOPPED))

        if status == service.State.TO_SYNC or status == service.State.STARTED:
            self.restart.setEnabled(True)
        else:
            self.start_or_stop.setDisabled(False)
            self.restart.setEnabled(False)

    def update_title(self, status: Optional[service.State] = None):
        if status is None:
            status = self.status
        self.setTitle(f'状态({status.display_text})')

    @Slot()
    def start_or_stop_action(self):
        self.start_or_stop.setDisabled(True)
        if self.status == service.State.STOPPED and not self.is_port_available():
            config = self.cfg.user_gpustack_config
            port = config.port
            host = config.host
            show_warning(self, "端口不可用", f"无法启动服务，因为端口 {host}:{port} 已被占用。请检查是否有其他服务在运行。")
        else:
            self.status = service.State.STARTING if self.status == service.State.STOPPED else service.State.STOPPING
        self.start_or_stop.setEnabled(True)

    @Slot()
    def restart_action(self):
        self.restart.setDisabled(True)
        self.status = service.State.RESTARTING
    
    @Slot()
    def update_menu_status(self):
        """根据服务状态更新菜单项状态"""
        logger.debug("Query service status")
        if not self.start_or_stop.isEnabled():
            self.start_or_stop.setEnabled(True)
        if self.qprocess is not None:
            if isinstance(self.qprocess, QProcess) and self.qprocess.state() == QProcess.ProcessState.Running:
                logger.debug("Process is running, skipping status update")
                return
            elif isinstance(self.qprocess, QThread) and self.qprocess.isRunning():
                logger.debug("Thread is running, skipping status update")
                return
        self.status = self.service_class.get_current_state(self.cfg)

    def wait_for_process_finish(self):
        """
        等待当前的 QProcess 实例完成
        """
        if self.qprocess is not None:
            if isinstance(self.qprocess, QProcess):
                self.qprocess.waitForFinished()
            elif isinstance(self.qprocess, QThread):
                self.qprocess.wait()

    def is_port_available(self) -> bool:
        config = self.cfg.user_gpustack_config
        port = config.port
        host = config.host
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, port))
                return True
            except OSError as e:
                logger.debug(f"端口 {host}:{port} 不可用: {e}")
                return False
        
