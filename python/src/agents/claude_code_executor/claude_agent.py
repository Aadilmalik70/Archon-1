"""
Claude Code Executor Agent

Executes tasks by running Claude Code CLI as a subprocess.
Builds prompts from task details and parses execution results.
"""

import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ClaudeCodeExecutionError(Exception):
    """Raised when Claude Code execution fails."""

    pass


class ClaudeCodeExecutor:
    """Executes tasks using Claude Code CLI."""

    def __init__(
        self,
        claude_code_path: str | None = None,
        workspace_path: str | None = None,
        timeout: int = 600,  # 10 minutes default
    ):
        """
        Initialize Claude Code Executor.

        Args:
            claude_code_path: Path to Claude Code CLI (default: from env or 'claude-code')
            workspace_path: Working directory for execution (default: current directory)
            timeout: Max execution time in seconds (default: 600)
        """
        # Get Claude Code path, handling empty strings
        env_path = os.getenv("CLAUDE_CODE_PATH", "").strip()
        self.claude_code_path = claude_code_path or env_path or "claude-code"

        # Get workspace path, handling empty strings
        env_workspace = os.getenv("WORKSPACE_PATH", "").strip()
        self.workspace_path = workspace_path or env_workspace or os.getcwd()

        self.timeout = timeout

        logger.info(
            f"Initialized ClaudeCodeExecutor: path={self.claude_code_path}, "
            f"workspace={self.workspace_path}, timeout={self.timeout}s"
        )

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a task using Claude Code CLI.

        Args:
            task: Task dict with title, description, acceptance_criteria, files_affected

        Returns:
            Dict with execution results:
            {
                "success": bool,
                "output": str,
                "files_modified": list[str],
                "tests_passed": bool,
                "test_output": str,
                "error": str | None,
            }
        """
        logger.info(f"Executing task via Claude Code: {task.get('title')}")

        try:
            # Build prompt from task details
            prompt = self._build_task_prompt(task)

            # Execute Claude Code CLI
            result = await self._run_claude_code(prompt)

            # Parse execution result
            execution_result = self._parse_execution_result(result, task)

            logger.info(
                f"Task execution {'succeeded' if execution_result['success'] else 'failed'}: "
                f"{task.get('title')}"
            )

            return execution_result

        except asyncio.TimeoutError:
            error_msg = f"Claude Code execution timed out after {self.timeout}s"
            logger.error(error_msg)
            return {
                "success": False,
                "output": "",
                "files_modified": [],
                "tests_passed": False,
                "test_output": "",
                "error": error_msg,
            }
        except Exception as e:
            error_msg = f"Claude Code execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "output": "",
                "files_modified": [],
                "tests_passed": False,
                "test_output": "",
                "error": error_msg,
            }

    def _build_task_prompt(self, task: dict[str, Any]) -> str:
        """
        Build Claude Code prompt from task details.

        Args:
            task: Task dict

        Returns:
            Formatted prompt string
        """
        title = task.get("title", "Untitled Task")
        description = task.get("description", "")
        files_affected = task.get("files_affected", [])

        # Extract acceptance criteria from description if present
        acceptance_criteria = self._extract_criteria_from_description(description)

        # Build comprehensive prompt
        prompt = f"""You are implementing a task for the Archon project. Follow these requirements exactly:

TASK: {title}

DESCRIPTION:
{description}

"""

        if acceptance_criteria:
            prompt += f"""ACCEPTANCE CRITERIA:
{chr(10).join(f'  {i+1}. {criterion}' for i, criterion in enumerate(acceptance_criteria))}

"""

        if files_affected:
            prompt += f"""FILES TO MODIFY:
{chr(10).join(f'  - {file}' for file in files_affected)}

"""

        # Add execution instructions
        prompt += """EXECUTION REQUIREMENTS:
1. Read and understand all requirements above
2. Implement the solution following acceptance criteria
3. Create/modify files as specified
4. Run all relevant tests to verify correctness
5. Fix any failing tests before completing
6. When done, output exactly: "ARCHON_TASK_COMPLETE"
7. If you encounter errors you cannot resolve, output: "ARCHON_TASK_FAILED: [reason]"

IMPORTANT:
- Do NOT ask for confirmation - proceed with implementation
- Follow the project's coding standards and patterns
- Ensure all tests pass before marking complete
- Be thorough but efficient

