from PySide6.QtCore import Qt, QObject, Signal, Slot
from PySide6.QtWidgets import (
    QLineEdit,
    QAbstractButton,
    QSpinBox,
    QTableWidget,
    QComboBox,
    QTableWidgetItem,
)
from typing import Callable, TypeVar, Type, Union, Dict, Any, Optional
from pydantic import BaseModel
from PySide6.QtGui import QAction, QIntValidator
from pydantic.fields import FieldInfo

supported_types = (str, int, bool, float, Dict[str, str])
T = TypeVar("T", str, int, bool, float, Dict[str, str])
T_BaseModel = TypeVar("T_BaseModel", bound=BaseModel)  # 定义在模块顶部


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

    def __init__(
        self,
        key: str,
        type_class: Type[T_BaseModel],
        widget: Union[
            QAbstractButton, QSpinBox, QIntValidator, QLineEdit, QAction, QTableWidget
        ],
        /,
        ignore_zero_value=False,
    ):
        super().__init__()
        self._ignore_zero_value = ignore_zero_value
        field = get_nested_field_info(type_class, key)

        base_type = _get_base_type(field.annotation)
        if base_type not in supported_types:
            raise NotImplementedError(
                f"type {base_type} is not supported, supported types are {supported_types}"
            )
        self._data_type = base_type
        self._key = key
        self._assign_widget_handlers(widget)
        self.load_config.connect(self._load_to_widget)

    def _assign_widget_handlers(self, widget):
        if isinstance(widget, (QAction, QAbstractButton)):
            self._widget_getter = widget.isChecked
            self._widget_setter = widget.setChecked
        elif (
            isinstance(widget, QLineEdit)
            and hasattr(widget, "value")
            and hasattr(widget, "setValue")
        ):
            # number widget like QDoubleSpinBox or QSpinBox
            self._widget_getter = widget.value
            self._widget_setter = widget.setValue
        elif isinstance(widget, QLineEdit):
            self._widget_getter = widget.text
            self._widget_setter = widget.setText
        elif isinstance(widget, QSpinBox):
            self._widget_getter = widget.value
            self._widget_setter = widget.setValue
        elif isinstance(widget, QTableWidget):
            self._widget_getter, self._widget_setter = self._table_widget_handlers(
                widget
            )
        else:
            raise ValueError(
                f"Widget {widget.__class__.__name__} has no text or isChecked method"
            )

    def _table_widget_handlers(self, widget):
        if widget.columnCount() != 2:
            raise ValueError(
                "QTableWidget must have exactly 2 columns for key-value pairs"
            )

        def _get_table_value() -> Dict[str, str]:
            result = {}
            for row in range(widget.rowCount()):
                key_item = widget.cellWidget(row, 0)  # Assume first column is key
                if isinstance(key_item, QComboBox):
                    key = key_item.currentText()
                else:
                    continue
                value_item = widget.item(row, 1)
                if value_item and value_item.text() != "":
                    result[key] = value_item.text()
            return result

        def _set_table_value(value: Dict[str, str]) -> None:
            widget.setRowCount(0)
            for k, v in value.items():
                row_position = widget.rowCount()
                widget.insertRow(row_position)
                combo = QComboBox()
                combo.setEditable(True)
                combo.addItem(k)
                combo.setToolTip(k)
                widget.setCellWidget(row_position, 0, combo)
                item = QTableWidgetItem(v)
                item.setToolTip(v)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                widget.setItem(row_position, 1, item)

        return _get_table_value, _set_table_value

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
        split_keys = self._key.split(".")
        current = content
        for part in split_keys[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        # 最后一个部分是实际的键
        current[split_keys[-1]] = value


def get_nested_field_info(
    model: Type[BaseModel], field_path: str
) -> Optional[FieldInfo]:
    """
    Recursively get the field info of a nested model

    :param model: The root model class
    :param field_path: Dot-separated field path, e.g. 'b.c'
    :return: Field info object or None (if the field does not exist)
    """
    current = model
    parts = field_path.split(".")

    for part in parts:
        if not hasattr(current, "model_fields"):
            return None

        fields = current.model_fields
        if part not in fields:
            return None

        field_info = fields[part]
        current = field_info.annotation

        # 如果是嵌套模型且不是最后一个部分，继续深入
        if (
            isinstance(current, type)
            and issubclass(current, BaseModel)
            and part != parts[-1]
        ):
            continue

        return field_info if part == parts[-1] else None

    return None  # 如果没有找到字段，返回None


def get_nested_field_value(
    model: BaseModel, field_path: str, default: Any = None
) -> Any:
    """
    Get the actual value of a nested model field

    Args:
        model: Pydantic model instance
        field_path: Dot-separated field path (e.g. 'user.address.street')
        default: The default value to return if the field does not exist

    Returns:
        The field value or the default value
    """
    try:
        parts = field_path.split(".")
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


def reset_model_to_default(model: BaseModel):
    # Pydantic v2
    for name, field in model.__class__.model_fields.items():
        if field.default_factory is not None:
            value = field.default_factory()
        elif hasattr(field, 'default'):
            value = field.default  # 允许 default 为 None
        else:
            continue  # 没有 default 也没有 default_factory
        setattr(model, name, value)


def set_nested_data(
    model: BaseModel, data: Dict[str, Any], reset_default: bool = False
) -> bool:
    """
    Recursively update the contents of a dict into a nested Pydantic BaseModel instance

    Args:
        model: Pydantic model instance
        data: dict data

    Returns:
        bool: Whether all updates succeeded
    """
    try:
        if reset_default:
            reset_model_to_default(model)
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
