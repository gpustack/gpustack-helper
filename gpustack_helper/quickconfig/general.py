from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QButtonGroup,
    QRadioButton,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QLayout,
)
from PySide6.QtCore import Qt, Slot, SignalInstance
from typing import Tuple, List, Union
from gpustack_helper.config import HelperConfig, CleanConfig
from gpustack_helper.quickconfig.common import (
    fixed_titled_input,
    fixed_titled_port_input,
    create_stand_box,
    DataBindWidget,
)


class GeneralConfigPage(DataBindWidget):
    group: QButtonGroup = None
    _worker_index: int = None
    server_url: Tuple[QLabel, QLineEdit] = None
    token: Tuple[QLabel, QLineEdit] = None
    port: Tuple[QLabel, QSpinBox] = None

    @Slot(QRadioButton, bool)
    def on_button_toggled(self, button: QRadioButton, checked: bool):
        if not checked:
            return
        id = self.group.id(button)
        for widget in self.server_url:
            widget.setEnabled(id == self._worker_index)

    def _get_role_group(self, selection_layout: QLayout) -> QGroupBox:
        rows: List[Union[QWidget, QLayout, Tuple[QLabel, QLineEdit]]] = list()
        rows.append(selection_layout)
        for _, (attr, title) in enumerate(
            (("server_url", "Server URL:"), ("token", "Token:")), start=1
        ):
            label, input = fixed_titled_input(title)
            self.config_binders.append(
                CleanConfig.bind(attr, input, ignore_zero_value=True)
            )
            setattr(self, attr, (label, input))
            rows.append((label, input))
        return create_stand_box("服务角色", rows)

    def _create_port_group(self) -> QGroupBox:
        rows: List[Union[QWidget, QLayout, Tuple[QLabel, QSpinBox]]] = list()
        for _, (attr, title) in enumerate((("port", "服务端口:"),)):
            label, input = fixed_titled_port_input(title)
            self.config_binders.append(
                CleanConfig.bind(attr, input, ignore_zero_value=True)
            )
            setattr(self, attr, (label, input))
            rows.append((label, input))
        return create_stand_box("端口配置", rows)

    def on_show(self, cfg, config):
        super().on_show(cfg, config)
        if config.server_url is not None and config.server_url != "":
            self.group.button(self._worker_index).setChecked(True)

    def on_save(self, cfg, config):
        if self.group.checkedId() != self._worker_index:
            self.server_url[1].setText("")

    def __init__(
        self,
        cfg: HelperConfig,
        onShowSignal: SignalInstance,
        onSaveSignal: SignalInstance,
    ):
        super().__init__(onShowSignal, onSaveSignal)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        selection_group, selection_layout = self._get_role_selection()
        self.group = selection_group
        # 连接信号
        self.group.buttonToggled.connect(self.on_button_toggled)

        layout.addWidget(self._get_role_group(selection_layout))
        layout.addWidget(self._create_port_group())
        self.setLayout(layout)

        self.group.button(0).setChecked(True)

    def _get_role_selection(self) -> Tuple[QButtonGroup, QHBoxLayout]:
        server_button_index = -1
        group = QButtonGroup()
        kvgroup = (
            ("both", "All"),
            ("worker", "Worker"),
            ("server", "Server Only"),
        )
        radio_layout = QHBoxLayout()
        for index, (key, value) in enumerate(kvgroup):
            button = QRadioButton(value)
            self.__setattr__(key, button)
            group.addButton(button, index)
            radio_layout.addWidget(button)
            if key == "worker":
                self._worker_index = index
            if key == "server":
                server_button_index = index
        server_button = group.button(server_button_index)
        self.config_binders.append(CleanConfig.bind("disable_worker", server_button))
        return group, radio_layout
