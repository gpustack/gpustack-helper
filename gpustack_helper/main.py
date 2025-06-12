import sys
import signal
import argparse
import logging
import os
from gpustack.utils.process import add_signal_handlers
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtCore import Slot, QUrl, QTimer
from typing import Dict, Any, List
import multiprocessing
from gpustack_helper.databinder import DataBinder
from gpustack_helper.defaults import (
    log_file_path,
    open_and_select_file,
    open_with_app,
)
from gpustack_helper.config import HelperConfig
from gpustack_helper.quickconfig.dialog import QuickConfig
from gpustack_helper.status import Status
from gpustack_helper.common import create_menu_action, show_warning
from gpustack_helper.icon import get_icon
from gpustack_helper.services.abstract_service import AbstractService as service

logger = logging.getLogger(__name__)


def show_about():
    from PySide6.QtWidgets import QMessageBox

    try:
        import gpustack

        version = gpustack.__version__
    except Exception:
        version = "未知"
    QMessageBox.information(None, "关于", f"GPUStack\n版本: {version}")


@Slot()
def open_log_dir() -> None:
    open_with_app(log_file_path)


@Slot()
def open_browser(parent: QWidget, cfg: HelperConfig) -> None:
    config = cfg.user_gpustack_config.load_active_config()
    if config.server_url is not None and config.server_url != "":
        url = QUrl(config.server_url)
    else:
        is_tls = config.ssl_certfile is not None and config.ssl_keyfile is not None
        port = config.port
        if port is None or port == 0:
            port = 443 if is_tls else 80
        hostname = (
            config.host
            if config.host is not None and config.host != ""
            else "localhost"
        )
        if hostname == "0.0.0.0":
            hostname = "localhost"
        url = QUrl(f"http{'s' if is_tls else ''}://{hostname}:{port}")

    # 使用默认浏览器打开URL
    # TODO 如果打开不了的话需要弹出消息框
    if not QDesktopServices.openUrl(url):
        show_warning(
            parent,
            "打开浏览器失败",
            f"无法打开 URL: {url.toString()}\n请检查您的默认浏览器设置。",
        )


@Slot(service.State)
def set_tray_icon(
    tray_icon: QSystemTrayIcon,
    normal_icon: QIcon,
    disabled_icon: QIcon,
    state: service.State,
):
    if state == service.State.STARTED or state == service.State.TO_SYNC:
        icon = normal_icon
    else:
        icon = disabled_icon
    tray_icon.setIcon(icon)


@Slot(service.State)
def widget_enabled_on_state(widget: QWidget, state: service.State):
    widget.setEnabled(state == service.State.STARTED or state == service.State.TO_SYNC)


class Configuration:
    cfg: HelperConfig
    open_config: QAction
    quick_config: QAction
    quick_config_dialog: QuickConfig
    boot_on_start: QAction
    copy_token: QAction
    binders: List[DataBinder] = list()

    def __init__(self, cfg: HelperConfig, status: Status, parent: QMenu):
        self.cfg = cfg
        parent.aboutToShow.connect(self.on_menu_shown)

        self.boot_on_start = create_menu_action("开机启动", parent)
        self.boot_on_start.setCheckable(True)
        self.binders.append(HelperConfig.bind("RunAtLoad", self.boot_on_start))
        self.boot_on_start.toggled.connect(self.update_and_save)

        # 快速配置
        self.quick_config_dialog = QuickConfig(cfg, status)
        self.quick_config = create_menu_action("快速配置", parent)
        self.quick_config.triggered.connect(self.quick_config_dialog.show)

        self.open_config = create_menu_action("配置目录", parent)
        self.open_config.triggered.connect(self.open_config_dir)

        self.copy_token = create_menu_action("复制Token", parent)
        self.copy_token.triggered.connect(self.copy_token_to_clipboard)
        self.copy_token.setDisabled(True)
        status.status_signal.connect(
            lambda x: widget_enabled_on_state(self.copy_token, x)
        )
        parent.addSeparator()

    @Slot()
    def open_config_dir(self) -> None:
        config = self.cfg.user_gpustack_config
        if not os.path.exists(config.filepath):
            config._save()
        open_and_select_file(config.filepath)

    @Slot()
    def on_menu_shown(self):
        for binder in self.binders:
            binder.load_config.emit(self.cfg)

    @Slot()
    def update_and_save(self):
        content: Dict[str, Any] = {}
        for binder in self.binders:
            binder.update_config(content)
        self.cfg.update_with_lock(**content)
        for binder in self.binders:
            binder.load_config.emit(self.cfg)

    @Slot()
    def copy_token_to_clipboard(self):
        clickboard = QApplication.clipboard()
        gpustack_config = self.cfg.user_gpustack_config
        if gpustack_config.token is not None:
            clickboard.setText(gpustack_config.token)
            return

        token_path = os.path.join(self.cfg.active_data_dir, "token")
        if not os.path.exists(token_path):
            logger.warning("Token file does not exist.")
            return
        with open(token_path, "r", encoding="utf-8") as f:
            token = f.read().strip()
        if token:
            clickboard.setText(token)

    def is_first_boot(self) -> bool:
        return not os.path.exists(self.cfg.filepath)


