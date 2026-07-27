"""Core agent functionality module.

This module provides the minimal core functionality needed for the agent system.
It will be expanded as we implement more features through TDD.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel


class AgentStatus(str, BaseModel):
    """Enumeration of possible agent statuses."""
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class AgentResult(BaseModel):
    """Result structure for agent operations."""
    success: bool = False
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class Agent:
    """Minimal agent implementation for core functionality."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the agent with optional configuration."""
        self.config = config or {}
        self.status = AgentStatus.INITIALIZED

    def execute(self, task: str) -> AgentResult:
        """Execute a basic agent task."""
        if not task:
            return AgentResult(
                success=False,
                message="Task cannot be empty",
                error="Empty task"
            )
        
        return AgentResult(
            success=True,
            message=f"Task '{task}' executed successfully",
            data={"task": task, "status": "completed"}
        )


def execute_core(config: Optional[Dict[str, Any]] = None) -> Agent:
    """Initialize and return a core agent instance.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Agent instance
    """
    return Agent(config)