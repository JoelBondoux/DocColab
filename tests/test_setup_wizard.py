from dataclasses import replace
from pathlib import Path

import pytest

from agent.config import load_config
from agent.mcp_server.registry import ProjectRegistry, UserRegistry, load_server_config
from agent.setup_wizard import (
    SetupAnswers,
    SetupConflict,
    generate_setup,
    run_interactive,
)


def _answers(root: Path) -> SetupAnswers:
    return SetupAnswers(
        output_directory=root,
        project_id="example",
        project_title="Example project",
        owner_user_id="owner@example.com",
        github_owner="example-owner",
        github_repository="example-repository",
        github_branch="develop",
        exposed_folders=("documents", "references"),
        google_enabled=True,
        google_file_id="google-file-id",
        google_broad_access_acknowledged=True,
        google_write_enabled=False,
        microsoft_enabled=True,
        microsoft_drive_id="drive-id",
        microsoft_item_id="item-id",
        microsoft_broad_access_acknowledged=True,
        ai_provider="openai",
        tailnet_hostname="doccolab.example.ts.net",
        github_token="github-secret",
        openai_api_key="openai-secret",
        microsoft_client_id="microsoft-client-id",
    )


def test_generate_setup_creates_valid_isolated_configuration(tmp_path: Path) -> None:
    stored_secrets: dict[str, str] = {}
    result = generate_setup(
        _answers(tmp_path),
        secret_writer=lambda values: stored_secrets.update(values),
    )

    sync_config = load_config(tmp_path / "config.json")
    server_config = load_server_config(tmp_path / "mcp-config.json")
    project = ProjectRegistry(server_config).get("example")
    users = UserRegistry(server_config.users_file)

    assert sync_config.github.repository == "example-repository"
    assert sync_config.documents[0].google_file_id == "google-file-id"
    assert sync_config.documents[0].microsoft_item_id == "item-id"
    assert project.root_path == tmp_path.resolve()
    assert project.exposed_folders == ["documents", "references"]
    assert users.authenticate(result.owner_token) is not None
    assert result.owner_token not in server_config.users_file.read_text(encoding="utf-8")
    environment = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "openai-secret" not in environment
    assert "github-secret" not in environment
    assert stored_secrets["OPENAI_API_KEY"] == "openai-secret"
    assert stored_secrets["GITHUB_TOKEN"] == "github-secret"
    assert len(stored_secrets["GOOGLE_WEBHOOK_TOKEN"]) >= 32
    assert server_config.allowed_hosts == [
        "127.0.0.1:*",
        "localhost:*",
        "doccolab.example.ts.net",
    ]
    assert (tmp_path / "documents").is_dir()
    assert (tmp_path / "references").is_dir()


def test_generate_setup_refuses_to_overwrite_any_existing_target(tmp_path: Path) -> None:
    existing = tmp_path / "config.json"
    existing.write_text("keep me", encoding="utf-8")

    with pytest.raises(SetupConflict, match="config.json"):
        generate_setup(_answers(tmp_path))

    assert existing.read_text(encoding="utf-8") == "keep me"
    assert not (tmp_path / "mcp-config.json").exists()
    assert not (tmp_path / "registry").exists()


def test_setup_answers_require_at_least_one_document_surface(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Google Docs or OneDrive"):
        SetupAnswers(
            output_directory=tmp_path,
            project_id="example",
            project_title="Example",
            owner_user_id="owner@example.com",
            github_owner="owner",
            github_repository="repo",
            google_enabled=False,
            microsoft_enabled=False,
        )


def test_setup_answers_reject_unsafe_project_and_folder_names(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="project_id"):
        replace(_answers(tmp_path), project_id="../../escape")

    with pytest.raises(ValueError, match="exposed_folders"):
        SetupAnswers(
            output_directory=tmp_path,
            project_id="example",
            project_title="Example",
            owner_user_id="owner@example.com",
            github_owner="owner",
            github_repository="repo",
            google_enabled=True,
            google_file_id="google-id",
            google_broad_access_acknowledged=True,
            exposed_folders=("../private",),
        )


def test_interactive_setup_accepts_defaults_and_generates_follow_up(
    tmp_path: Path,
) -> None:
    responses = iter(
        [
            "",  # project title
            "",  # project ID
            "owner@example.com",
            "example-owner",
            "",  # repository
            "",  # branch
            "",  # document title
            "",  # document ID
            "yes",
            "google-file-id",
            "yes",  # acknowledge Google access
            "no",  # keep Google read-only
            "no",
            "none",
            "",  # exposed folders
            "",  # Tailnet hostname
            "",  # confirmation
        ]
    )
    secrets = iter([""])
    output: list[str] = []

    result = run_interactive(
        tmp_path,
        input_fn=lambda _: next(responses),
        secret_fn=lambda _: next(secrets),
        output_fn=output.append,
        secret_writer=lambda _: None,
    )

    assert (tmp_path / "config.json").exists()
    assert any("Configuration directory" in line for line in output)
    assert result.owner_token
    assert any("auth-google" in command for command in result.next_commands)
    assert load_config(tmp_path / "config.json").google.write_mode == "read_only"
