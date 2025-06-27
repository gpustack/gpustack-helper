from abc import ABC, abstractmethod
from PySide6.QtCore import QProcess, QThread
from enum import Flag, auto
from typing import Union

from gpustack_helper.config import HelperConfig


class AbstractService(ABC):
    """
    Base class for all services in the application.
    Provides a common interface and shared functionality.
    """

    class State(Flag):
        STOPPED = auto()
        STOPPING = auto()
        RESTARTING = auto()
        STARTING = auto()
        TO_MIGRATE = auto()
        TO_SYNC = auto()
        UNKNOWN = auto()
        STARTED = auto()

    @classmethod
    def get_display_text(cls, state: State) -> str:
        display_text = {
            cls.State.STOPPED | cls.State.TO_MIGRATE: "待升级",
            cls.State.STOPPED: "停止",
            cls.State.STOPPING: "停止中",
            cls.State.RESTARTING: "重新启动中",
            cls.State.STARTING: "启动中",
            cls.State.TO_SYNC: "待重启",
            cls.State.UNKNOWN: "未知",
            cls.State.STARTED: "运行中",
        }
        if display_text.get(state, None) is not None:
            return display_text[state]
        texts = []
        for key, value in display_text.items():
            if (state & key) == key:
                texts.append(value)
        return "|".join(texts) if texts else "未知状态"

    @classmethod
    @abstractmethod
    def start(cls, cfg: HelperConfig) -> Union[QProcess, QThread]:
        """
        Start the service. Override this method in subclasses to provide specific start logic.
        """

    @classmethod
    @abstractmethod
    def stop(self, cfg: HelperConfig) -> Union[QProcess, QThread]:
        """
        Stop the service. Override this method in subclasses to provide specific stop logic.
        """

    @classmethod
    @abstractmethod
    def restart(cls, cfg: HelperConfig) -> Union[QProcess, QThread]:
        """
        Restart the service. Override this method in subclasses to provide specific restart logic.
        """

    @classmethod
    @abstractmethod
    def get_current_state(cls, cfg: HelperConfig) -> State:
        """
        Get the current state of the service. Override this method in subclasses to provide specific state retrieval logic.
        """

    @classmethod
    @abstractmethod
    def migrate(cls, cfg: HelperConfig) -> None:
        """
        Migrate the service if necessary. Override this method in subclasses to provide specific migration logic.
        """
