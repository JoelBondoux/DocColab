from __future__ import annotations

from agent.cli_errors import run_cli
from agent.main import main as agent_main
from agent.mcp_server.main import main as mcp_main


def test_run_cli_maps_common_failures_to_stable_exit_codes(capsys) -> None:
    assert run_cli(lambda: None) == 0
    assert run_cli(lambda: (_ for _ in ()).throw(FileNotFoundError("missing.json"))) == 2
    assert run_cli(lambda: (_ for _ in ()).throw(PermissionError("forbidden"))) == 3
    assert run_cli(lambda: (_ for _ in ()).throw(RuntimeError("offline"))) == 1
    assert run_cli(lambda: (_ for _ in ()).throw(KeyboardInterrupt())) == 130

    errors = capsys.readouterr().err
    assert "Configuration error: missing.json" in errors
    assert "Access denied: forbidden" in errors
    assert "Operation failed: offline" in errors
    assert "Cancelled." in errors
    assert "Traceback" not in errors


def test_entry_points_render_missing_config_without_traceback(capsys) -> None:
    assert agent_main(["--config", "missing-agent.json", "status"]) == 2
    assert mcp_main(["--config", "missing-mcp.json", "validate"]) == 2

    errors = capsys.readouterr().err
    assert "Configuration error:" in errors
    assert "Traceback" not in errors
