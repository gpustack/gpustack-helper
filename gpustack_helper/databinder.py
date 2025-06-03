from PySide6.QtCore import Qt, QObject, Signal, Slot
from PySide6.QtWidgets import QLineEdit, QAbstractButton, QSpinBox, QTableWidget, QComboBox, QTableWidgetItem
from typing import Callable, TypeVar, Type, Union, Dict, Any, Optional
from pydantic import BaseModel
from PySide6.QtGui import QAction, QIntValidator
from pydantic.fields import FieldInfo

supported_types = (str, int, bool, float, Dict[str, str])
T = TypeVar('T', str, int, bool, float, Dict[str, str])
T_BaseModel = TypeVar('T_BaseModel', bound=BaseModel)  # 定义在模块顶部

def _get_base_type(key_type: Type[T]) -> Type[T]:
    """Extract the base type from Optional[T] or return the type itself."""
    if hasattr(key_type, "__origin__") and key_type.__origin__ is Union:
        # Handle Optional[T] which is Union[T, None]
        for t in key_type.__args__:
            if t is not type(None):
                return t
    return key_type


def get_zero_value(t: Type[T]) -> T:
    if t is bool:
        return False  # bool() 返回 False，但你可能想要 False 而不是 bool()
    if t is Dict[str, str]:
        return dict()
    return t()

class DataBinder(QObject):
    load_config = Signal(BaseModel)
    _key: str = None
    _data_type: Type[T]
    _widget_getter: Callable[[], T] = None
    _widget_setter: Callable[[T], None] = None
    _ignore_zero_value: bool = False
    def __init__(self, 
                 key: str, 
                 type_class: Type[T_BaseModel], 
                 widget: Union[QAbstractButton, QSpinBox, QIntValidator, QLineEdit, QAction],
                 /,
                 ignore_zero_value = False,
                 ):
        super().__init__()
        self._ignore_zero_value = ignore_zero_value
        field = get_nested_field_info(type_class, key)
        
        base_type = _get_base_type(field.annotation)
        if base_type not in supported_types:
            raise NotImplementedError(f'type {base_type} is not supported, supported types are {supported_types}')
        self._data_type = base_type
        self._key = key
        if isinstance(widget, (QAction, QAbstractButton)):
            self._widget_getter = widget.isChecked
            self._widget_setter = widget.setChecked
        elif isinstance(widget, QLineEdit):
            self._widget_getter = widget.text
            self._widget_setter = widget.setText
        elif isinstance(widget,QSpinBox):
            self._widget_getter = widget.value
            self._widget_setter = widget.setValue
        elif isinstance(widget, QTableWidget):
            if widget.columnCount() != 2:
                raise ValueError("QTableWidget must have exactly 2 columns for key-value pairs")
            def _get_table_value() -> Dict[str, str]:
                """获取表格中所有行的键值对"""
                result = {}
                for row in range(widget.rowCount()):
                    key_item = widget.cellWidget(row, 0)  # 假设第一列是键
                    # only supports QComboBox for now
                    if isinstance(key_item, QComboBox):
                        key = key_item.currentText()
                    else:
                        continue
                    value_item = widget.item(row, 1)
                    if value_item and value_item.text() != '':
                        result[key] = value_item.text()
                return result
            def _set_table_value(value: Dict[str, str]) -> None:
                widget.setRowCount(0)
                for k, v in value.items():
                    row_position = widget.rowCount()
                    widget.insertRow(row_position)
                    # 第一列为可编辑下拉列表
                    combo = QComboBox()
                    combo.setEditable(True)
                    combo.addItem(k)
                    widget.setCellWidget(row_position, 0, combo)
                    # 第二列为可编辑文本
                    item = QTableWidgetItem(v)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                    widget.setItem(row_position, 1, item)
            self._widget_getter = _get_table_value
            self._widget_setter = _set_table_value
        else: 
            raise ValueError(f"Widget {widget.__class__.__name__} has no text or isChecked method")
        self.load_config.connect(self._load_to_widget)

    def ignore_zero_value(self, ignore: bool = True):
        self._ignore_zero_value = ignore

    @Slot(BaseModel)
    def _load_to_widget(self, cfg: BaseModel) -> None:
        if self._widget_setter is None:
            return
        attr = get_nested_field_value(cfg, self._key, None)
        value = get_zero_value(self._data_type) if attr is None else attr
        self._widget_setter(value)

    def update_config(self, content: Dict[str, Any]) -> None:
        value = self._widget_getter()
        if value == get_zero_value(self._data_type) and self._ignore_zero_value:
            value = None
        split_keys = self._key.split('.')
        current = content
        for part in split_keys[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        # 最后一个部分是实际的键
        current[split_keys[-1]] = value


def get_nested_field_info(
    model: Type[BaseModel], 
    field_path: str
) -> Optional[FieldInfo]:
    """
    递归获取嵌套模型的字段信息
    
    :param model: 根模型类
    :param field_path: 点分隔的字段路径，如 'b.c'
    :return: 字段信息对象或None(如果字段不存在)
    """
    current = model
    parts = field_path.split('.')
    
    for part in parts:
        if not hasattr(current, 'model_fields'):
            return None
            
        fields = current.model_fields
        if part not in fields:
            return None
            
        field_info = fields[part]
        current = field_info.annotation
        
        # 如果是嵌套模型且不是最后一个部分，继续深入
        if isinstance(current, type) and issubclass(current, BaseModel) and part != parts[-1]:
            continue
            
        return field_info if part == parts[-1] else None

    return None  # 如果没有找到字段，返回None


def get_nested_field_value(
    model: BaseModel,
    field_path: str,
    default: Any = None
) -> Any:
    """
    获取嵌套模型字段的实际值
    
    Args:
        model: Pydantic 模型实例
        field_path: 点分隔的字段路径 (如 'user.address.street')
        default: 如果字段不存在时返回的默认值
    
    Returns:
        字段值或默认值
    """
    try:
        parts = field_path.split('.')
        current = model
        
        for part in parts:
            if not hasattr(current, part):
                return default
            current = getattr(current, part)
            
            # 如果遇到None值，提前返回
            if current is None:
                return default
                
        return current
    except Exception:
        return default

def set_nested_data(
    model: BaseModel,
    data: Dict[str, Any],
) -> bool:
    """
    递归地将 dict 的内容更新到嵌套 Pydantic BaseModel 实例
    
    Args:
        model: Pydantic 模型实例
        data: dict 数据
    
    Returns:
        bool: 是否全部成功
    """
    try:
        for key, value in data.items():
            if not hasattr(model, key):
                continue  # 跳过不存在的字段
            attr = getattr(model, key)
            # 如果 value 是 dict 且 attr 是 BaseModel，递归
            if isinstance(value, dict) and isinstance(attr, BaseModel):
                set_nested_data(attr, value)
            else:
                setattr(model, key, value)
        return True
    except Exception:
        return False