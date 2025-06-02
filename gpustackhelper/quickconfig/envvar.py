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
    QTableWidget, 
    QTableWidgetItem,
    QPushButton,
    QComboBox,
    )
from PySide6.QtCore import Qt, Slot, SignalInstance
from typing import Tuple, List, Union, Dict, Any, BinaryIO
from gpustackhelper.config import HelperConfig, CleanConfig
from gpustackhelper.databinder import DataBinder
from gpustackhelper.quickconfig.common import (
    fixed_titled_input,
    fixed_titled_port_input,
    create_stand_box,
    DataBindWidget,
)

table_style = """
    QTableWidget {
        border: 1px solid #888888;
        font-size: 14px;
        gridline-color: #888888;
    }
"""

class EnvironmentVariablePage(DataBindWidget):
    envvar: QTableWidget = None
    def add_row(self):
        """添加新行，第一列为可自定义输入的下拉列表"""
        row_position = self.envvar.rowCount()
        self.envvar.insertRow(row_position)

        # 第一列为可编辑下拉列表
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(["HF_TOKEN", "HF_ENDPOINT", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"])  # 可根据需要自定义
        self.envvar.setCellWidget(row_position, 0, combo)

        # 第二列为可编辑文本
        item = QTableWidgetItem()
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.envvar.setItem(row_position, 1, item)

    def remove_row(self):
        """删除选中行"""
        current_row = self.envvar.currentRow()
        if current_row >= 0:
            self.envvar.removeRow(current_row)

    def on_save(self, cfg, config):
        editor = self.envvar.focusWidget()
        if editor and isinstance(editor, QLineEdit):
            index = self.envvar.currentIndex()
            row, col = index.row(), index.column()
            # 手动将 QLineEdit 的内容写回 QTableWidgetItem
            item = self.envvar.item(row, col)
            if item is not None:
                item.setText(editor.text())
            rows = self.envvar.rowCount()
            cols = self.envvar.columnCount()
        return super().on_save(cfg, config)
    def __init__(self, onShowSignal: SignalInstance, onSaveSignal: SignalInstance):
        super().__init__(onShowSignal, onSaveSignal)
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        table = QTableWidget()
        table.verticalHeader().setVisible(False)
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Name", "Value"])
        table.setStyleSheet(table_style)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setMinimumSectionSize(140)

        main_layout.addWidget(table)
        self.envvar = table

        add_button = QPushButton("+")
        add_button.setFixedSize(30, 30)
        add_button.clicked.connect(self.add_row)
        
        # 删除按钮
        remove_button = QPushButton("-")
        remove_button.setFixedSize(30, 30)
        remove_button.clicked.connect(self.remove_row)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.helper_binders.append(HelperConfig.bind('EnvironmentVariables', self.envvar))

