from abc import ABC, abstractmethod
from PySide6.QtCore import QProcess, QThread
from enum import Flag, auto
from typing import Union
from PySide6.QtCore import QCoreApplication


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
            cls.State.STOPPED
            | cls.State.TO_MIGRATE: QCoreApplication.translate(
                "AbstractService", "To Upgrade"
            ),
            cls.State.STOPPED: QCoreApplication.translate("AbstractService", "Stopped"),
            cls.State.STOPPING: QCoreApplication.translate(
                "AbstractService", "Stopping"
            ),
            cls.State.RESTARTING: QCoreApplication.translate(
                "AbstractService", "Restarting"
            ),
            cls.State.STARTING: QCoreApplication.translate(
                "AbstractService", "Starting"
            ),
            cls.State.TO_SYNC: QCoreApplication.translate(
                "AbstractService", "To Restart"
            ),
            cls.State.UNKNOWN: QCoreApplication.translate("AbstractService", "Unknown"),
            cls.State.STARTED: QCoreApplication.translate("AbstractService", "Running"),
        }
        if display_text.get(state, None) is not None:
            return display_text[state]
        texts = []
        for key, value in display_text.items():
            if (state & key) == key:
                texts.append(value)
        return (
            "|".join(texts)
            if texts
            else QCoreApplication.translate("AbstractService", "Unknown")
        )

    @classmethod
    @abstractmethod
    def start(cls) -> Union[QProcess, QThread]:
        """
        Start the service. Override this method in subclasses to provide specific start logic.
        """

    @classmethod
    @abstractmethod
    def stop(self) -> Union[QProcess, QThread]:
        """
        Stop the service. Override this method in subclasses to provide specific stop logic.
        """

    @classmethod
    @abstractmethod
    def restart(cls) -> Union[QProcess, QThread]:
        """
        Restart the service. Override this method in subclasses to provide specific restart logic.
        """

    @classmethod
    @abstractmethod
    def get_current_state(cls) -> State:
        """
        Get the current state of the service. Override this method in subclasses to provide specific state retrieval logic.
        """
