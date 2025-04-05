"""Bash tool for executing shell commands.

This module provides the BashTool, which allows the agent to execute shell commands
with safety checks and special handling for interactive commands.
"""

import logging
import os
import shlex

# import signal
# import threading
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool
from code_ally.trust import DISALLOWED_COMMANDS, is_command_allowed

# Configure logging
logger = logging.getLogger(__name__)


@register_tool
class BashTool(BaseTool):
    """Tool for executing shell commands safely.

    This tool allows the agent to run shell commands. It includes safety checks
    to prevent potentially dangerous commands and handles interactive commands
    like those that request user input.
    """

    name = "bash"
    description = "Execute a shell command and return its output"
    requires_confirmation = True

    # Default timeout for commands
    DEFAULT_TIMEOUT = 5

    # Maximum timeout allowed (in seconds)
    MAX_TIMEOUT = 60

    # Interactive command detection timeout
    INTERACTIVE_CHECK_TIMEOUT = 1.0

    # Default script permissions (rwxr-xr-x)
    DEFAULT_SCRIPT_PERMISSIONS = 0o755

    def execute(
        self,
        command: str,
        timeout: int = DEFAULT_TIMEOUT,
        create_script: bool = False,
        script_path: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute a shell command and return its output.

        Args:
            command: The shell command to execute
            timeout: Maximum time in seconds to wait for command completion (default: 5)
            create_script: Whether to create a shell script instead of executing directly
            script_path: Path where to save the script if create_script is True
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the command executed successfully
                output: The command's output (stdout)
                error: Error message if any (stderr)
                interactive: Whether the command is waiting for input
                message: Optional explanatory message about the command execution
                script_path: Path to the created script (if create_script=True)
        """
        # Sanitize and log the command
        command = command.strip()
        logger.info(f"Executing command: {command}")

        # Handle script creation mode
        if create_script:
            return self._create_bash_script(command, script_path)

        # Validate timeout
        timeout = min(max(1, timeout), self.MAX_TIMEOUT)

        # Security check
        if not is_command_allowed(command):
            disallowed = next(
                (cmd for cmd in DISALLOWED_COMMANDS if cmd in command), ""
            )
            logger.warning(f"Command not allowed: {command}")
            return self._format_error_response(
                f"Command not allowed for security reasons: {command}\n"
                f"Matched disallowed pattern: {disallowed}"
            ) | {"output": "", "interactive": False}

        # Analyze command to determine how to handle it
        command_info = self._analyze_command(command)

        # Adjust timeout for commands that might need more time
        adjusted_timeout = self._adjust_timeout(command, timeout, command_info)

        # Execute the command based on its characteristics
        try:
            if command_info["likely_interactive"]:
                logger.debug(f"Running command as interactive: {command}")
                return self._run_interactive_command(command, adjusted_timeout)
            else:
                logger.debug(f"Running command as non-interactive: {command}")
                return self._run_standard_command(command, adjusted_timeout)
        except Exception as e:
            logger.exception(f"Error executing command: {command}")
            return self._format_error_response(f"Error executing command: {str(e)}") | {
                "output": "",
                "interactive": False,
            }

    def _analyze_command(self, command: str) -> Dict[str, Any]:
        """Analyze a command to determine its characteristics.

        Args:
            command: The command to analyze

        Returns:
            Dict with command characteristics
        """
        # Parse the command to get the main executable
        parts = shlex.split(command)
        executable = os.path.basename(parts[0]) if parts else ""

        # Check for Python scripts
        is_python_command = executable == "python" or executable == "python3"
        is_python_script = (
            is_python_command and len(parts) > 1 and parts[1].endswith(".py")
        )
        is_python_module = is_python_command and len(parts) > 1 and ("-m" in parts[:2])
        is_python_code = is_python_command and len(parts) > 1 and ("-c" in parts[:2])

        # Check for likely interactive programs
        likely_interactive = False

        # Python scripts without -c or -m flags are potentially interactive
        if is_python_script and not is_python_module and not is_python_code:
            likely_interactive = True

        # Other known interactive commands
        interactive_commands = [
            "vi",
            "vim",
            "nano",
            "emacs",
            "less",
            "more",
            "top",
            "htop",
        ]
        if executable in interactive_commands:
            likely_interactive = True

        return {
            "executable": executable,
            "is_python_command": is_python_command,
            "is_python_script": is_python_script,
            "likely_interactive": likely_interactive,
        }

    def _adjust_timeout(
        self, command: str, timeout: int, command_info: Dict[str, Any]
    ) -> int:
        """Adjust timeout based on command characteristics.

        Args:
            command: The command to execute
            timeout: The specified timeout
            command_info: Command analysis info

        Returns:
            Adjusted timeout value
        """
        # Extend timeout for Python scripts to ensure they complete
        if command_info["is_python_script"] and timeout == self.DEFAULT_TIMEOUT:
            return min(timeout * 2, self.MAX_TIMEOUT)

        return timeout

    def _run_standard_command(self, command: str, timeout: int) -> Dict[str, Any]:
        """Run a standard (non-interactive) command.

        Args:
            command: The command to run
            timeout: Command timeout in seconds

        Returns:
            Command execution result
        """
        try:
            # Run the command with timeout
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )

            # Format the result
            return (
                self._format_success_response(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    interactive=False,
                    return_code=result.returncode,
                )
                if result.returncode == 0
                else self._format_error_response(
                    f"Command exited with status {result.returncode}: {result.stderr}"
                )
                | {
                    "output": result.stdout,
                    "interactive": False,
                    "return_code": result.returncode,
                }
            )

        except subprocess.TimeoutExpired:
            logger.warning(f"Command timed out after {timeout} seconds: {command}")
            return self._format_error_response(
                f"Command timed out after {timeout} seconds"
            ) | {"output": "", "interactive": False}

    def _run_interactive_command(self, command: str, timeout: int) -> Dict[str, Any]:
        """Run a potentially interactive command and detect if it's waiting for input.

        Args:
            command: The command to run
            timeout: Command timeout in seconds

        Returns:
            Command execution result with interactive flag if appropriate
        """
        try:
            # Start process without waiting for it to complete
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            # Read output with short timeout to detect if it's interactive
            stdout_data, stderr_data = self._read_process_output(
                process, self.INTERACTIVE_CHECK_TIMEOUT
            )

            # If process is still running after the check timeout,
            # it might be waiting for input
            if process.poll() is None:
                # Try to terminate the process gracefully
                self._terminate_process(process)

                return self._format_success_response(
                    output=stdout_data,
                    error=stderr_data,
                    interactive=True,
                    message="This command is interactive and is waiting for user input.",
                )
            else:
                # Process completed
                return_code = process.returncode or 0

                return (
                    self._format_success_response(
                        success=return_code == 0,
                        output=stdout_data,
                        error=stderr_data,
                        interactive=False,
                        return_code=return_code,
                    )
                    if return_code == 0
                    else self._format_error_response(
                        f"Command exited with status {return_code}: {stderr_data}"
                    )
                    | {
                        "output": stdout_data,
                        "interactive": False,
                        "return_code": return_code,
                    }
                )

        except Exception as e:
            logger.exception(f"Error handling interactive command: {command}")
            return self._format_error_response(
                f"Error running potentially interactive command: {str(e)}"
            ) | {"output": "", "interactive": False}

    def _read_process_output(
        self, process: subprocess.Popen, timeout: float
    ) -> Tuple[str, str]:
        """Read available output from a process for a specified time.

        Args:
            process: The subprocess.Popen object
            timeout: How long to read output for

        Returns:
            Tuple of (stdout_data, stderr_data)
        """
        stdout_data = ""
        stderr_data = ""

        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check if process has terminated
            if process.poll() is not None:
                # Get any remaining output
                remaining_out, remaining_err = process.communicate()
                stdout_data += remaining_out
                stderr_data += remaining_err
                break

            # Try to read available output without blocking
            if process.stdout and process.stdout.readable():
                line = process.stdout.readline()
                if line:
                    stdout_data += line

            if process.stderr and process.stderr.readable():
                line = process.stderr.readline()
                if line:
                    stderr_data += line

            # Short sleep to prevent CPU thrashing
            time.sleep(0.05)

        return stdout_data, stderr_data

    def _create_bash_script(
        self, command: str, script_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a bash script with the provided command content.

        Args:
            command: The shell command(s) to include in the script
            script_path: Path where to save the script

        Returns:
            Dict with script creation result
        """
        try:
            # Determine script path if not provided
            if not script_path:
                script_dir = os.getcwd()
                script_name = f"script_{int(time.time())}.sh"
                script_path = os.path.join(script_dir, script_name)

            # Create script content with shebang
            script_content = "#!/bin/bash\n\n"
            script_content += "set -e\n\n"  # Exit on error
            script_content += command

            # Ensure the content ends with a newline
            if not script_content.endswith("\n"):
                script_content += "\n"

            # Write the script file
            script_path = os.path.abspath(script_path)
            os.makedirs(os.path.dirname(script_path), exist_ok=True)

            with open(script_path, "w") as f:
                f.write(script_content)

            # Make the script executable
            os.chmod(script_path, self.DEFAULT_SCRIPT_PERMISSIONS)

            return self._format_success_response(
                output=f"Script created at: {script_path}",
                script_path=script_path,
                message=f"Bash script created successfully at {script_path}",
            )

        except Exception as e:
            logger.exception(f"Error creating bash script: {str(e)}")
            return self._format_error_response(f"Error creating bash script: {str(e)}")

    def _terminate_process(self, process: subprocess.Popen) -> None:
        """Safely terminate a process.

        Args:
            process: The process to terminate
        """
        try:
            # First try SIGTERM for graceful shutdown
            process.terminate()

            # Wait a bit for it to exit
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                # If it doesn't terminate, force kill with SIGKILL
                process.kill()
                process.wait(timeout=0.5)
        except Exception as e:
            logger.warning(f"Error terminating process: {str(e)}")
            # We tried our best, let's move on
