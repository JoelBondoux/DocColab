"""
Minimal test to verify CI signals are working.
This test should fail initially to demonstrate the CI gap.
"""

def test_ci_signals_exist():
    """Verify that CI workflow signals are properly configured."""
    # This test will fail initially because there's no CI workflow file
    # After adding .github/workflows/ci.yml, this should pass
    import os
    ci_workflow_path = ".github/workflows/ci.yml"
    
    # Check if CI workflow exists
    assert os.path.exists(ci_workflow_path), (
        f"CI workflow file missing: {ci_workflow_path}. "
        "This prevents automated linting and testing on push/PR."
    )
    
    # Verify it contains expected jobs
    with open(ci_workflow_path) as f:
        content = f.read()
        assert "jobs:" in content, "CI workflow missing jobs section"
        assert "test:" in content, "CI workflow missing test job"
        assert "lint" in content, "CI workflow missing lint step"


def test_lint_command_works():
    """Verify that the lint command can execute without errors."""
    import subprocess
    
    # This should work after hatch run lint is properly configured
    result = subprocess.run(
        ["hatch", "run", "lint"],
        capture_output=True,
        text=True
    )
    
    # The command should complete successfully (exit code 0)
    assert result.returncode == 0, (
        f"Lint command failed with exit code {result.returncode}. "
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )