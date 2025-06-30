from abc import abstractmethod
from typing import List, Tuple, Union, Optional
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSpinBox,
    QWidget,
    QLayout,
    QGroupBox,
    QFormLayout,
)
from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt, SignalInstance
from gpustack_helper.databinder import DataBinder
from gpustack_helper.config import HelperConfig, GPUStackConfig


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


class FixedUpValidator(QIntValidator):
    def validate(self, input_str, pos):
        if input_str == "":
            return (QIntValidator.State.Intermediate, input_str, pos)
        try:
            value = int(input_str)
            if self.bottom() <= value <= self.top():
                return (QIntValidator.State.Acceptable, input_str, pos)
            else:
                return (QIntValidator.State.Invalid, input_str, pos)
        except ValueError:
            return (QIntValidator.State.Invalid, input_str, pos)


class NumericLineEdit(QLineEdit):
    validator: FixedUpValidator

    def __init__(self, parent=None, min_value: int = 0, max_value: int = 65535):
        super().__init__(parent)
        self.validator = FixedUpValidator(parent=self, bottom=min_value, top=max_value)
        self.setValidator(self.validator)
        self.setPlaceholderText("可选")

    def value(self) -> Optional[int]:
        text = self.text().strip()
        return int(text) if text else None

    def setValue(self, value: Optional[int]) -> None:
        if value is None:
            self.clear()
        elif isinstance(value, int) and value == 0:
            self.setText("")
        else:
            self.setText(str(value))


def fixed_titled_input(title: str) -> Tuple[QLabel, QLineEdit]:
    label = QLabel(title)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    input = QLineEdit()
    input.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return (label, input)


def fixed_titled_port_input(title: str) -> Tuple[QLabel, NumericLineEdit]:
    label = QLabel(title)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    input = NumericLineEdit()
    input.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return (label, input)


def wrap_layout(layout: QLayout) -> QWidget:
    rtn = QWidget()
    rtn.setLayout(layout)
    return rtn


def create_stand_box(
    title: str,
    widgets: List[Union[QWidget, QLayout, Tuple[QLabel, Union[QLineEdit, QSpinBox]]]],
) -> QGroupBox:
    group = QGroupBox(title)
    group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    group.setStyleSheet(group_box_style)
    layout = QFormLayout(
        fieldGrowthPolicy=QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow,
        formAlignment=Qt.AlignmentFlag.AlignLeft,
        labelAlignment=Qt.AlignmentFlag.AlignLeft,
    )
    layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    group.setLayout(layout)
    for widget in widgets:
        if (
            isinstance(widget, tuple)
            and len(widget) == 2
            and isinstance(widget[0], QLabel)
            and isinstance(widget[1], (QLineEdit, QSpinBox))
        ):
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

    def on_show(self, cfg: HelperConfig, config: GPUStackConfig) -> None:
        for binder in self.config_binders:
            binder.load_config.emit(config)
        for binder in self.helper_binders:
            binder.load_config.emit(cfg)

    @abstractmethod
    def on_save(self, cfg: HelperConfig, config: GPUStackConfig) -> None:
        pass
