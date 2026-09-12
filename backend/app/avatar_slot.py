"""One local GPU slot shared by the HTTP service and direct experiment processes.

Every participant must use the same lock file in the same filesystem namespace.
The file is deliberately retained: unlinking it could let a new process lock a
different inode while an existing generation still holds the old one.
"""

import errno
import fcntl
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_GPU_LOCK_PATH = "/tmp/pnballie-avatar-gpu.lock"


class AvatarGpuBusy(RuntimeError):
    """Another cooperating process owns the GPU slot."""


class AvatarGpuLockUnavailable(RuntimeError):
    """The shared GPU lock cannot be used safely."""


@contextmanager
def gpu_slot(path: str | os.PathLike[str] | None = None) -> Iterator[None]:
    """Acquire the GPU slot without waiting; release it on exit or process death.

    Keep model loading, inference and cleanup inside this context. A child process
    does not inherit the descriptor across exec, so its parent must retain the
    context until the child exits. This is an advisory lock, not a GPU quota.
    """
    lock_path = Path(path if path is not None else os.getenv("AVATAR_GPU_LOCK_PATH", DEFAULT_GPU_LOCK_PATH))
    if not lock_path.is_absolute():
        raise AvatarGpuLockUnavailable("AVATAR_GPU_LOCK_PATH must be an absolute path")
    descriptor = None
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
            raise AvatarGpuLockUnavailable("The GPU lock must be an owned regular file without hard links")
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise AvatarGpuBusy("The GPU slot is already reserved") from None
            raise
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise AvatarGpuLockUnavailable("The GPU lock could not be acquired") from exc
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        raise
    try:
        yield
    finally:
        # Closing the only descriptor releases flock, including on exceptions.
        # The kernel also closes it after SIGKILL or a process crash.
        os.close(descriptor)
