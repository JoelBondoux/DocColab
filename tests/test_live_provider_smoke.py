from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent.config import AppConfig, load_config
from agent.runtime import Runtime, build_runtime


@pytest.fixture
def live_runtime() -> Iterator[tuple[AppConfig, Runtime]]:
    value = os.getenv("DOCCOLAB_LIVE_CONFIG")
    if not value:
        pytest.skip("Set DOCCOLAB_LIVE_CONFIG to run read-only provider smoke tests")
    config = load_config(Path(value))
    runtime = build_runtime(config)
    try:
        yield config, runtime
    finally:
        runtime.close()


@pytest.mark.live
def test_live_github_fixture_is_readable(live_runtime) -> None:
    config, runtime = live_runtime
    document = config.documents[0]
    branch = document.github_branch or config.github.branch

    runtime.github.get_file(document.markdown_path, branch)


@pytest.mark.live
def test_live_google_fixture_metadata_is_readable(live_runtime) -> None:
    config, runtime = live_runtime
    document = next(
        (item for item in config.documents if item.google_file_id),
        None,
    )
    if not config.google.enabled or not document or not runtime.manager.google_drive:
        pytest.skip("No enabled Google fixture is configured")

    metadata = runtime.manager.google_metadata(document)
    assert metadata and metadata.file_id == document.google_file_id


@pytest.mark.live
def test_live_microsoft_fixture_metadata_is_readable(live_runtime) -> None:
    config, runtime = live_runtime
    document = next(
        (item for item in config.documents if item.microsoft_item_id),
        None,
    )
    if not config.microsoft.enabled or not document or not runtime.manager.onedrive:
        pytest.skip("No enabled Microsoft fixture is configured")

    metadata = runtime.manager.microsoft_metadata(document)
    assert metadata and metadata.item_id == document.microsoft_item_id
