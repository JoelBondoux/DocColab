from pathlib import Path

from agent.main import build_parser as build_agent_parser
from agent.mcp_server.main import build_parser as build_mcp_parser


def test_agent_cli_parses_config_and_command() -> None:
    arguments = build_agent_parser().parse_args(
        ["--config", "project/config.json", "status"]
    )

    assert arguments.config == Path("project/config.json")
    assert arguments.command == "status"


def test_mcp_cli_parses_owner_initialization() -> None:
    arguments = build_mcp_parser().parse_args(
        [
            "--config",
            "project/mcp-config.json",
            "init-owner",
            "--user-id",
            "owner@example.com",
        ]
    )

    assert arguments.config == Path("project/mcp-config.json")
    assert arguments.command == "init-owner"
    assert arguments.user_id == "owner@example.com"
