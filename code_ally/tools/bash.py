import logging
import os
import re
import shlex
import subprocess
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool
from code_ally.trust import DISALLOWED_COMMANDS, is_command_allowed

# Configure logging
logger = logging.getLogger(__name__)


@register_tool
class BashTool(BaseTool):
    """Tool for executing shell commands safely with enhanced options.

    This tool allows the agent to run shell commands with configurable environment,
    working directory, output structuring, and command chaining options.
    """

    name = "bash"
    description = """Execute a shell command and return its output.
    
    Supports:
    - Working directory selection (working_dir)
    - Environment variable setting (environment)
    - Command piping and chaining (pipe_commands)
    - Timeout controls (timeout)
    - Structured output parsing (structured_output)
    """
    requires_confirmation = True

    # Default timeout for commands
    DEFAULT_TIMEOUT = 5

    # Maximum timeout allowed (in seconds)
    MAX_TIMEOUT = 60

    # Interactive command detection timeout
    INTERACTIVE_CHECK_TIMEOUT = 1.0

    # Default script permissions (rwxr-xr-x)
    DEFAULT_SCRIPT_PERMISSIONS = 0o755

    # Commands that support structured output parsing
    STRUCTURED_OUTPUT_COMMANDS = {
        "git": {
            "status": "_parse_git_status",
            "branch": "_parse_git_branch",
            "log": "_parse_git_log",
        },
        "ls": "_parse_ls",
        "ps": "_parse_ps",
        "pip": "_parse_pip",
        "npm": "_parse_npm",
    }

    def execute(
        self,
        command: str,
        timeout: int = DEFAULT_TIMEOUT,
        working_dir: str = "",
        environment: Optional[Dict[str, str]] = None,
        pipe_commands: bool = False,
        structured_output: bool = False,
        create_script: bool = False,
        script_path: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute a shell command and return its output with enhanced options.

        Args:
            command: The shell command to execute
            timeout: Maximum time in seconds to wait for command completion (default: 5)
            working_dir: Directory to run the command in (default: current directory)
            environment: Environment variables to set for the command
            pipe_commands: Whether to allow pipe operators in commands (|, &&, ||)
            structured_output: Whether to parse the output into a structured format
            create_script: Whether to create a shell script instead of executing directly
            script_path: Path where to save the script if create_script is True
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the command executed successfully
                output: The command's output (stdout)
                error: Error message if any (stderr)
                interactive: Whether the command is waiting for input
                return_code: The command's exit code
                structured: Parsed structured output (if structured_output=True)
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

        # Security check for command piping
        if not pipe_commands and any(op in command for op in ["|", "&&", "||", ";"]):
            logger.warning(
                f"Command contains pipe or chain operators but pipe_commands=False: {command}"
            )
            return self._format_error_response(
                f"Command contains pipe or chain operators ('|', '&&', '||', ';'). "
                f"Set pipe_commands=True to enable this feature."
            ) | {
                "output": "",
                "interactive": False,
                "return_code": -1,
                "structured": None,
            }

        # Security check for command allowlist
        if not is_command_allowed(command):
            disallowed = next(
                (cmd for cmd in DISALLOWED_COMMANDS if cmd in command), ""
            )
            logger.warning(f"Command not allowed: {command}")
            return self._format_error_response(
                f"Command not allowed for security reasons: {command}\n"
                f"Matched disallowed pattern: {disallowed}"
            ) | {
                "output": "",
                "interactive": False,
                "return_code": -1,
                "structured": None,
            }

        # Analyze command to determine how to handle it
        command_info = self._analyze_command(command)

        # Adjust timeout for commands that might need more time
        adjusted_timeout = self._adjust_timeout(command, timeout, command_info)

        # Execute the command based on its characteristics
        try:
            # Prepare environment variables
            env = os.environ.copy()
            if environment:
                env.update(environment)

            # Prepare working directory
            work_dir = os.path.abspath(working_dir) if working_dir else None

            if command_info["likely_interactive"]:
                logger.debug(f"Running command as interactive: {command}")
                result = self._run_interactive_command(
                    command, adjusted_timeout, env, work_dir
                )
            else:
                logger.debug(f"Running command as non-interactive: {command}")
                result = self._run_standard_command(
                    command, adjusted_timeout, env, work_dir
                )

            # Handle structured output parsing if requested
            if structured_output and result.get("success", False):
                structured_result = self._parse_structured_output(
                    command, result.get("output", "")
                )
                result["structured"] = structured_result
            else:
                result["structured"] = None

            return result
        except Exception as e:
            logger.exception(f"Error executing command: {command}")
            return self._format_error_response(f"Error executing command: {str(e)}") | {
                "output": "",
                "interactive": False,
                "return_code": -1,
                "structured": None,
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

        # Extract base command (for structured output)
        base_command = executable
        subcommand = parts[1] if len(parts) > 1 else ""

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
            "mysql",
            "psql",
            "sqlite3",
            "python",
            "node",
            "ipython",
            "jupyter",
        ]
        if executable in interactive_commands:
            likely_interactive = True

        return {
            "executable": executable,
            "base_command": base_command,
            "subcommand": subcommand,
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

        # Extend timeout for potentially long-running commands
        long_running_prefixes = [
            "npm install",
            "pip install",
            "apt",
            "yum",
            "brew",
            "make",
            "mvn",
            "gradle",
        ]
        if any(command.startswith(prefix) for prefix in long_running_prefixes):
            return min(timeout * 3, self.MAX_TIMEOUT)

        return timeout

    def _run_standard_command(
        self, command: str, timeout: int, env: Dict[str, str], cwd: Optional[str]
    ) -> Dict[str, Any]:
        """Run a standard (non-interactive) command.

        Args:
            command: The command to run
            timeout: Command timeout in seconds
            env: Environment variables
            cwd: Working directory

        Returns:
            Command execution result
        """
        try:
            # Run the command with timeout
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=cwd,
            )

            # Format the result
            return (
                self._format_success_response(
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
            ) | {"output": "", "interactive": False, "return_code": -1}

    def _run_interactive_command(
        self, command: str, timeout: int, env: Dict[str, str], cwd: Optional[str]
    ) -> Dict[str, Any]:
        """Run a potentially interactive command and detect if it's waiting for input.

        Args:
            command: The command to run
            timeout: Command timeout in seconds
            env: Environment variables
            cwd: Working directory

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
                env=env,
                cwd=cwd,
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
                    return_code=None,
                    message="This command is interactive and is waiting for user input.",
                )
            else:
                # Process completed
                return_code = process.returncode or 0

                return (
                    self._format_success_response(
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
            ) | {"output": "", "interactive": False, "return_code": -1}

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
                interactive=False,
                return_code=0,
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

    def _parse_structured_output(self, command: str, output: str) -> Dict[str, Any]:
        """Parse command output into a structured format when possible.

        Args:
            command: The command that was executed
            output: The command's output

        Returns:
            Structured data based on the command type
        """
        parts = shlex.split(command)
        if not parts:
            return None

        # Get base command and subcommand if any
        base_cmd = os.path.basename(parts[0])
        subcommand = parts[1] if len(parts) > 1 else ""

        # Check if we have a parser for this command
        if base_cmd in self.STRUCTURED_OUTPUT_COMMANDS:
            cmd_parsers = self.STRUCTURED_OUTPUT_COMMANDS[base_cmd]

            # If it's a dict, check for subcommand parsers
            if isinstance(cmd_parsers, dict):
                if subcommand in cmd_parsers:
                    parser_name = cmd_parsers[subcommand]
                    parser_method = getattr(self, parser_name, None)
                    if parser_method:
                        return parser_method(output)
            # Otherwise use the general parser
            elif isinstance(cmd_parsers, str):
                parser_method = getattr(self, cmd_parsers, None)
                if parser_method:
                    return parser_method(output)

        # If no parser found or parsing fails, return the output as is
        return {"raw": output}

    # Built-in parsers for common commands

    def _parse_git_status(self, output: str) -> Dict[str, Any]:
        """Parse output from 'git status' command."""
        result = {
            "branch": "",
            "is_clean": "working tree clean" in output.lower(),
            "staged": [],
            "unstaged": [],
            "untracked": [],
        }

        # Extract branch name
        branch_match = re.search(r"On branch ([^\n]+)", output)
        if branch_match:
            result["branch"] = branch_match.group(1)

        # Extract staged files
        staged_section = False
        unstaged_section = False
        untracked_section = False

        for line in output.splitlines():
            line = line.strip()

            # Check for section headers
            if "Changes to be committed:" in line:
                staged_section = True
                unstaged_section = False
                untracked_section = False
                continue
            elif "Changes not staged for commit:" in line:
                staged_section = False
                unstaged_section = True
                untracked_section = False
                continue
            elif "Untracked files:" in line:
                staged_section = False
                unstaged_section = False
                untracked_section = True
                continue

            # Skip empty or non-file lines
            if not line or line.startswith("(") or ":" not in line:
                continue

            # Extract file info
            if staged_section and ":" in line:
                status, file = line.split(":", 1)
                result["staged"].append(
                    {"status": status.strip(), "file": file.strip()}
                )
            elif unstaged_section and ":" in line:
                status, file = line.split(":", 1)
                result["unstaged"].append(
                    {"status": status.strip(), "file": file.strip()}
                )
            elif untracked_section and line:
                result["untracked"].append(line)

        return result

    def _parse_git_branch(self, output: str) -> Dict[str, Any]:
        """Parse output from 'git branch' command."""
        branches = []
        current = ""

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("*"):
                # Current branch
                branch_name = line[1:].strip()
                branches.append(branch_name)
                current = branch_name
            else:
                branches.append(line)

        return {"branches": branches, "current": current, "count": len(branches)}

    def _parse_git_log(self, output: str) -> Dict[str, Any]:
        """Parse output from 'git log' command."""
        commits = []
        current_commit = None

        for line in output.splitlines():
            line = line.strip()

            if line.startswith("commit "):
                # Start of a new commit
                if current_commit:
                    commits.append(current_commit)

                current_commit = {
                    "hash": line[7:].strip(),
                    "author": "",
                    "date": "",
                    "message": [],
                }
            elif current_commit and line.startswith("Author: "):
                current_commit["author"] = line[8:].strip()
            elif current_commit and line.startswith("Date: "):
                current_commit["date"] = line[6:].strip()
            elif current_commit and line and not line.startswith("Merge: "):
                current_commit["message"].append(line)

        # Add the last commit
        if current_commit:
            commits.append(current_commit)

        # Join commit messages
        for commit in commits:
            commit["message"] = "\n".join(commit["message"]).strip()

        return {"commits": commits, "count": len(commits)}

    def _parse_ls(self, output: str) -> Dict[str, Any]:
        """Parse output from 'ls' command."""
        files = []
        directories = []

        # Handle 'ls -l' output
        if (
            output
            and "\n" in output
            and any(l.startswith("total ") for l in output.splitlines()[:1])
        ):
            is_detailed = True
            lines = output.splitlines()[1:]  # Skip the "total" line

            for line in lines:
                if not line.strip():
                    continue

                parts = line.split(maxsplit=8)
                if len(parts) >= 9:
                    perms, links, owner, group, size, date1, date2, date3, name = parts
                    item = {
                        "name": name,
                        "permissions": perms,
                        "owner": owner,
                        "group": group,
                        "size": size,
                        "date": f"{date1} {date2} {date3}",
                    }

                    if perms.startswith("d"):
                        directories.append(item)
                    else:
                        files.append(item)
        else:
            # Simple ls output
            is_detailed = False
            for item in output.splitlines():
                item = item.strip()
                if not item:
                    continue

                # Try to detect directories based on trailing slash or colors
                if item.endswith("/") or (item.startswith("\033[") and "m" in item):
                    directories.append({"name": item})
                else:
                    files.append({"name": item})

        return {
            "files": files,
            "directories": directories,
            "is_detailed": is_detailed,
            "total_files": len(files),
            "total_directories": len(directories),
        }

    def _parse_ps(self, output: str) -> Dict[str, Any]:
        """Parse output from 'ps' command."""
        processes = []

        lines = output.splitlines()
        if not lines:
            return {"processes": [], "count": 0}

        # Parse header to get column names
        header = lines[0]
        column_names = header.split()

        # Process each line
        for line in lines[1:]:
            if not line.strip():
                continue

            # Split the line and create a process entry
            values = line.split(None, len(column_names) - 1)
            if len(values) >= len(column_names):
                process = {}
                for i, col in enumerate(column_names):
                    process[col.lower()] = values[i]
                processes.append(process)

        return {"processes": processes, "count": len(processes)}

    def _parse_pip(self, output: str) -> Dict[str, Any]:
        """Parse output from pip commands."""
        packages = []

        if (
            "Requirement already satisfied:" in output
            or "Successfully installed" in output
        ):
            # Installation output
            for line in output.splitlines():
                if line.startswith("Successfully installed "):
                    package_str = line[len("Successfully installed ") :].strip()
                    package_list = package_str.split()
                    for pkg in package_list:
                        if "==" in pkg:
                            name, version = pkg.split("==", 1)
                            packages.append({"name": name, "version": version})
                        else:
                            packages.append({"name": pkg, "version": ""})
        elif "Package" in output and "Version" in output:
            # List output
            in_table = False
            for line in output.splitlines():
                if "----" in line:
                    in_table = True
                    continue

                if in_table and line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        packages.append({"name": parts[0], "version": parts[1]})

        return {"packages": packages, "count": len(packages)}

    def _parse_npm(self, output: str) -> Dict[str, Any]:
        """Parse output from npm commands."""
        result = {
            "packages": [],
            "added": [],
            "removed": [],
            "updated": [],
            "error": "",
        }

        if "ERR!" in output:
            # Error output
            error_lines = []
            for line in output.splitlines():
                if "ERR!" in line:
                    error_lines.append(line)
            result["error"] = "\n".join(error_lines)
        elif "+ " in output or "added " in output:
            # Installation output
            for line in output.splitlines():
                if line.startswith("+ "):
                    pkg = line[2:].strip()
                    if "@" in pkg:
                        name, version = pkg.rsplit("@", 1)
                        result["added"].append({"name": name, "version": version})
                    else:
                        result["added"].append({"name": pkg, "version": ""})
                elif "added" in line and "packages" in line:
                    # Summary line
                    pass

        return result
