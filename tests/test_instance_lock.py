from pathlib import Path

import pytest

from agent.instance_lock import InstanceLock


def test_instance_lock_prevents_two_publishers_for_one_database(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    first = InstanceLock.acquire(database)
    try:
        with pytest.raises(RuntimeError, match="already using"):
            InstanceLock.acquire(database)
    finally:
        first.close()

    reopened = InstanceLock.acquire(database)
    reopened.close()
