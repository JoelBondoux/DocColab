import json
from pathlib import Path

from agent.mcp_server.audit import AuditLogger


def test_audit_log_rotates_at_configured_size(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = AuditLogger(path, max_bytes=180, backup_count=2)

    for index in range(8):
        audit.record(
            user_id="owner@example.com",
            tool="doccolab.write_file",
            project_id="project",
            outcome="succeeded",
            detail={"index": index},
        )

    assert path.exists()
    assert path.with_suffix(".jsonl.1").exists()
    assert len(list(tmp_path.glob("audit.jsonl*"))) <= 3
    for log in tmp_path.glob("audit.jsonl*"):
        for line in log.read_text(encoding="utf-8").splitlines():
            assert json.loads(line)["outcome"] == "succeeded"
