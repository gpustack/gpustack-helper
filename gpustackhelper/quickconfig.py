import sys
from typing import Tuple, List, Union, Dict, Any
from PySide6.QtWidgets import (
    QDialog, 
    QVBoxLayout, 
    QHBoxLayout,
    QLayout,
    QLabel, 
    QLineEdit, 
    QDialogButtonBox,
    QRadioButton,
    QButtonGroup,
    QWidget,
    QStackedWidget,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QFormLayout,
    QSizePolicy,
    QSpinBox
)

from PySide6.QtGui import QIcon
from PySide6.QtCore import Slot, Qt
from gpustackhelper.config import HelperConfig, CleanConfig
from gpustackhelper.databinder import DataBinder

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

def create_list(stacked_widget: QStackedWidget, pages: Tuple[Tuple[str, QWidget],...]) -> QListWidget:
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
    # 应该只保存需要做配置映射的控件
    _worker_index: int = -1
    cfg: HelperConfig = None
    group: QButtonGroup = None
    server_url: Tuple[QLabel, QLineEdit] = None
    token: Tuple[QLabel, QLineEdit] = None
    port: Tuple[QLabel, QSpinBox] = None
    config_binders: List[DataBinder] = list()
    helper_binders: List[DataBinder] = list()
    def __init__(self, cfg: HelperConfig = None, *args):
        self.cfg = cfg
        super().__init__(*args)
        self.setWindowTitle("快速配置")
        if sys.platform != 'darwin':
            self.setWindowIcon(QIcon.fromTheme(QIcon.ThemeIcon.DocumentPageSetup))
        self.setFixedSize(600, 400)
        self.stacked_widget = QStackedWidget()
        list_widget = create_list(self.stacked_widget, (
            ("通用", self.create_general_page()),
            ("环境变量", self.create_environment_variable_page()),
        ))
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

    @Slot(QRadioButton,bool)
    def on_button_toggled(self, button: QRadioButton, checked: bool):
        if not checked:
            return
        id = self.group.id(button)
        for widget in self.server_url:
            widget.setEnabled(id == self._worker_index)
    
    def create_environment_variable_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.get_env_group())
        page.setLayout(layout)
        return page

    def create_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        selection_group, selection_layout = self.get_role_selection()
        self.group = selection_group
        # 连接信号
        self.group.buttonToggled.connect(self.on_button_toggled)

        layout.addWidget(self.get_role_group(selection_layout))
        layout.addWidget(self.create_port_group())
        page.setLayout(layout)

        self.group.button(0).setChecked(True)
        return page

    def get_role_selection(self) ->Tuple[QButtonGroup, QHBoxLayout]:
        server_button_index = -1
        group = QButtonGroup()
        kvgroup = (
            ('both','All' ),
            ('worker', 'Worker'),
            ('server', 'Server Only'),
            )
        radio_layout = QHBoxLayout()
        for index, (key, value) in enumerate(kvgroup):
            button = QRadioButton(value)
            self.__setattr__(key, button)
            group.addButton(button, index)
            radio_layout.addWidget(button)
            if key == 'worker':
                self._worker_index = index
            if key == 'server':
                server_button_index = index
        server_button = group.button(server_button_index)
        self.config_binders.append(CleanConfig.bind('disable_worker', server_button))
        return group, radio_layout

    def get_role_group(self, selection_layout: QLayout) ->QGroupBox:
        rows: List[Union[QWidget, QLayout, Tuple[QLabel,QLineEdit]]] = list()
        rows.append(selection_layout)
        for index, (attr, title) in enumerate((('server_url', 'Server URL:'), ('token','Token:')), start=1):
            label, input = fixed_titled_input(title)
            self.config_binders.append(CleanConfig.bind(attr, input, ignore_zero=True))
            setattr(self, attr, (label, input))
            rows.append((label,input))
        return create_stand_box('服务角色',rows)
    def create_port_group(self) -> QGroupBox:
        rows: List[Union[QWidget, QLayout, Tuple[QLabel,QSpinBox]]] = list()
        for index, (attr, title) in enumerate((('port', '服务端口:'),)):
            label, input = fixed_titled_port_input(title)
            self.config_binders.append(CleanConfig.bind(attr, input, ignore_zero=True))
            setattr(self, attr, (label, input))
            rows.append((label,input))
        return create_stand_box('端口配置', rows)

    def get_env_group(self) -> QGroupBox:
        rows: List[Tuple[QLabel,QLineEdit]] = list()
        for index,(config_name, title) in enumerate((('EnvironmentVariables.HF_ENDPOINT', 'HF_ENDPOINT'), ('EnvironmentVariables.HF_TOKEN', 'HF_TOKEN'))):
            label, input = fixed_titled_input(title)
            self.helper_binders.append(HelperConfig.bind(config_name, input, ignore_zero=True))
            rows.append((label, input))
        group = create_stand_box("环境变量", rows)
        return group

    def config_confirm(self) -> QWidget:
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        return buttons

    def showEvent(self, event):
        self.cfg._reload()
        config = self.cfg.user_gpustack_config
        super().showEvent(event)
        # 读取 CleanConfig 配置并设置到 QLineEdit
        for binder in self.config_binders:
            binder.load_config.emit(config)
        for binder in self.helper_binders:
            binder.load_config.emit(self.cfg)
        # 额外处理 server_url 和 token 的显示
        if config.server_url is not None and config.server_url != '':
            self.server_url[1].setText(config.server_url)
            self.group.button(self._worker_index).setChecked(True)

    def accept(self):
        # 处理ButtonGroup的状态，当选择不是 Server + Worker 时清空输入
        if self.group.checkedId()!= self._worker_index:
            self.server_url[1].setText('')

        # 更新Helper配置
        data: Dict[str, any] = {}
        for binder in self.helper_binders:
            binder.update_config(data)
        self.cfg.update_with_lock(**data)

        data: Dict[str, Any] = {}
        for binder in self.config_binders:
            binder.update_config(data)
        config = self.cfg.user_gpustack_config
        config.update_with_lock(**data)

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