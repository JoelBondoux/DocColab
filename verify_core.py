#!/usr/bin/env python3
"""Verify that the core module works correctly."""

import sys
sys.path.insert(0, '.')

from agent.core import execute_core, AgentStatus, AgentResult

print("Testing core module...")

# Test 1: Agent initialization
print("\n1. Testing agent initialization...")
agent = execute_core({})
print(f"   Agent created: {agent is not None}")
print(f"   Agent status: {agent.status}")
print(f"   Status matches: {agent.status == AgentStatus.INITIALIZED}")

# Test 2: Agent execution
print("\n2. Testing agent task execution...")
result = agent.execute("test task")
print(f"   Result type: {type(result).__name__}")
print(f"   Result success: {result.success}")
print(f"   Result message: {result.message}")
print(f"   Result data: {result.data}")

# Test 3: Verify AgentResult structure
print("\n3. Verifying AgentResult structure...")
assert isinstance(result, AgentResult), "Result should be AgentResult instance"
assert result.success is True, "Task should succeed"
assert "test task" in result.message, "Message should contain task name"

print("\n✅ All core module tests passed!")
print("\nThis confirms we can implement the minimal functionality.")
print("The RED phase test should now be updated to expect this behavior.")