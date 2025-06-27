import yaml
import os
import logging
import threading
import plistlib
import sys
from types import SimpleNamespace
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, BinaryIO, Tuple
from PySide6.QtWidgets import QWidget

from gpustack_helper.databinder import DataBinder, set_nested_data
from gpustack.config import Config
from gpustack.cmd.start import (
    set_common_options,
    set_server_options,
    set_worker_options,
    load_config_from_yaml,
)

from gpustack_helper.defaults import (
    log_file_path,
    data_dir as default_data_dir,
    global_data_dir,
    gpustack_config_name,
    gpustack_binary_path,
)


logger = logging.getLogger(__name__)
helper_config_file_name = "ai.gpustack.plist"
# TODO remove platform related logic
plist_path = f"/Library/LaunchDaemons/{helper_config_file_name}"


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
            logger.debug(
                f"Configuration file not found, skipping loading: {self.filepath}"
            )
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
    def active_data_dir(self) -> str:
        return self._active_dir

    @property
    def active_config_path(self) -> str:
        return os.path.join(self._active_dir, os.path.basename(self.filepath))

    @property
    def active_token_path(self) -> str:
        """
        Returns the path to the token file.
        """
        return os.path.join(self._active_dir, "token")

    @classmethod
    def bind(
        cls, key: str, widget: QWidget, /, ignore_zero_value: bool = False
    ) -> DataBinder:
        return DataBinder(key, cls, widget, ignore_zero_value=ignore_zero_value)

    def token_exists(self) -> bool:
        return self.token is not None or os.path.exists(self.active_token_path)

    def load_active_config(self) -> "CleanConfig":
        return CleanConfig(
            active_dir=self._active_dir, filepath=self.active_config_path
        )

    def is_sync(self) -> bool:
        """
        Check if the current configuration is synchronized with the active configuration.
        """
        user_config = self.model_dump(exclude_defaults=True)
        active_config = self.load_active_config().model_dump(exclude_defaults=True)
        return user_config == active_config

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


def simple_parse(input_args: List[str]) -> SimpleNamespace:
    # args_list is directly read from old ai.gpustack.plist, the first two arguments must be
    # <executable> and 'start'
    args_list = input_args[2:]
    args = SimpleNamespace()
    positional = []
    i = 0
    while i < len(args_list):
        arg = args_list[i]
        if arg.startswith('--'):
            if '=' in arg:
                key, value = arg.split('=', 1)
                setattr(args, key[2:].replace('-', '_'), value)
            else:
                # Check if next arg is a value (not another option)
                if i + 1 < len(args_list) and not args_list[i + 1].startswith('--'):
                    setattr(args, arg[2:].replace('-', '_'), args_list[i + 1])
                    i += 1
                else:
                    setattr(args, arg[2:].replace('-', '_'), True)
        else:
            positional.append(arg)
        i += 1
    if positional:
        setattr(args, '_positional', positional)
    return args


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

    @classmethod
    def decode_from_data(cls, f: BinaryIO) -> Dict[str, Any]:
        data = plistlib.load(f)
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

    def load_active_config(self) -> "HelperConfig":
        """
        Load the active configuration from the specified path.
        """
        return HelperConfig(
            filepath=self.active_config_path,
            data_dir=self.active_data_dir,
            binary_path=self.gpustack_binary_path,
            debug=self.debug,
        )

    @property
    def user_gpustack_config(self) -> CleanConfig:
        return CleanConfig(
            self.active_data_dir, os.path.join(self.user_data_dir, gpustack_config_name)
        )

    @classmethod
    def load_legacy_helper_config(cls) -> Optional[_HelperConfig]:
        if not os.path.exists(plist_path):
            return None
        if os.path.islink(plist_path):
            logger.warning(f"{plist_path} is a symlink, it is not a legacy config.")
            return None
        try:
            with open(plist_path, 'rb') as f:
                datas = cls.decode_from_data(f)
        except Exception as e:
            logger.error(f"Failed to read legacy config from {plist_path}: {e}")
            return None

        return _HelperConfig(**datas)

    def load_legacy_gpustack_config(self) -> Optional[CleanConfig]:
        helper_config = self.load_legacy_helper_config()
        if helper_config is None:
            return None
        args = simple_parse(helper_config.ProgramArguments)
        config_data = {}
        active_data_dir = _default_path(
            Config.get_data_dir(), getattr(args, 'data_dir', None)
        )
        if hasattr(args, 'data_dir'):
            delattr(args, 'data_dir')
        if hasattr(args, 'config_file') and os.path.exists(args.config_file):
            config_data.update(load_config_from_yaml(args.config_file))
        set_common_options(args, config_data)
        set_server_options(args, config_data)
        set_worker_options(args, config_data)
        return CleanConfig(
            active_dir=active_data_dir,
            filepath=os.path.join(self.user_data_dir, gpustack_config_name),
            **config_data,
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
        self._override_data_dir = data_dir
        self._override_binary_path = binary_path
        self._debug = debug
        if self.gpustack_binary_path == "":
            raise ValueError(
                "GPUStack binary path is not set. Please set it via commandline flag."
            )
        super().__init__(filepath, **kwargs)
        if len(kwargs) == 0 and os.path.exists(filepath):
            self._reload()
        else:
            legacy = self.load_legacy_helper_config()
            if legacy is not None:
                self.EnvironmentVariables.update(legacy.EnvironmentVariables)
        if self.EnvironmentVariables.get("HOME") is None:
            self.EnvironmentVariables["HOME"] = os.path.join(
                self.active_data_dir, "root"
            )

    def update_with_lock(self, **kwargs):
        kwargs['ProgramArguments'] = self.program_args_defaults()
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
            if not os.path.lexists(link_target):
                os.symlink(self.active_data_dir, link_target, target_is_directory=True)

    def is_sync(self) -> bool:
        user_config = self.model_dump(exclude_defaults=True)
        active_config = self.load_active_config().model_dump(exclude_defaults=True)
        return user_config == active_config


def _default_path(default: str, override: Optional[str] = None) -> str:
    return override if override is not None else default
