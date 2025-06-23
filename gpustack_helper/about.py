import logging
from PySide6.QtWidgets import QMessageBox, QWidget

logger = logging.getLogger(__name__)


class About:
    parent: QWidget
    gpustack_version: str
    gpustack_commit: str
    helper_version: str
    helper_commit: str

    def __init__(self, parent: QWidget):
        self.parent = parent
        self.gpustack_commit = "unknown"
        self.gpustack_version = "unknown"
        self.helper_version = "unknown"
        self.helper_commit = "unknown"

        try:
            from gpustack_helper import __version__ as __helper_version
            from gpustack_helper import __commit__ as __helper_commit
            from gpustack_helper import __gpustack_commit__
            from gpustack import __version__ as gpustack_version
            from gpustack import __git_commit__ as gpustack_commit

            self.helper_version = __helper_version
            self.helper_commit = __helper_commit
            self.gpustack_version = gpustack_version
            self.gpustack_commit = gpustack_commit

            if self.gpustack_commit == "HEAD" and __gpustack_commit__ != "":
                self.gpustack_commit = __gpustack_commit__

        except Exception as e:
            logger.error("Failed to get GPUStack version or commit", exc_info=e)

    def exec(self):
        return QMessageBox.information(
            self.parent,
            "关于",
            f"GPUStack\n版本: {self.gpustack_version}({self.gpustack_commit})\nHelper: {self.helper_version}({self.helper_commit})",
        )
