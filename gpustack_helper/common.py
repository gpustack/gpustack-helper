from PySide6.QtWidgets import QMenu, QMessageBox, QWidget
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication
import sys
def create_menu_action(name: str, menu: QMenu) -> QAction:
    """
    create a button under a menu 
    """
    action = QAction(name, menu)
    menu.addAction(action)
    return action

def show_warning(parent: QWidget, title: str, message: str):
    QMessageBox(QMessageBox.Icon.Critical, title, message, parent=parent, buttons=QMessageBox.StandardButton.Ok).exec()

