import os
import sys
import argparse
import logging
from typing import Optional, List, Dict
from types import SimpleNamespace
from functools import partial
from gpustack.config import Config
from gpustack.cmd.start import (
    set_common_options,
    set_server_options,
    set_worker_options,
    load_config_from_yaml,
)
from gpustack_helper.config.config import HelperConfig, GPUStackConfig
from gpustack_helper.config.backends import FileConfigModel, PlistEncoder
from gpustack_helper.defaults import (
    global_data_dir,
    data_dir as default_data_dir,
    gpustack_config_name,
    helper_config_file_name,
)

if sys.platform == "win32":
    from gpustack_helper.config.windows_backend import (
        RegistryModel,
        legacy_helper_config,
        service_exists,
    )
else:
    from gpustack_helper.config.config import legacy_helper_config


__all__ = [
    'init_config',
    "HelperConfig",
    "GPUStackConfig",
    "user_helper_config",
    "active_helper_config",
    "user_gpustack_config",
    "active_gpustack_config",
    "legacy_gpustack_config",
    "ensure_data_dir",
    "is_first_boot",
    "migrate_config",
]

logger = logging.getLogger(__name__)

_user_helper_config: HelperConfig = None
_active_helper_config: HelperConfig = None
_user_gpustack_config: GPUStackConfig = None
_active_gpustack_config: GPUStackConfig = None


def init_config(args: argparse.Namespace) -> None:
    global _user_helper_config, _active_helper_config, _user_gpustack_config, _active_gpustack_config, active_gpustack_path, user_gpustack_path
    config_vars = args.__dict__
    # Remove all keys from config_vars where the value is None
    for key in list(config_vars.keys()):
        if config_vars[key] is None:
            config_vars.pop(key)
            continue
        if key.endswith("_path") or key.endswith("_dir"):
            config_vars[key] = os.path.abspath(config_vars[key])
    override_data_dir = config_vars.pop('data_dir', None)

    user_data_dir = override_data_dir or default_data_dir
    active_data_dir = override_data_dir or global_data_dir

    user_gpustack_path = os.path.join(user_data_dir, gpustack_config_name)
    active_gpustack_path = os.path.join(active_data_dir, gpustack_config_name)

    _user_gpustack_config = GPUStackConfig(
        backend=lambda x: FileConfigModel(
            x,
            filepath=user_gpustack_path,
        ),
        gpustack_config_path=user_gpustack_path,
        data_dir=user_data_dir,
    )

    _active_gpustack_config = GPUStackConfig(
        backend=lambda x: FileConfigModel(
            x,
            filepath=active_gpustack_path,
        ),
        gpustack_config_path=active_gpustack_path,
        data_dir=active_data_dir,
    )

    active_helper_path = (
        os.path.join(active_data_dir, helper_config_file_name)
        if sys.platform == "darwin"
        else None
    )
    p_model_func = (
        (
            partial(
                FileConfigModel,
                filepath=active_helper_path,
                encoder=PlistEncoder,
            )
        )
        if sys.platform != "win32"
        else RegistryModel
    )
    _active_helper_config = HelperConfig(
        backend=p_model_func,
        data_dir=active_data_dir,
        config_path=active_helper_path,
        gpustack_config_path=active_gpustack_path,
        **config_vars,
    )

    if sys.platform == "darwin":
        _user_helper_config_path = os.path.join(user_data_dir, helper_config_file_name)
        _user_helper_config = HelperConfig(
            backend=lambda x: FileConfigModel(
                x, filepath=_user_helper_config_path, encoder=PlistEncoder
            ),
            data_dir=active_data_dir,
            config_path=_user_helper_config_path,
            gpustack_config_path=active_gpustack_path,
            **config_vars,
        )
    else:
        # In windows, we use the same config for user and active
        _user_helper_config = _active_helper_config


def user_helper_config() -> HelperConfig:
    global _user_helper_config
    return _user_helper_config


def active_helper_config() -> HelperConfig:
    global _active_helper_config
    return _active_helper_config


def user_gpustack_config() -> GPUStackConfig:
    global _user_gpustack_config
    return _user_gpustack_config


def active_gpustack_config() -> GPUStackConfig:
    global _active_gpustack_config
    return _active_gpustack_config


def ensure_data_dir() -> None:
    user_data_dir = _user_gpustack_config.data_dir
    active_data_dir = _active_gpustack_config.data_dir
    if not os.path.exists(user_data_dir):
        try:
            os.makedirs(user_data_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create user data directory {user_data_dir}: {e}")
            raise
    if sys.platform != "darwin" or user_data_dir == active_data_dir:
        return

    link_target = os.path.join(user_data_dir, "data-dir")
    if os.path.lexists(link_target):
        if os.path.islink(link_target):
            if os.readlink(link_target) != active_data_dir:
                os.unlink(link_target)
        else:
            logger.warning(
                f"{link_target} exists and is not a symlink, skip creating symlink to avoid data loss."
            )
            return
    if not os.path.lexists(link_target):
        os.symlink(active_data_dir, link_target, target_is_directory=True)


def all_config_sync() -> bool:
    helper_user = _user_helper_config.model_dump(exclude_defaults=True)
    helper_active = _active_helper_config.model_dump(exclude_defaults=True)
    gpustack_user = _user_gpustack_config.model_dump(exclude_defaults=True)
    gpustack_active = _active_gpustack_config.model_dump(exclude_defaults=True)
    return helper_user == helper_active and gpustack_user == gpustack_active


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


def legacy_gpustack_config() -> Optional[GPUStackConfig]:
    helper_config = legacy_helper_config()
    if helper_config is None:
        return None
    args = simple_parse(helper_config.ProgramArguments)
    config_data = {}
    config_data['data_dir'] = getattr(args, 'data_dir', Config.get_data_dir())
    if hasattr(args, 'data_dir'):
        delattr(args, 'data_dir')
    if hasattr(args, 'config_file') and os.path.exists(args.config_file):
        config_data.update(load_config_from_yaml(args.config_file))
    set_common_options(args, config_data)
    set_server_options(args, config_data)
    set_worker_options(args, config_data)
    return GPUStackConfig(backend=None, gpustack_config_path="", **config_data)


def is_first_boot() -> bool:
    if sys.platform == "darwin":
        return not os.path.exists(_user_helper_config.config_path)
    exists, _ = service_exists()
    return not exists


def migrate_config():
    helper_legacy = legacy_helper_config()
    gpustack_legacy = legacy_gpustack_config()
    if helper_legacy is None or gpustack_legacy is None:
        return
    if gpustack_legacy is not None:
        # will migrate legacy config to new config
        config_data = gpustack_legacy.model_dump(exclude_defaults=True)
        user_gpustack_config().update_with_lock(
            **config_data,
        )
    if sys.platform == "darwin":
        env1: Dict[str, str] = helper_legacy.model_dump(
            include={"EnvironmentVariables"}
        ).get("EnvironmentVariables", {})
        env2: Dict[str, str] = _user_helper_config.model_dump(
            include={"EnvironmentVariables"}
        ).get("EnvironmentVariables", {})
        merged = env2.copy()
        merged.update(env1)

        _user_helper_config.update_with_lock(
            EnvironmentVariables=merged,
        )
