from abc import ABC, abstractmethod
from PySide6.QtCore import QProcess, QThread
from enum import Enum
from typing import Union

from gpustack_helper.config import HelperConfig


class AbstractService(ABC):
    """
    Base class for all services in the application.
    Provides a common interface and shared functionality.
    """

    class State(Enum):
        STOPPED = ("stopped", "停止")
        STOPPING = ("stopping", "停止中")
        RESTARTING = ("restarting", "重新启动中")
        STARTING = ("starting", "启动中")
        TO_SYNC = ("to_sync", "需要同步")
        UNKNOWN = ("unknown", "未知")
        STARTED = ("started", "运行中")

        def __init__(self, state, display_text):
            self.state = state  # 内部状态值
            self.display_text = display_text  # 显示文本

        @classmethod
        def get_display_text(cls, state):
            return next(
                (status.display_text for status in cls if status.state == state),
                "未知状态",
            )

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
