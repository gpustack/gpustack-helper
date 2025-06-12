import sys
from gpustack_helper.services.abstract_service import AbstractService


def get_service_class() -> AbstractService:
    """
    Factory function to get the appropriate service class based on the platform.
    This function should be implemented in platform-specific modules.
    """
    if sys.platform == "win32":
        from gpustack_helper.services.windows import WindowsService

        return WindowsService
    elif sys.platform == "darwin":
        from gpustack_helper.services.darwin import DarwinService

        return DarwinService
    else:
        raise NotImplementedError(
            f"Service not implemented for platform: {sys.platform}"
        )
