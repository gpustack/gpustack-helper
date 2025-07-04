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
from PySide6.QtCore import Qt, Signal, Slot
from gpustack_helper.config import (
    HelperConfig,
    GPUStackConfig,
    user_gpustack_config,
    user_helper_config,
)
from gpustack_helper.quickconfig.common import wrap_layout, DataBindWidget
from gpustack_helper.quickconfig.general import GeneralConfigPage
from gpustack_helper.quickconfig.envvar import EnvironmentVariablePage
from gpustack_helper.status import Status
from gpustack_helper.services.abstract_service import AbstractService as service

list_widget_style = """
    /* Main list style */
    QListWidget {
        background-color: #f5f5f5;  /* WeChat-style light gray background */
        border: none;
        outline: none;             /* Remove focus border */
        font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; /* Common WeChat fonts */
        font-size: 14px;
        padding: 8px 0;           /* Top and bottom padding */
    }

    /* Normal item style */
    QListWidget::item {
        height: 44px;              /* Typical WeChat item height */
        padding: 0 16px;           /* Left and right padding */
        border: none;
        background-color: transparent;
        color: #333333;            /* Main text color */
    }

    /* Hover effect - WeChat-style light gray background */
    QListWidget::item:hover {
        background-color: #ebebeb;
    }

    /* Selected state - WeChat-style blue indicator bar */
    QListWidget::item:selected {
        background-color: #ffffff;  /* Selected item white background */
        color: #07C160;             /* WeChat green text */
        border-left: 3px solid #07C160; /* Left green indicator bar */
        padding-left: 13px;         /* Compensate for border width */
        font-weight: 500;           /* Medium bold */
    }

    /* Selected and hovered state */
    QListWidget::item:selected:hover {
        background-color: #f9f9f9;  /* Slightly lighter background */
    }

    /* Remove default selected dashed border */
    QListWidget::item:focus {
        outline: none;
    }

    /* Scrollbar style - WeChat-style minimalist scrollbar */
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


def create_list(
    stacked_widget: QStackedWidget, *pages: Tuple[str, QWidget]
) -> QListWidget:
    list_widget = QListWidget()
    list_widget.setFixedWidth(150)
    list_widget.setStyleSheet(list_widget_style)

    for title, widget in pages:
        stacked_widget.addWidget(widget)
        list_widget.addItem(QListWidgetItem(title))

    list_widget.currentRowChanged.connect(stacked_widget.setCurrentIndex)
    if len(pages) > 0:
        list_widget.setCurrentRow(0)

    return list_widget


class QuickConfig(QDialog):
    signalOnShow = Signal(HelperConfig, GPUStackConfig, name="onShow")
    signalOnSave = Signal(HelperConfig, GPUStackConfig, name="onSave")
    pages: Tuple[Tuple[str, DataBindWidget]] = None
    status: Status = None

    def __init__(self, status: Status = None, *args):
        self.status = status
        super().__init__(*args)
        self.setWindowTitle(self.tr("Quick Config"))
        if sys.platform != "darwin":
            self.setWindowIcon(QIcon.fromTheme(QIcon.ThemeIcon.DocumentPageSetup))
        self.setFixedSize(600, 400)
        self.stacked_widget = QStackedWidget()
        self.pages = (
            (
                self.tr("General"),
                GeneralConfigPage(self.signalOnShow, self.signalOnSave),
            ),
            (
                self.tr("Environments"),
                EnvironmentVariablePage(self.signalOnShow, self.signalOnSave),
            ),
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
        right_layout.setContentsMargins(0, 0, 20, 20)
        main_layout.addWidget(right_widget)

        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

    def config_confirm(self) -> QDialogButtonBox:
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.rejected.connect(self.reject)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText(self.tr("Start"))
        ok.clicked.connect(self.save_and_start)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText(self.tr("Cancel"))

        @Slot()
        def on_state_changed(new_state: service.State):
            if new_state & service.State.STARTED:
                ok.setText(self.tr("Restart"))
                ok.setEnabled(True)
            elif new_state & service.State.STOPPED:
                ok.setText(self.tr("Start"))
                ok.setEnabled(True)
            else:
                ok.setText(self.tr("Start"))
                ok.setEnabled(False)

        self.status.status_signal.connect(on_state_changed)

        return buttons

    def showEvent(self, event):
        cfg = user_helper_config()
        cfg.reload()
        config = user_gpustack_config()
        config.reload()
        super().showEvent(event)
        self.signalOnShow.emit(cfg, config)
        self.raise_()
        self.activateWindow()

    def save_and_start(self):
        self.save()
        self.status.status = (
            service.State.STARTING
            if self.status.status & service.State.STOPPED
            else service.State.RESTARTING
        )

    def save(self):
        # 处理ButtonGroup的状态，当选择不是 Server + Worker 时清空输入
        cfg = user_helper_config()
        config = user_gpustack_config()
        self.signalOnSave.emit(cfg, config)

        helper_data: Dict[str, any] = {}
        config_data: Dict[str, any] = {}
        for _, page in self.pages:
            for binder in page.helper_binders:
                binder.update_config(helper_data)
            for binder in page.config_binders:
                binder.update_config(config_data)

        cfg.update_with_lock(**helper_data)
        config.update_with_lock(**config_data)

        super().accept()
