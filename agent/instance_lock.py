from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


@dataclass(slots=True)
class InstanceLock:
    path: Path
    _handle: BinaryIO
    _closed: bool = False

    @classmethod
    def acquire(cls, database_path: Path) -> InstanceLock:
        lock_path = database_path.with_suffix(database_path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+b")
        try:
            _lock(handle)
        except OSError as exc:
            handle.close()
            raise RuntimeError(
                f"Another DocColab publisher is already using {database_path}"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n".encode("ascii"))
        handle.flush()
        handle.seek(0)
        return cls(path=lock_path, _handle=handle)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            _unlock(self._handle)
        finally:
            self._handle.close()


def _lock(handle: BinaryIO) -> None:
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return
    import fcntl

    fcntl.flock(  # type: ignore[attr-defined]
        handle.fileno(),
        fcntl.LOCK_EX | fcntl.LOCK_NB,  # type: ignore[attr-defined]
    )


def _unlock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(  # type: ignore[attr-defined]
        handle.fileno(),
        fcntl.LOCK_UN,  # type: ignore[attr-defined]
    )
