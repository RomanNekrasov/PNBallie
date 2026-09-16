"""Private, immutable originals on the application PVC; never served by HTTP."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
              "image/heic": ".heic", "image/heif": ".heif",
              "image/heic-sequence": ".heic", "image/heif-sequence": ".heif"}


def store_original(raw: bytes, mime: str, *, group_id: int, player_id: int, job_id: str) -> Path:
    # None of these path components comes from a filename supplied by the client.
    UUID(job_id)
    if group_id < 1 or player_id < 1:
        raise ValueError("Invalid archive owner")
    folder = Path(os.getenv("AVATAR_ORIGINALS_DIR", ".local-data/avatar-originals"))
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    for part in (str(group_id), str(player_id)):
        folder = folder / part
        folder.mkdir(mode=0o700, exist_ok=True)
    target = folder / (job_id + EXTENSIONS[mime])
    temporary = None
    try:
        with NamedTemporaryFile(dir=folder, prefix=".upload-", delete=False) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), 0o600)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        # Immutable destination. Linking is atomic and refuses an existing file.
        os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target
