#!/usr/bin/env python3
"""
Test file for P1-FUNC-001: Core functionality tests - Runtime and Manager.

This file captures the expected behavior of critical path operations.
Initially, these tests will fail since the functionality is not yet fully tested.
"""

import pytest
from agent.runtime import build_runtime, Runtime
from agent.config import load_config
from pathlib import Path


def test_runtime_builds_with_github_only():
    """
    Test that Runtime can be built with GitHub integration only.
    This is the minimal core functionality test.
    Initially this will fail since we need to verify the actual behavior.
    """
    # This test should fail initially - we're documenting the expected behavior
    config_path = Path("config.example.json")
    if not config_path.exists():
        pytest.skip("config.example.json not found")
    
    config = load_config(config_path)
    config.github.enabled = True
    config.github.token_env = "GITHUB_TOKEN"
    config.google.enabled = False
    config.microsoft.enabled = False
    config.ai.enabled = False
    
    # Expected: Runtime should be created successfully
    runtime = build_runtime(config)
    assert runtime is not None, "Runtime should be created"
    assert isinstance(runtime, Runtime), "Should return a Runtime instance"
    runtime.close()


def test_runtime_has_required_components():
    """
    Test that Runtime has all required components after build.
    """
    config_path = Path("config.example.json")
    if not config_path.exists():
        pytest.skip("config.example.json not found")
    
    config = load_config(config_path)
    config.github.enabled = True
    config.github.token_env = "GITHUB_TOKEN"
    config.google.enabled = False
    config.microsoft.enabled = False
    config.ai.enabled = False
    
    runtime = build_runtime(config)
    
    # Expected components
    assert runtime.manager is not None, "Runtime should have a manager"
    assert runtime.state is not None, "Runtime should have a state store"
    assert runtime.github is not None, "Runtime should have a GitHub client"
    assert runtime.graph is None, "Runtime should not have Microsoft Graph when disabled"
    
    runtime.close()


def test_runtime_close_is_safe():
    """
    Test that Runtime.close() can be called multiple times without error.
    """
    config_path = Path("config.example.json")
    if not config_path.exists():
        pytest.skip("config.example.json not found")
    
    config = load_config(config_path)
    config.github.enabled = True
    config.github.token_env = "GITHUB_TOKEN"
    config.google.enabled = False
    config.microsoft.enabled = False
    config.ai.enabled = False
    
    runtime = build_runtime(config)
    
    # Expected: close should be safe to call
    runtime.close()
    runtime.close()  # Should not raise an error


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])