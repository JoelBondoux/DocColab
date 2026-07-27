import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
PYPROJECT = ROOT / "pyproject.toml"


def test_ci_workflow_runs_project_quality_gates() -> None:
    content = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "jobs:" in content
    assert "ruff check agent tests" in content
    assert "mypy agent" in content
    assert "pytest --cov-report=xml" in content
    assert "pip-audit" in content
    assert "bandit -c pyproject.toml -r agent" in content


def test_ci_workflow_surfaces_coverage_results() -> None:
    content = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "--cov-report=xml" in content
    assert "actions/upload-artifact@" in content
    assert "path: coverage.xml" in content


def test_pyproject_is_the_single_coverage_source_of_truth() -> None:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    pytest_options = config["tool"]["pytest"]["ini_options"]["addopts"]
    coverage = config["tool"]["coverage"]
    assert "--cov=agent" in pytest_options
    assert "--cov-branch" in pytest_options
    assert "--cov-report=term-missing" in pytest_options
    assert coverage["run"]["source"] == ["agent"]
    assert coverage["run"]["branch"] is True
    assert coverage["report"]["fail_under"] == 60
    assert not (ROOT / "pytest.ini").exists()


def test_release_workflow_builds_checks_and_uses_trusted_publishing() -> None:
    content = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "python -m build" in content
    assert "twine check dist/*" in content
    assert "id-token: write" in content
    assert "pypa/gh-action-pypi-publish@" in content
