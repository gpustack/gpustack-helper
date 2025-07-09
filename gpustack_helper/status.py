import logging
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication
from PySide6.QtCore import Slot, Signal, QProcess, QThread, QCoreApplication
from typing import Optional, Tuple, Union, Dict
from gpustack_helper.config import (
    user_gpustack_config,
    active_gpustack_config,
    active_helper_config,
)
from gpustack_helper.common import create_menu_action, show_warning
from gpustack_helper.services.abstract_service import AbstractService as service
from gpustack_helper.services.factory import get_service_class

logger = logging.getLogger(__name__)


class Status(QMenu):
    status_signal = Signal(service.State)
    start_or_stop: QAction
    restart: QAction

    _status: service.State = None
    translations: Dict[str, str] = None

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

    def __init__(self, parent: QMenu):
        self._status = service.State.UNKNOWN
        # --- status
        super().__init__(parent)
        self.translations = {
            "Start": QCoreApplication.translate("Status", "Start"),
            "Stop": QCoreApplication.translate("Status", "Stop"),
            "Restart": QCoreApplication.translate("Status", "Restart"),
            "Status": QCoreApplication.translate("Status", "Status ({status})"),
        }
        self.setTitle(
            self.translations["Status"].format(
                status=service.get_display_text(self._status)
            )
        )
        parent.addMenu(self)

        self.start_or_stop = create_menu_action(self.translations["Start"], self)
        self.start_or_stop.triggered.connect(self.start_or_stop_action)
        self.start_or_stop.setDisabled(True)

        self.addSeparator()
        self.restart = create_menu_action(self.translations["Restart"], self)
        self.restart.setDisabled(True)
        self.restart.triggered.connect(self.restart_action)

        self.update_menu_status()
        self.update_title()
        # functions
        self.status_signal.connect(self.on_status_changed)
        # QProcess 实例
        self.qprocess = None

    def start_process(
        self,
        process: Union[QProcess, QThread],
        state_to_change: Tuple[service.State, service.State],
    ):
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
                logger.info("Service thread finished successfully")
                self.status = state_to_change[1]
                self.qprocess.deleteLater()
                self.qprocess = None
                active_gpustack_config().reload()
                active_helper_config().reload()

            self.qprocess.finished.connect(on_thread_finish)
        elif isinstance(self.qprocess, QProcess):

            def on_process_finish(code: int, status: QProcess.ExitStatus):
                if code == 0:
                    logger.info("Service process finished successfully")
                    self.status = state_to_change[1]
                else:
                    stderr = bytes(self.qprocess.readAllStandardError()).decode()
                    stdout = bytes(self.qprocess.readAllStandardOutput()).decode()
                    logger.error(
                        f"Service process failed: stdout: {stdout} stderr: {stderr}"
                    )
                    self.status = state_to_change[0]
                self.qprocess.deleteLater()
                self.qprocess = None
                active_gpustack_config().reload()
                active_helper_config().reload()

            self.qprocess.finished.connect(on_process_finish)
        self.qprocess.start()

    @Slot(service.State)
    def on_status_changed(self, status: service.State):
        self.update_title(status)
        self.start_or_stop.setText(
            self.translations["Start"]
            if status & service.State.STOPPED
            else self.translations["Stop"]
        )
        # need to use launchctl to create service
        if status == service.State.STARTING:
            self.start_process(
                self.service_class.start(),
                (service.State.STOPPED, service.State.STARTED),
            )
        elif status == service.State.RESTARTING:
            self.start_process(
                self.service_class.restart(),
                (service.State.STOPPED, service.State.STARTED),
            )
        elif status == service.State.STOPPING:
            self.start_process(
                self.service_class.stop(),
                (service.State.UNKNOWN, service.State.STOPPED),
            )

        if status & service.State.STARTED:
            self.restart.setEnabled(True)
        else:
            self.start_or_stop.setDisabled(False)
            self.restart.setEnabled(False)

    def update_title(self, status: Optional[service.State] = None):
        if status is None:
            status = self.status
        title = QCoreApplication.translate("Status", "Status ({status})").format(
            status=service.get_display_text(status)
        )
        self.setTitle(title)

    @Slot()
    def start_or_stop_action(self):
        self.start_or_stop.setDisabled(True)
        if bool(self.status & service.State.STOPPED):
            self.start_action(
                skip_config_check=bool(self.status & service.State.TO_MIGRATE)
            )
        else:
            self.stop_action()
        self.start_or_stop.setEnabled(True)

    @Slot()
    def restart_action(self):
        self.restart.setDisabled(True)
        self.status = service.State.RESTARTING

    def stop_action(self):
        self.status = service.State.STOPPING

    def start_action(self, skip_config_check: bool = False):
        if not skip_config_check:
            try:
                user_gpustack_config().validate_updates()
            except Exception as e:
                show_warning(
                    self,
                    QGuiApplication.translate("GPUStackConfig", "Configuration Error"),
                    QGuiApplication.translate("GPUStackConfig", "{error}").format(
                        error=str(e)
                    ),
                )
                return
        self.status = service.State.STARTING

    @Slot()
    def update_menu_status(self):
        logger.debug("Query service status")
        if not self.start_or_stop.isEnabled():
            self.start_or_stop.setEnabled(True)
        if self.qprocess is not None:
            if (
                isinstance(self.qprocess, QProcess)
                and self.qprocess.state() == QProcess.ProcessState.Running
            ):
                logger.debug("Process is running, skipping status update")
                return
            elif isinstance(self.qprocess, QThread) and self.qprocess.isRunning():
                logger.debug("Thread is running, skipping status update")
                return
        user_gpustack_config().reload()
        active_gpustack_config().reload()
        active_helper_config().reload()
        self.status = self.service_class.get_current_state()

    @Slot()
    def wait_for_process_finish(self):
        if self.qprocess is not None:
            if isinstance(self.qprocess, QProcess):
                self.qprocess.waitForFinished()
            elif isinstance(self.qprocess, QThread):
                self.qprocess.wait()
