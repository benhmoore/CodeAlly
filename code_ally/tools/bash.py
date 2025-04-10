"""BashTool class for executing shell commands safely."""

import logging
import os
import subprocess
from typing import Any

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool
from code_ally.trust import DISALLOWED_COMMANDS, is_command_allowed

# Configure logging
logger = logging.getLogger(__name__)


@register_tool
class BashTool(BaseTool):
    """Tool for executing shell commands safely."""

    name = "bash"
    description = """Execute a shell command and return its output.

    <tool_call>
    {"name": "bash", "arguments": {"command": "ls -la", "working_dir": "/path/to/dir", "timeout": 10}}
    </tool_call>
    
    Supports:
    - Working directory selection (working_dir)
    - Timeout controls (timeout)
    """
    requires_confirmation = True

    # Default timeout for commands
    DEFAULT_TIMEOUT = 5

    # Maximum timeout allowed (in seconds)
    MAX_TIMEOUT = 60

    def execute(
        self,
        command: str,
        timeout: int = DEFAULT_TIMEOUT,
        working_dir: str = "",
        **kwargs: dict[str, object],
    ) -> dict[str, Any]:
        """Execute a shell command and return its output.

        Args:
            command: The shell command to execute
            timeout: Maximum time in seconds to wait for command completion (default: 5)
            working_dir: Directory to run the command in (default: current directory)
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the command executed successfully
                output: The command's output (stdout)
                error: Error message if any (stderr)
                return_code: The command's exit code
        """
        # Sanitize and log the command
        command = command.strip()
        logger.info(f"Executing command: {command}")

        # Verify working directory is within allowed bounds
        if working_dir:
            try:
                abs_working_dir = os.path.abspath(working_dir)
                current_dir = os.path.abspath(os.getcwd())

                if not abs_working_dir.startswith(current_dir):
                    logger.warning(
                        f"Directory traversal attempt detected: {working_dir}",
                    )
                    return self._format_error_response(
                        f"Access denied: The working directory '{working_dir}' is outside "
                        f"the current working directory '{current_dir}'. Operations are "
                        f"restricted to the starting directory and its subdirectories.",
                    ) | {
                        "output": "",
                        "return_code": -1,
                    }
            except Exception as e:
                logger.warning(f"Error checking working directory: {e}")
                return self._format_error_response(
                    f"Error validating working directory: {str(e)}",
                ) | {
                    "output": "",
                    "return_code": -1,
                }

        # Validate timeout
        timeout = min(max(1, timeout), self.MAX_TIMEOUT)

        # Security check for command allowlist
        if not is_command_allowed(command):
            disallowed = next(
                (cmd for cmd in DISALLOWED_COMMANDS if cmd in command),
                "",
            )
            logger.warning(f"Command not allowed: {command}")
            return self._format_error_response(
                f"Command not allowed for security reasons: {command}\n"
                f"Matched disallowed pattern: {disallowed}",
            ) | {
                "output": "",
                "return_code": -1,
            }

        # Execute the command
        try:
            # Prepare working directory
            work_dir = os.path.abspath(working_dir) if working_dir else None

            # Run the command with timeout
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=work_dir,
            )

            # Format the result
            return (
                self._format_success_response(
                    output=result.stdout,
                    error=result.stderr,
                    return_code=result.returncode,
                )
                if result.returncode == 0
                else self._format_error_response(
                    f"Command exited with status {result.returncode}: {result.stderr}",
                )
                | {
                    "output": result.stdout,
                    "return_code": result.returncode,
                }
            )

        except subprocess.TimeoutExpired:
            logger.warning(f"Command timed out after {timeout} seconds: {command}")
            return self._format_error_response(
                f"Command timed out after {timeout} seconds",
            ) | {"output": "", "return_code": -1}
        except Exception as e:
            logger.exception(f"Error executing command: {command}")
            return self._format_error_response(f"Error executing command: {str(e)}") | {
                "output": "",
                "return_code": -1,
            }
