import threading
import yaml
import logging
import os
from typing import Dict, Any, BinaryIO, Type
from abc import ABC, abstractmethod
from pydantic import BaseModel
from gpustack_helper.databinder import set_nested_data

logger = logging.getLogger(__name__)


class ModelBackend(ABC):
    model: BaseModel
    _lock: threading.Lock

    def __init__(self, model: BaseModel):
        self.model = model
        self._lock = threading.Lock()

    def update_with_lock(self, **kwargs):
        with self._lock:
            self.reload()
            set_nested_data(self.model, kwargs)
            self.save()

    @abstractmethod
    def reload(self):
        pass

    @abstractmethod
    def save(self):
        pass


class ModelEncoder(ABC):
    @classmethod
    @abstractmethod
    def encode_to_data(cls, model: BaseModel) -> bytes:
        """
        Encode the model to a byte stream.
        """
        pass

    @classmethod
    @abstractmethod
    def decode_from_data(self, f: BinaryIO) -> Dict[str, Any]:
        """
        Decode the model from a byte stream.
        """
        pass


class YamlEncoder(ModelEncoder):
    @classmethod
    def encode_to_data(cls, model: BaseModel) -> bytes:
        data = model.model_dump(exclude_defaults=True)
        return yaml.safe_dump(data, stream=None).encode("utf-8")

    @classmethod
    def decode_from_data(cls, f: BinaryIO) -> Dict[str, Any]:
        data = f.read().decode("utf-8")
        return yaml.safe_load(data)


class PlistEncoder(ModelEncoder):
    @classmethod
    def encode_to_data(cls, model: BaseModel) -> bytes:
        import plistlib

        data = model.model_dump()
        return plistlib.dumps(data)

    @classmethod
    def decode_from_data(cls, f: BinaryIO) -> Dict[str, Any]:
        import plistlib

        return plistlib.load(f)


class FileConfigModel(ModelBackend):
    _filepath: str = None
    _encoder: Type[ModelEncoder] = None

    @property
    def filepath(self) -> str:
        return self._filepath

    def __init__(self, model: BaseModel, filepath: str, encoder=YamlEncoder):
        self._filepath = filepath
        self._encoder = encoder
        super().__init__(model)

    def reload(self):
        """
        Reload the configuration from the file.
        """
        if not os.path.exists(self.filepath):
            logger.debug(
                f"Configuration file not found, skipping loading: {self.filepath}"
            )
            return
        try:
            with open(self.filepath, "rb") as f:
                content = self._encoder.decode_from_data(f)
                set_nested_data(self.model, content)
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")

    def save(self):
        """
        Save the configuration to the specified path.
        """
        try:
            config_dir = os.path.dirname(self.filepath)
            os.makedirs(config_dir, exist_ok=True)
            with open(self.filepath, "wb") as f:
                f.write(self._encoder.encode_to_data(self.model))
        except Exception as e:
            logger.error(f"Failed to create config directory {config_dir}: {e}")
            return
