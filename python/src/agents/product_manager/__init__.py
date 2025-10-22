"""
AI Product Manager Orchestrator Agent

This module provides the main AI-PM orchestrator agent that:
- Analyzes feature requests
- Breaks down work into atomic tasks
- Assigns tasks to specialized agents
- Monitors execution progress
- Updates external systems (Slack, Asana)
"""

from .orchestrator_agent import OrchestratorAgent, OrchestratorDependencies, TaskBreakdown
from .progress_reporter import ProgressReporter
from .task_executor import TaskExecutor, start_task_monitoring

__all__ = [
    "OrchestratorAgent",
    "OrchestratorDependencies",
    "TaskBreakdown",
    "ProgressReporter",
    "TaskExecutor",
    "start_task_monitoring",
]
