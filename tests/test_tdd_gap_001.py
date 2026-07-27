#!/usr/bin/env python3
"""
Test file for P1-FUNC-001: Core functionality tests - Minimal TDD test.

This test establishes the Green phase of TDD after implementing minimal functionality.
"""

import pytest
from agent.core import execute_core, AgentStatus, AgentResult


def test_agent_initialization():
    """
    Test that agent can be initialized with configuration.
    
    TDD Green phase: Minimal implementation to pass the test.
    """
    agent = execute_core({})
    assert agent is not None, "Agent should be initialized"
    assert agent.status == AgentStatus.INITIALIZED, "Agent status should be initialized"


def test_agent_execute_task():
    """
    Test that agent can execute a basic task.
    
    TDD Green phase: Minimal implementation to pass the test.
    """
    agent = execute_core({})
    result = agent.execute("test task")
    
    assert isinstance(result, AgentResult), "Result should be an AgentResult instance"
    assert result.success is True, "Task execution should succeed"
    assert "test task" in result.message, "Result message should contain the task"


def test_agent_with_configuration():
    """
    Test that agent can be initialized with configuration.
    
    TDD Green phase: Verify configuration handling.
    """
    config = {"model": "test-model", "timeout": 30}
    agent = execute_core(config)
    assert agent is not None, "Agent should be initialized with config"
    assert agent.config == config, "Agent should store the configuration"


def test_agent_execute_empty_task():
    """
    Test that agent handles empty tasks gracefully.
    
    TDD Green phase: Verify error handling.
    """
    agent = execute_core({})
    result = agent.execute("")
    
    assert isinstance(result, AgentResult), "Result should be an AgentResult instance"
    assert result.success is False, "Empty task should fail"
    assert "cannot be empty" in result.message.lower(), "Result should indicate empty task error"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])