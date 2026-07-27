from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import BinaryIO, cast


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
        _windows_lock(handle, "LK_NBLCK")
        return
    _posix_lock(handle, exclusive=True)


def _unlock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        _windows_lock(handle, "LK_UNLCK")
        return
    _posix_lock(handle, exclusive=False)


def _windows_lock(handle: BinaryIO, mode_name: str) -> None:
    module_values = vars(import_module("msvcrt"))
    locking = cast(Callable[[int, int, int], None], module_values["locking"])
    mode = cast(int, module_values[mode_name])
    locking(handle.fileno(), mode, 1)


def _posix_lock(handle: BinaryIO, *, exclusive: bool) -> None:
    module_values = vars(import_module("fcntl"))
    flock = cast(Callable[[int, int], None], module_values["flock"])
    operation = cast(
        int,
        (
            module_values["LOCK_EX"] | module_values["LOCK_NB"]
            if exclusive
            else module_values["LOCK_UN"]
        ),
    )
    flock(handle.fileno(), operation)
