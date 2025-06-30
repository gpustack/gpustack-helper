import os
import logging
import sys
from pydantic import BaseModel, Field, PrivateAttr
from typing import List, Dict, Optional, Callable, TypeVar, Tuple
from PySide6.QtWidgets import QWidget
from gpustack.config import Config
from gpustack_helper.defaults import (
    log_file_path,
    data_dir as default_data_dir,
    global_data_dir,
    gpustack_binary_path,
    gpustack_config_name,
    runtime_plist_path,
)
from gpustack_helper.config.backends import ModelBackend, FileConfigModel, PlistEncoder
from gpustack_helper.databinder import DataBinder

logger = logging.getLogger(__name__)

ModelBackend_Type = TypeVar("ModelBackend_Type", bound="ModelBackend")


class HelperConfig(BaseModel):
    _backend: Optional[ModelBackend] = PrivateAttr(default=None)
    _data_dir: Optional[str] = PrivateAttr(default=None)
    _binary_path: Optional[str] = PrivateAttr(
        default=None,
    )
    _config_path: Optional[str] = PrivateAttr(
        default=None,
    )
    _gpustack_config_path: Optional[str] = PrivateAttr(
        default=None,
    )
    _debug: Optional[bool] = PrivateAttr(default=False)
    Label: str = Field(default="ai.gpustack", description="服务名称")
    ProgramArguments: List[str] = Field(
        default_factory=list,
        description="启动服务时的参数列表",
    )
    KeepAlive: bool = Field(default=True, description="服务是否保持运行")
    EnableTransactions: bool = Field(default=True, description="是否启用事务")
    StandardOutPath: Optional[str] = Field(
        default=log_file_path, description="服务的可执行文件路径"
    )
    StandardErrorPath: Optional[str] = Field(
        default=log_file_path, description="服务的错误输出路径"
    )
    RunAtLoad: Optional[bool] = Field(
        default=False, description="是否在启动时自动启动服务"
    )
    EnvironmentVariables: Dict[str, str] = Field(
        default_factory=dict, description="环境变量配置"
    )

    @property
    def data_dir(self) -> Optional[str]:
        return self._data_dir

    @property
    def config_path(self) -> Optional[str]:
        return self._config_path

    @property
    def default_program_arguments(self) -> List[str]:
        return [
            self._binary_path,
            "start",
            f"--config-file={self._gpustack_config_path}",
            f"--data-dir={self._data_dir}",
        ]

    def _ensure_environment_home(self) -> None:
        if sys.platform != "darwin":
            return
        if self.EnvironmentVariables.get("HOME", None) is None:
            self.EnvironmentVariables["HOME"] = os.path.join(self._data_dir, "root")

    def update_with_lock(self, **kwargs):
        """
        Update the configuration with the provided keyword arguments.
        This method is thread-safe and ensures that the configuration is updated
        atomically.
        """
        self._backend.update_with_lock(**kwargs)

    def reload(self):
        """
        Reload the configuration from the file.
        """
        if self._backend is not None:
            self._backend.reload()

    def save(self):
        """
        Save the configuration to the specified path.
        """
        self._ensure_environment_home()
        if self._backend is not None:
            self._backend.save()

    def __init__(
        self,
        /,
        backend: Callable[[BaseModel], ModelBackend_Type] = None,
        data_dir: Optional[str] = None,
        binary_path: Optional[str] = None,
        config_path: Optional[str] = None,
        debug: Optional[bool] = None,
        gpustack_config_path: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._data_dir = data_dir or global_data_dir
        self._binary_path = binary_path or gpustack_binary_path
        self._config_path = config_path
        self._debug = debug if debug is not None else False
        self._gpustack_config_path = gpustack_config_path or os.path.join(
            self._data_dir, gpustack_config_name
        )
        if backend is not None:
            self._backend = backend(self)
        if len(self.ProgramArguments) == 0 and self._binary_path and self._data_dir:
            self.ProgramArguments = self.default_program_arguments
        if len(kwargs) == 0:
            self.reload()
        self._ensure_environment_home()

    @classmethod
    def bind(
        cls, key: str, widget: QWidget, /, ignore_zero_value: bool = False
    ) -> DataBinder:
        return DataBinder(key, cls, widget, ignore_zero_value=ignore_zero_value)


class GPUStackConfig(Config):
    _backend: Optional[ModelBackend] = PrivateAttr(default=None)
    _confg_path: str = PrivateAttr(default=None)
    data_dir: str = Field(
        default=default_data_dir, exclude=True, description="数据目录"
    )

    @property
    def config_path(self) -> str:
        return self._confg_path

    def update_with_lock(self, **kwargs):
        """
        Update the configuration with the provided keyword arguments.
        This method is thread-safe and ensures that the configuration is updated
        atomically.
        """
        self._backend.update_with_lock(**kwargs)

    def reload(self):
        """
        Reload the configuration from the file.
        """
        if self._backend is not None:
            self._backend.reload()

    def save(self):
        """
        Save the configuration to the specified path.
        """
        if self._backend is not None:
            self._backend.save()

    def __init__(
        self,
        gpustack_config_path: str,
        data_dir: Optional[str] = None,
        backend: Callable[[BaseModel], ModelBackend_Type] = None,
        **kwargs,
    ):
        super(Config, self).__init__(**kwargs)
        self._confg_path = gpustack_config_path
        if backend is not None:
            self._backend = backend(self)
        if data_dir is not None:
            self.data_dir = data_dir
        if len(kwargs) == 0:
            self.reload()

    @property
    def token_path(self) -> str:
        return os.path.join(self.data_dir, "token")

    def token_exists(self) -> bool:
        return self.token is not None or os.path.exists(self.token_path)

    def get_token(self) -> Optional[str]:
        if not self.token_exists():
            return None
        if self.token is not None:
            return self.token
        with open(self.active_token_path, "r") as f:
            token = f.read().strip()
            if token:
                return token
        return None

    def get_port(self) -> Tuple[int, bool]:
        is_tls = self.ssl_certfile is not None and self.ssl_keyfile is not None
        port = self.port
        if port is None or port == 0:
            port = 443 if is_tls else 80
        return port, is_tls

    @classmethod
    def bind(
        cls, key: str, widget: QWidget, /, ignore_zero_value: bool = False
    ) -> DataBinder:
        return DataBinder(key, cls, widget, ignore_zero_value=ignore_zero_value)


def legacy_helper_config() -> Optional[HelperConfig]:
    if not os.path.exists(runtime_plist_path):
        return None
    if os.path.islink(runtime_plist_path):
        return None

    return HelperConfig(
        backend=lambda x: FileConfigModel(
            x, filepath=runtime_plist_path, encoder=PlistEncoder
        ),
    )


if __name__ == "__main__":
    model = HelperConfig()
    print(model.model_dump())  # Should not include _hidden field
    test_data_dir = {}
    test_data_dir.update(data_dir="/tmp/gpustack_test")
    gpustack_config = GPUStackConfig(**test_data_dir)
    print(
        gpustack_config.model_dump(exclude_defaults=True)
    )  # Should not include _hidden field
