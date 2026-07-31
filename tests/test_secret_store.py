import pytest

from agent.secret_store import require_secret


def test_require_secret_prefers_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCCOLAB_TEST_SECRET", "from-environment")

    assert require_secret("DOCCOLAB_TEST_SECRET") == "from-environment"


def test_require_secret_falls_back_to_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DOCCOLAB_TEST_SECRET", raising=False)
    monkeypatch.setattr(
        "agent.secret_store.keyring.get_password",
        lambda service, name: (
            "from-keyring"
            if service == "doccolab-secrets" and name == "DOCCOLAB_TEST_SECRET"
            else None
        ),
    )

    assert require_secret("DOCCOLAB_TEST_SECRET") == "from-keyring"


def test_require_secret_reports_missing_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DOCCOLAB_TEST_SECRET", raising=False)
    monkeypatch.setattr("agent.secret_store.keyring.get_password", lambda *_: None)

    with pytest.raises(RuntimeError, match="environment or OS keyring"):
        require_secret("DOCCOLAB_TEST_SECRET")
