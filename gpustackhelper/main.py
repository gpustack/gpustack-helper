import sys
import signal
import argparse
import logging
import os
from gpustack.utils.process import add_signal_handlers
from PySide6.QtWidgets import (
    QApplication, 
    QSystemTrayIcon, 
    QMenu,
)
from PySide6.QtGui import QIcon, QAction, QDesktopServices
from PySide6.QtCore import Slot, QUrl
from typing import Dict, Any, List
import multiprocessing
from gpustackhelper.databinder import DataBinder
from gpustackhelper.defaults import (
    log_file_path,
    icon_path,
    open_and_select_file,
    open_with_app,
)
from gpustackhelper.config import HelperConfig
from gpustackhelper.quickconfig  import QuickConfig
from gpustackhelper.status import Status, state
from gpustackhelper.common import create_menu_action
from gpustackhelper.icon import get_icon

logger = logging.getLogger(__name__)

def show_about():
    from PySide6.QtWidgets import QMessageBox
    try:
        import gpustack
        version = gpustack.__version__
    except Exception:
        version = '未知'
    QMessageBox.information(None, '关于', f'GPUStack\n版本: {version}')

@Slot()
def open_log_dir() -> None:
    open_with_app(log_file_path)

@Slot()
def open_browser(cfg: HelperConfig) -> None:
    config = cfg.user_gpustack_config.load_active_config()
    if config.server_url is not None and config.server_url != '':
        url = QUrl(config.server_url)
    else:
        is_tls = config.ssl_certfile is not None and config.ssl_keyfile is not None
        port = config.port
        if port is None or port == 0:
            port = 443 if is_tls else 80
        hostname = config.host if config.host is not None and config.host != '' else 'localhost'
        url = QUrl(f"http{'s' if is_tls else ''}://{hostname}:{port}")
    
    # 使用默认浏览器打开URL
    # TODO 如果打开不了的话需要弹出消息框
    if not QDesktopServices.openUrl(url):
        print("无法打开浏览器")

class Configuration():
    cfg: HelperConfig
    open_config: QAction
    quick_config: QAction
    quick_config_dialog: QuickConfig
    boot_on_start: QAction
    copy_token: QAction
    binders: List[DataBinder] = list()
    def __init__(self, cfg: HelperConfig ,parent: QMenu):
        self.cfg = cfg
        parent.aboutToShow.connect(self.on_menu_shown)

        self.boot_on_start = create_menu_action("开机启动", parent)
        self.boot_on_start.setCheckable(True)
        self.binders.append(HelperConfig.bind('RunAtLoad', self.boot_on_start))
        self.boot_on_start.toggled.connect(self.update_and_save)

        # 快速配置
        self.quick_config_dialog = QuickConfig(cfg)
        self.quick_config = create_menu_action("快速配置", parent)
        self.quick_config.triggered.connect(self.quick_config_dialog.show)

        self.open_config = create_menu_action("配置目录", parent)
        self.open_config.triggered.connect(self.open_config_dir)

        self.copy_token = create_menu_action("复制Token", parent)
        self.copy_token.triggered.connect(self.copy_token_to_clipboard)
        self.copy_token.setDisabled(True)
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
        content: Dict[str, Any] ={}
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
        
        token_path = os.path.join(self.cfg.active_data_dir, 'token')
        if not os.path.exists(token_path):
            logger.warning("Token file does not exist.")
            return
        with open(token_path, 'r', encoding='utf-8') as f:
            token = f.read().strip()
        if token:
            clickboard.setText(token)
    
    @Slot(state)
    def on_status_changed(self, state: state):
        self.copy_token.setEnabled(state == state.STARTED or state == state.TO_SYNC)

def main():
    parser = argparse.ArgumentParser(description='GPUStack Helper')
    parser.add_argument('--data-dir', type=str, default=None, help='数据目录')
    parser.add_argument('--config-path', type=str, default=None, help='helper 配置文件路径')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--binary-path', type=str, default=None, help='GPUStack 二进制文件路径')
    args, _ = parser.parse_known_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 让 Ctrl+C 能终止程序
    add_signal_handlers()
    if sys.platform != 'win32':
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    cfg = HelperConfig(args.config_path, args.data_dir, args.binary_path, debug= args.debug)

    # 创建系统托盘图标
    normal_icon = get_icon(False)
    disabled_icon = get_icon(True)
    tray_icon = QSystemTrayIcon(disabled_icon)
    tray_icon.setToolTip('GPUStack Helper')
    # 创建主菜单
    menu = QMenu()
    status = Status(menu, cfg)
    
    @Slot()
    def set_tray_icon(state: state):
        if state == state.STARTED or state == state.TO_SYNC:
            icon = normal_icon
        else:
            icon = disabled_icon
        tray_icon.setIcon(icon)
    status.status_signal.connect(set_tray_icon)

    open_gpustack = create_menu_action("控制台", menu)
    open_gpustack.triggered.connect(lambda: open_browser(cfg))
    open_gpustack.setDisabled(True)
    menu.addSeparator()
    
    @Slot()
    def console_on_status_changed(state: state):
        open_gpustack.setEnabled(state == state.STARTED or state == state.TO_SYNC)
    status.status_signal.connect(console_on_status_changed)

    @Slot()
    def cleanup():
        status.wait_for_process_finish()
            
    app.aboutToQuit.connect(cleanup)

    configure = Configuration(cfg, menu)
    status.status_signal.connect(configure.on_status_changed)



    # 打开日志
    log_action = create_menu_action("显示日志", menu)
    log_action.triggered.connect(open_log_dir)
    menu.addSeparator()
    # 添加“关于”菜单项
    about_action = QAction('关于', menu)

    about_action.triggered.connect(show_about)
    menu.addAction(about_action)

    # 添加退出菜单项
    exit_action = QAction('退出', menu)
    exit_action.triggered.connect(app.quit)
    menu.addAction(exit_action)

    tray_icon.setContextMenu(menu)
    status.start_load_status()
    tray_icon.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    multiprocessing.set_start_method('spawn', force=True)
    main()

