from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QComboBox,
)
from PySide6.QtCore import Qt, SignalInstance
from gpustack_helper.config import HelperConfig
from gpustack_helper.quickconfig.common import (
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
    remove_button: QPushButton = None
    add_button: QPushButton = None

    def add_row(self):
        row_position = self.envvar.rowCount()
        self.envvar.insertRow(row_position)

        # First column is an editable dropdown list
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(
            ["HF_TOKEN", "HF_ENDPOINT", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"]
        )  # Customize as needed
        self.envvar.setCellWidget(row_position, 0, combo)

        # Second column is an editable text
        item = QTableWidgetItem()
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.envvar.setItem(row_position, 1, item)

    def remove_row(self):
        current_row = self.envvar.currentRow()
        if hasattr(self, "_home_row") and current_row == self._home_row:
            return  # Prevent deleting HOME row
        if current_row >= 0:
            self.envvar.removeRow(current_row)

    def on_save(self, cfg, config):
        editor = self.envvar.focusWidget()
        if editor and isinstance(editor, QLineEdit):
            index = self.envvar.currentIndex()
            row, col = index.row(), index.column()
            # Manually write QLineEdit content back to QTableWidgetItem
            item = self.envvar.item(row, col)
            if item is not None:
                item.setText(editor.text())
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

        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(30, 30)
        self.add_button.clicked.connect(self.add_row)

        # Delete button
        self.remove_button = QPushButton("-")
        self.remove_button.setFixedSize(30, 30)
        self.remove_button.clicked.connect(self.remove_row)
        self.remove_button.setEnabled(False)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.helper_binders.append(
            HelperConfig.bind("EnvironmentVariables", self.envvar)
        )

        self.envvar.currentCellChanged.connect(self.on_table_selection_changed)
        self.envvar.selectionModel().selectionChanged.connect(
            self.on_table_selection_changed_selection
        )

    def on_show(self, cfg, config):
        super().on_show(cfg, config)
        for row in range(self.envvar.rowCount()):
            key_widget = self.envvar.cellWidget(row, 0)
            if isinstance(key_widget, QComboBox) and key_widget.currentText() == "HOME":
                # Set Value column to not editable
                item = self.envvar.item(row, 1)
                if item:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                # Set Name column to not editable
                key_widget.setEditable(False)
                self.envvar.setRowHidden(row, True)
                # Record HOME row index
                self._home_row = row
                break
        else:
            self._home_row = None

    def on_table_selection_changed(
        self, currentRow, currentColumn, previousRow, previousColumn
    ):
        # 只有选中有效行时才可用
        self.remove_button.setEnabled(currentRow >= 0)

    def on_table_selection_changed_selection(self, selected, deselected):
        # 没有选中任何行时禁用
        indexes = self.envvar.selectedIndexes()
        self.remove_button.setEnabled(bool(indexes))
