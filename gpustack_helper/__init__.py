try:
    from gpustack_helper._version import (
        __version__ as version,
        __commit__ as commit,
        __gpustack_commit__ as gpustack_commit,
    )
except ImportError:
    version = "v0.0.0.0"
    commit = "HEAD"
    gpustack_commit = "HEAD"
finally:
    __version__ = version
    __commit__ = commit
    __gpustack_commit__ = gpustack_commit