def parse_args(args: argparse.Namespace) -> HelperConfig:
    config_path = getattr(args, "config_path", None)
    data_dir = getattr(args, "data_dir", None)
    binary_path = getattr(args, "binary_path", None)
    debug = getattr(args, "debug", False)

    return HelperConfig(config_path, data_dir, binary_path, debug)


def init_application(cfg: HelperConfig) -> QApplication:
    app = QApplication(sys.argv)
    normal_icon = get_icon(False)
    disabled_icon = get_icon(True)
    app.setQuitOnLastWindowClosed(False)

    tray_icon = QSystemTrayIcon(disabled_icon, parent=app, toolTip="GPUStack Helper")
    # 创建主菜单
    menu = QMenu()
    status = Status(menu, cfg)

    status.status_signal.connect(
        lambda x: set_tray_icon(tray_icon, normal_icon, disabled_icon, x)
    )
    app.aboutToQuit.connect(status.wait_for_process_finish)

    open_gpustack = create_menu_action("控制台", menu)
    open_gpustack.triggered.connect(lambda: open_browser(menu, cfg))
    open_gpustack.setDisabled(True)
    status.status_signal.connect(lambda x: widget_enabled_on_state(open_gpustack, x))
    menu.addSeparator()

    configure = Configuration(cfg, status, menu)

    # 打开日志
    log_action = create_menu_action("显示日志", menu)
    log_action.triggered.connect(open_log_dir)
    log_action.setDisabled(True)
    menu.addSeparator()
    # 添加“关于”菜单项
    about_action = QAction("关于", menu)

    about_action.triggered.connect(show_about)
    menu.addAction(about_action)

    # 添加退出菜单项
    exit_action = QAction("退出", menu)
    exit_action.triggered.connect(app.quit)
    menu.addAction(exit_action)

    tray_icon.setContextMenu(menu)
    timer: QTimer = QTimer(menu)

    @Slot()
    def interval_check():
        status.update_menu_status()
        if os.path.exists(log_file_path):
            log_action.setEnabled(True)
        else:
            log_action.setDisabled(True)

    timer.timeout.connect(interval_check)
    timer.start(2000)

    tray_icon.show()

    if configure.is_first_boot():
        configure.quick_config_dialog.show()
    return app


def main():
    # Let Ctrl+C terminate the program
    add_signal_handlers()
    if sys.platform == "win32":
        from gpustack_helper.admin_prompt_win import check_and_prompt_admin

        check_and_prompt_admin()
    else:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    parser = argparse.ArgumentParser(description="GPUStack Helper")
    parser.add_argument(
        "--config", default=None, type=str, help="GPUStack helper config path"
    )
    parser.add_argument(
        "--debug", default=None, action="store_true", help="Enable debug logs"
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        type=str,
        help="The GPUStack data dir path for debugging",
    )
    parser.add_argument(
        "--binary-path", default=None, type=str, help="The GPUStack Binary Path"
    )
    args, _ = parser.parse_known_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    cfg = parse_args(args)
    app = init_application(cfg)
    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    multiprocessing.set_start_method("spawn", force=True)
    main()
