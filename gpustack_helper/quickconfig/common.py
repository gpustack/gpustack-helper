from typing import Optional, Dict, Any, BinaryIO, List, Tuple, Union
from PySide6.QtWidgets import QLabel, QLineEdit, QSizePolicy, QSpinBox, QWidget, QLayout, QGroupBox, QFormLayout
from PySide6.QtCore import Qt, SignalInstance
from gpustack_helper.databinder import DataBinder
from gpustack_helper.config import HelperConfig, CleanConfig
from abc import abstractmethod

group_box_style = """
    QGroupBox {
        border: 1px solid transparent;
        margin-top: 1.5ex;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
    }
"""

def fixed_titled_input(title: str) -> Tuple[QLabel,QLineEdit]:
    label = QLabel(title)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)  # 固定标签大小
    input = QLineEdit()
    input.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)  # 输入框横向扩展
    return (label,input)

def fixed_titled_port_input(title: str) -> Tuple[QLabel, QSpinBox]:
    # validator = QIntValidator(0, 65535)  # 端口范围
    label = QLabel(title)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)  # 固定标签大小
    input = QSpinBox()
    input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)  # 输入框横向扩展
    input.setRange(0, 65535)  # 设置端口范围
    input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # 移除上下按钮
    return (label, input)

def wrap_layout(layout: QLayout) -> QWidget:
    rtn = QWidget()
    rtn.setLayout(layout)
    return rtn

def create_stand_box(title: str, widgets: List[Union[QWidget, QLayout, Tuple[QLabel,Union[QLineEdit, QSpinBox]]]]) ->QGroupBox:
    group = QGroupBox(title)
    group.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed)
    group.setStyleSheet(group_box_style)
    layout = QFormLayout(
        fieldGrowthPolicy=QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow,
        formAlignment=Qt.AlignmentFlag.AlignLeft,
        labelAlignment=Qt.AlignmentFlag.AlignLeft,
    )
    layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    group.setLayout(layout)
    for widget in widgets:
        if isinstance(widget, tuple) and len(widget) == 2 and \
           isinstance(widget[0], QLabel) and isinstance(widget[1], (QLineEdit, QSpinBox)):
            label, input = widget
            layout.addRow(label, input)
        elif isinstance(widget, (QWidget, QLayout)):
            layout.addRow(widget)
    group.adjustSize()
    group.setFixedHeight(group.sizeHint().height())
    return group

class DataBindWidget(QWidget):
    helper_binders: List[DataBinder] = None
    config_binders: List[DataBinder] = None

    def __init__(self, onShowSignal: SignalInstance, onSaveSignal: SignalInstance):
        super().__init__()
        self.helper_binders = list()
        self.config_binders = list()
        onShowSignal.connect(self.on_show)
        onSaveSignal.connect(self.on_save)
        pass

    def on_show(self, cfg: HelperConfig, config: CleanConfig) -> None:
        for binder in self.config_binders:
            binder.load_config.emit(config)
        for binder in self.helper_binders:
            binder.load_config.emit(cfg)
    @abstractmethod
    def on_save(self, cfg: HelperConfig, config: CleanConfig) -> None:
        pass