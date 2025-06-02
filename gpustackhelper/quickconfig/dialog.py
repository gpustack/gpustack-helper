import sys
from typing import Tuple, Dict
from PySide6.QtWidgets import (
    QDialog, 
    QVBoxLayout, 
    QHBoxLayout,
    QDialogButtonBox,
    QWidget,
    QStackedWidget,
    QListWidget,
    QListWidgetItem,
)

from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Signal
from gpustackhelper.config import HelperConfig, CleanConfig
from gpustackhelper.quickconfig.common import (
    wrap_layout,
    DataBindWidget
)
from gpustackhelper.quickconfig.general import GeneralConfigPage
from gpustackhelper.quickconfig.envvar import EnvironmentVariablePage

list_widget_style = """
    /* 整体列表样式 */
    QListWidget {
        background-color: #f5f5f5;  /* 微信风格的浅灰色背景 */
        border: none;
        outline: none;             /* 移除焦点边框 */
        font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; /* 微信常用字体 */
        font-size: 14px;
        padding: 8px 0;           /* 上下留白 */
    }

    /* 普通项目样式 */
    QListWidget::item {
        height: 44px;              /* 微信典型的项目高度 */
        padding: 0 16px;           /* 左右内边距 */
        border: none;
        background-color: transparent;
        color: #333333;            /* 主文字颜色 */
    }

    /* 悬停效果 - 微信风格的浅灰色背景 */
    QListWidget::item:hover {
        background-color: #ebebeb;
    }

    /* 选中状态 - 微信风格的蓝色指示条 */
    QListWidget::item:selected {
        background-color: #ffffff;  /* 选中项白色背景 */
        color: #07C160;             /* 微信绿色文字 */
        border-left: 3px solid #07C160; /* 左侧绿色指示条 */
        padding-left: 13px;         /* 补偿边框宽度 */
        font-weight: 500;           /* 中等加粗 */
    }

    /* 选中且悬停状态 */
    QListWidget::item:selected:hover {
        background-color: #f9f9f9;  /* 稍浅的背景 */
    }

    /* 移除默认的选中虚线框 */
    QListWidget::item:focus {
        outline: none;
    }

    /* 滚动条样式 - 微信风格的简约滚动条 */
    QListWidget::scroll-bar:vertical {
        width: 6px;
        background: transparent;
    }
    QListWidget::scroll-bar::handle:vertical {
        background: #cccccc;
        min-height: 30px;
        border-radius: 3px;
    }
    QListWidget::scroll-bar::handle:vertical:hover {
        background: #aaaaaa;
    }
"""


def create_list(stacked_widget: QStackedWidget, *pages: Tuple[str, QWidget]) -> QListWidget:
    list_widget = QListWidget()
    list_widget.setFixedWidth(150)
    list_widget.setStyleSheet(list_widget_style)

    for (title, widget) in pages:
        stacked_widget.addWidget(widget)
        list_widget.addItem(QListWidgetItem(title))
        
    list_widget.currentRowChanged.connect(stacked_widget.setCurrentIndex)
    if len(pages) > 0:
        list_widget.setCurrentRow(0)

    return list_widget


class QuickConfig(QDialog):
    cfg: HelperConfig = None
    signalOnShow = Signal(HelperConfig,CleanConfig, name='onShow')
    signalOnSave = Signal(HelperConfig,CleanConfig, name='onSave')
    pages: Tuple[Tuple[str, DataBindWidget]] = None
    def __init__(self, cfg: HelperConfig = None, *args):
        self.cfg = cfg
        super().__init__(*args)
        self.setWindowTitle("快速配置")
        if sys.platform != 'darwin':
            self.setWindowIcon(QIcon.fromTheme(QIcon.ThemeIcon.DocumentPageSetup))
        self.setFixedSize(600, 400)
        self.stacked_widget = QStackedWidget()
        self.pages = (
            ('通用', GeneralConfigPage(cfg, self.signalOnShow, self.signalOnSave)),
            ('环境变量', EnvironmentVariablePage(self.signalOnShow, self.signalOnSave)),
            )
        list_widget = create_list(self.stacked_widget, *self.pages)
        confirm = self.config_confirm()
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.stacked_widget)
        right_layout.addWidget(confirm)

        # 设置页的 layout 都平铺在这里
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 移除布局边距
        main_layout.setSpacing(0)  # 移除控件间距
        self.setLayout(main_layout)
        main_layout.addWidget(list_widget)
        right_widget = wrap_layout(right_layout)
        right_layout.setContentsMargins(0,0,20,20)
        main_layout.addWidget(right_widget)

    def config_confirm(self) -> QWidget:
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        return buttons

    def showEvent(self, event):
        self.cfg._reload()
        config = self.cfg.user_gpustack_config
        super().showEvent(event)
        self.signalOnShow.emit(self.cfg, config)

    def accept(self):
        # 处理ButtonGroup的状态，当选择不是 Server + Worker 时清空输入
        self.signalOnSave.emit(self.cfg, self.cfg.user_gpustack_config)
        
        helper_data: Dict[str, any] = {}
        config_data: Dict[str, any] = {}
        for (_, page) in self.pages:
            for binder in page.helper_binders:
                binder.update_config(helper_data)
            for binder in page.config_binders:
                binder.update_config(config_data)

        self.cfg.update_with_lock(**helper_data)
        config = self.cfg.user_gpustack_config
        config.update_with_lock(**config_data)

        super().accept()
        

from PySide6.QtWidgets import QApplication

if __name__ == "__main__":

    app = QApplication(sys.argv)
    # 创建一个假的 HelperConfig 以便调试
    class DummyConfig:
        def _reload(self): pass
        def update_with_lock(self, **kwargs): pass
        user_gpustack_config = type("DummyUserConfig", (), {
            "server_url": "",
            "token": "",
            "port": 0,
            "update_with_lock": lambda self, **kwargs: None
        })()

    dlg = QDialog()
    dlg.setWindowTitle("Env Group 调试")
    layout = QVBoxLayout(dlg)
    qc = QuickConfig(cfg=DummyConfig())
    env_group = qc.get_env_group()
    layout.addWidget(env_group)
    dlg.setLayout(layout)
    dlg.show()
    sys.exit(app.exec())