Begin implementation now.
"""

        return prompt

    def _extract_criteria_from_description(self, description: str) -> list[str]:
        """Extract acceptance criteria from task description."""
        criteria = []

        # Look for "Acceptance Criteria:" section
        if "**Acceptance Criteria:**" in description:
            lines = description.split("\n")
            in_criteria = False
            for line in lines:
                if "**Acceptance Criteria:**" in line:
                    in_criteria = True
                    continue
                if in_criteria:
                    # Stop at next section
                    if line.strip().startswith("**") and line.strip().endswith("**"):
                        break
                    # Extract criterion (remove leading "- ")
                    if line.strip().startswith("-"):
                        criteria.append(line.strip()[2:])

        return criteria

    async def _run_claude_code(self, prompt: str) -> dict[str, Any]:
        """
        Run Claude Code CLI with prompt.

        Args:
            prompt: Task prompt

        Returns:
            Dict with stdout, stderr, returncode
        """
        # Write prompt to temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            logger.debug(f"Created prompt file: {prompt_file}")
            logger.debug(f"Prompt content:\n{prompt}")

            # Build command
            # Note: Adjust these flags based on your Claude Code CLI version
            cmd = [
                self.claude_code_path,
                # "--non-interactive",  # Uncomment if Claude Code supports this
                # "--prompt-file", prompt_file,  # Uncomment if supported
            ]

            logger.info(f"Executing command: {' '.join(cmd)}")

            # Execute Claude Code
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_path,
            )

            # Send prompt via stdin and wait for completion
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=prompt.encode("utf-8")), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                logger.error("Claude Code execution timed out, terminating process")
                process.kill()
                await process.wait()
                raise

            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": process.returncode,
            }

        finally:
            # Clean up prompt file
            try:
                os.unlink(prompt_file)
            except Exception as e:
                logger.warning(f"Failed to delete prompt file: {e}")

    def _parse_execution_result(self, result: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
        """
        Parse Claude Code execution result.

        Args:
            result: Raw execution result with stdout/stderr
            task: Original task dict

        Returns:
            Parsed execution result
        """
        stdout = result["stdout"]
        stderr = result["stderr"]
        returncode = result["returncode"]

        # Check for completion markers
        success = "ARCHON_TASK_COMPLETE" in stdout or returncode == 0
        failed = "ARCHON_TASK_FAILED" in stdout

        # Extract error message if failed
        error = None
        if failed:
            # Extract reason from "ARCHON_TASK_FAILED: reason"
            match = re.search(r"ARCHON_TASK_FAILED:\s*(.+)", stdout)
            if match:
                error = match.group(1).strip()
            else:
                error = "Task execution failed (no reason provided)"
        elif returncode != 0:
            error = f"Process exited with code {returncode}"

        # Extract modified files
        files_modified = self._extract_modified_files(stdout)

        # Extract test results
        tests_passed, test_output = self._extract_test_results(stdout)

        return {
            "success": success and not failed,
            "output": stdout,
            "files_modified": files_modified,
            "tests_passed": tests_passed,
            "test_output": test_output,
            "error": error or (stderr if stderr else None),
        }

    def _extract_modified_files(self, output: str) -> list[str]:
        """Extract list of modified files from Claude Code output."""
        files = []

        # Look for common file modification patterns
        patterns = [
            r"Created\s+file:\s*(.+)",
            r"Modified\s+file:\s*(.+)",
            r"Updated\s+file:\s*(.+)",
            r"Wrote\s+to:\s*(.+)",
            r"✓\s+(.+\.(?:py|ts|tsx|js|jsx|sql|md))",  # Common file extensions
        ]

        for pattern in patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            for match in matches:
                file_path = match.strip()
                if file_path and file_path not in files:
                    files.append(file_path)

        return files

    def _extract_test_results(self, output: str) -> tuple[bool, str]:
        """
        Extract test results from Claude Code output.

        Returns:
            Tuple of (tests_passed: bool, test_output: str)
        """
        # Look for test result patterns
        test_patterns = {
            "passed": [
                r"(\d+)\s+passed",
                r"All\s+tests\s+passed",
                r"✓\s+All\s+tests",
                r"Tests:\s+\d+\s+passed",
            ],
            "failed": [
                r"(\d+)\s+failed",
                r"Tests\s+failed",
                r"✗\s+.+\s+failed",
                r"FAILED",
            ],
        }

        # Check for test execution
        test_output = ""
        test_section_started = False

        for line in output.split("\n"):
            # Detect test execution start
            if any(
                keyword in line.lower()
                for keyword in ["running tests", "pytest", "test suite", "npm test"]
            ):
                test_section_started = True

            if test_section_started:
                test_output += line + "\n"

        # Determine if tests passed
        tests_passed = False

        # Check for passed patterns
        for pattern in test_patterns["passed"]:
            if re.search(pattern, output, re.IGNORECASE):
                tests_passed = True
                break

        # Check for failed patterns (overrides passed)
        for pattern in test_patterns["failed"]:
            if re.search(pattern, output, re.IGNORECASE):
                tests_passed = False
                break

        return tests_passed, test_output.strip()
