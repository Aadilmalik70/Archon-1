"""
Claude Code Executor Module

This module provides automated execution of tasks using Claude Code CLI.
It manages subprocess execution, prompt building, and result parsing.
"""

from .claude_agent import ClaudeCodeExecutor, ClaudeCodeExecutionError

__all__ = ["ClaudeCodeExecutor", "ClaudeCodeExecutionError"]
