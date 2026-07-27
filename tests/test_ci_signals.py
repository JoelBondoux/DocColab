from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_runs_project_quality_gates() -> None:
    content = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "jobs:" in content
    assert "ruff check agent tests" in content
    assert "mypy agent" in content
    assert "pytest --cov=agent --cov-branch" in content
    assert "--cov-fail-under=50" in content
    assert "pip-audit" in content
    assert "bandit -c pyproject.toml -r agent" in content


def test_ci_workflow_surfaces_coverage_results() -> None:
    content = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "--cov-report=term-missing" in content
    assert "--cov-report=xml" in content
    assert "actions/upload-artifact@" in content
    assert "path: coverage.xml" in content
