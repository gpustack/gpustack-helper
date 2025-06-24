import yaml
import os
import logging
import threading
import plistlib
import sys
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, BinaryIO
from gpustack.config import Config
from PySide6.QtWidgets import QWidget
from gpustack_helper.databinder import DataBinder, set_nested_data

from gpustack_helper.defaults import (
    log_file_path,
    data_dir as default_data_dir,
    global_data_dir,
    gpustack_config_name,
    gpustack_binary_path,
)

logger = logging.getLogger(__name__)
helper_config_file_name = "ai.gpustack.plist"


class _FileConfigModel(BaseModel):
    _lock: threading.Lock
    _filepath: str = None

    @property
    def filepath(self) -> str:
        return self._filepath

    def __init__(self, filepath: str, **kwargs):
        if isinstance(self, Config):
            super(Config, self).__init__(**kwargs)
        else:
            super().__init__(**kwargs)
        self._filepath = filepath
        self._lock = threading.Lock()
        self._reload()

    def update_with_lock(self, **kwargs):
        with self._lock:
            self._reload()
            set_nested_data(self, kwargs)
            self._save()

    def encode_to_data(self) -> bytes:
        data = self.model_dump(exclude_defaults=True)
        return yaml.safe_dump(data, stream=None).encode("utf-8")

    def decode_from_data(self, f: BinaryIO) -> Dict[str, Any]:
        data = f.read().decode("utf-8")
        return yaml.safe_load(data)

    def _reload(self):
        """
        Reload the configuration from the file.
        """
        try:
            with open(self.filepath, "rb") as f:
                content = self.decode_from_data(f)
                set_nested_data(self, content)
        except FileNotFoundError:
            logger.warning(f"Configuration file not found: {self.filepath}")
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")

    def _save(self):
        """
        Save the configuration to the specified path.
        """
        try:
            config_dir = os.path.dirname(self.filepath)
            os.makedirs(config_dir, exist_ok=True)
            with open(self.filepath, "wb") as f:
                f.write(self.encode_to_data())
        except Exception as e:
            logger.error(f"Failed to create config directory {config_dir}: {e}")
            return


class CleanConfig(_FileConfigModel, Config):
    port: Optional[int] = Field(default=80, description="服务端口")
    _active_dir: str

    def __init__(self, active_dir: str, filepath: str, **kwargs):
        """
        Initialize the configuration with the given file path.
        """
        super().__init__(filepath=filepath, **kwargs)
        self._active_dir = active_dir
        if len(kwargs) == 0 and os.path.exists(filepath):
            self._reload()

    @property
    def active_config_path(self) -> str:
        return os.path.join(self._active_dir, os.path.basename(self.filepath))

    @classmethod
    def bind(
        cls, key: str, widget: QWidget, /, ignore_zero_value: bool = False
    ) -> DataBinder:
        return DataBinder(key, cls, widget, ignore_zero_value=ignore_zero_value)

    def load_active_config(self) -> "CleanConfig":
        return CleanConfig(
            active_dir=self._active_dir, filepath=self.active_config_path
        )


class _HelperConfig(BaseModel):
    Label: str = Field(default="ai.gpustack", description="服务名称")
    ProgramArguments: List[str] = Field(
        default_factory=list, description="启动服务时的参数列表"
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


class HelperConfig(_FileConfigModel, _HelperConfig):
    _override_data_dir: Optional[str] = None
    _override_binary_path: Optional[str] = None
    _debug: bool = None

    def encode_to_data(self) -> bytes:
        return plistlib.dumps(self.model_dump(by_alias=True, exclude_none=True))

    def decode_from_data(self, f: BinaryIO) -> Dict[str, Any]:
        data = plistlib.load(f)
        # 忽略 EnvironmentVariables 下 key 为 'HOME' 的键值对
        env = data.get('EnvironmentVariables')
        if sys.platform == 'darwin':
            if isinstance(env, dict) and 'HOME' in env:
                env.pop('HOME')
        return data

    @classmethod
    def bind(
        cls, key: str, widget: QWidget, /, ignore_zero_value: bool = False
    ) -> DataBinder:
        return DataBinder(key, cls, widget, ignore_zero_value=ignore_zero_value)

    @property
    def user_data_dir(self) -> str:
        return _default_path(default_data_dir, self._override_data_dir)

    @property
    def active_data_dir(self) -> str:
        return _default_path(global_data_dir, self._override_data_dir)

    @property
    def active_config_path(self) -> str:
        """
        if _override_data_dir is set, the active_config_path will have prefix 'active.'. Otherwise it will have the same basename with filepath.
        """
        if self._override_data_dir is not None:
            return os.path.join(
                self.active_data_dir, f"active.{os.path.basename(self.filepath)}"
            )
        return os.path.join(self.active_data_dir, os.path.basename(self.filepath))

    @property
    def user_gpustack_config(self) -> CleanConfig:
        return CleanConfig(
            self.active_data_dir, os.path.join(self.user_data_dir, gpustack_config_name)
        )

    @property
    def gpustack_binary_path(self):
        return _default_path(gpustack_binary_path, self._override_binary_path)

    @property
    def debug(self) -> bool:
        return self._debug

    def __init__(
        self,
        /,
        filepath: Optional[str] = None,
        data_dir: Optional[str] = None,
        binary_path: Optional[str] = None,
        debug: Optional[bool] = False,
        **kwargs,
    ):
        if filepath is None:
            filepath = os.path.join(
                _default_path(default_data_dir, data_dir), helper_config_file_name
            )
        super().__init__(filepath, **kwargs)
        self._override_data_dir = data_dir
        self._override_binary_path = binary_path
        self._debug = debug
        if self.gpustack_binary_path == "":
            raise ValueError(
                "GPUStack binary path is not set. Please set it via commandline flag."
            )
        if len(kwargs) == 0 and os.path.exists(filepath):
            self._reload()

    def update_with_lock(self, **kwargs):
        kwargs['ProgramArguments'] = self.program_args_defaults()
        if 'EnvironmentVariables' not in kwargs:
            kwargs['EnvironmentVariables'] = {}
        if 'HOME' not in kwargs['EnvironmentVariables']:
            kwargs['EnvironmentVariables']['HOME'] = os.path.join(
                self.active_data_dir, 'root'
            )
        super().update_with_lock(**kwargs)

    def program_args_defaults(self) -> List[str]:
        """
        Returns the default program arguments for the GPUStack service.
        """
        gpustack_config = self.user_gpustack_config
        return [
            self.gpustack_binary_path,
            "start",
            f"--config-file={os.path.abspath(gpustack_config.active_config_path)}",
            f"--data-dir={os.path.abspath(self.active_data_dir)}",
        ]

    def ensure_data_dir(self) -> None:
        if not os.path.exists(self.user_data_dir):
            try:
                os.makedirs(self.user_data_dir, exist_ok=True)
            except Exception as e:
                logger.error(
                    f"Failed to create user data directory {self.user_data_dir}: {e}"
                )
                raise
        if self.user_data_dir != self.active_data_dir and sys.platform == 'darwin':
            link_target = os.path.join(self.user_data_dir, "data-dir")
            if os.path.lexists(link_target):
                if os.path.islink(link_target):
                    if os.readlink(link_target) != self.active_data_dir:
                        os.unlink(link_target)
                else:
                    logger.warning(
                        f"{link_target} exists and is not a symlink, skip creating symlink to avoid data loss."
                    )
                    return
            if not os.path.exists(link_target):
                os.symlink(self.active_data_dir, link_target, target_is_directory=True)


def _default_path(default: str, override: Optional[str] = None) -> str:
    return override if override is not None else default
