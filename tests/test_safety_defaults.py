from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.config import AIConfig, AppConfig, GoogleConfig, MicrosoftConfig


def test_automation_and_provider_access_require_explicit_opt_in() -> None:
    ai = AIConfig()
    assert not ai.enabled
    assert not ai.auto_rewrite_human_changes

    with pytest.raises(ValidationError, match="acknowledge_broad_access"):
        GoogleConfig(enabled=True)
    with pytest.raises(ValidationError, match="non_atomic"):
        GoogleConfig(
            enabled=True,
            acknowledge_broad_access=True,
            write_mode="replace",
        )
    with pytest.raises(ValidationError, match="acknowledge_broad_access"):
        MicrosoftConfig(enabled=True)

    google = GoogleConfig(enabled=True, acknowledge_broad_access=True)
    assert google.write_mode == "read_only"


def test_example_config_is_valid_and_keeps_external_processing_disabled() -> None:
    path = Path(__file__).resolve().parents[1] / "config.example.json"
    config = AppConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert not config.google.enabled
    assert not config.microsoft.enabled
    assert not config.ai.enabled
    assert config.google.write_mode == "read_only"
