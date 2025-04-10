"""Trust management for security-sensitive operations.

This module provides security features for Code Ally, including:
1. Command allowlist/denylist checking for bash operations
2. User permission management for sensitive operations
3. Path-based trust scoping
4. Directory access restriction (prevents operation outside current working directory)
"""

import logging
import os
import re
import textwrap
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple, Union


class PermissionDeniedError(Exception):
    """Raised when a user denies permission for a tool.

    This special exception allows the agent to immediately stop processing
    and return to the main conversation loop.
    """

    pass


class DirectoryTraversalError(Exception):
    """Raised when an operation attempts to access paths outside of allowed directory.

    This special exception prevents the agent from accessing files or directories
    outside of the current working directory.
    """

    pass


# Configure logging
logger = logging.getLogger(__name__)
# Enable debug logging for trust-related operations
logger.setLevel(logging.DEBUG)

# Commands that are not allowed for security reasons
DISALLOWED_COMMANDS = [
    # Dangerous filesystem operations
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "rm -rf ~/",
    "rm -rf .",
    "rm -rf ./",
    "rm -rf --no-preserve-root /",
    "find / -delete",
    # Dangerous disk operations
    "dd if=/dev/zero",
    "> /dev/sda",
    "mkfs",
    "> /dev/null",
    # Destructive system operations
    ":(){ :|:& };:",  # Fork bomb
    "shutdown",
    "poweroff",
    "reboot",
    # Remote code execution
    "wget -O- | bash",
    "curl | bash",
    "wget | sh",
    "curl | sh",
    "curl -s | bash",
    # Dangerous network tools
    "nc -l",
    "netcat -l",
]

# List of regular expressions for more complex pattern matching
DISALLOWED_PATTERNS = [
    r"rm\s+(-[rRf]+\s+)?(\/|\~\/|\.\/).+",  # Dangerous rm commands
    r"curl\s+.+\s*\|\s*(bash|sh|zsh)",  # Piping curl to shell
    r"wget\s+.+\s*\|\s*(bash|sh|zsh)",  # Piping wget to shell
    r"ssh\s+.+\s+'.*'",  # SSH with commands
    r"eval\s+.+",  # Eval with commands
    r"ls\s+(-[alFhrt]+\s+)?(\.\.|\/|\~)[\/]?",  # List files outside CWD
    r"cat\s+(\.\.|\/|\~)[\/]?",  # Cat files outside CWD
    r"more\s+(\.\.|\/|\~)[\/]?",  # More files outside CWD
    r"less\s+(\.\.|\/|\~)[\/]?",  # Less files outside CWD
    r"head\s+(\.\.|\/|\~)[\/]?",  # Head files outside CWD
    r"tail\s+(\.\.|\/|\~)[\/]?",  # Tail files outside CWD
    r"grep\s+.+\s+(\.\.|\/|\~)[\/]?",  # Grep outside CWD
    r"find\s+(\.\.|\/|\~)[\/]?\s+",  # Find outside CWD
]

# Commands that require extra scrutiny
SENSITIVE_COMMAND_PREFIXES = [
    "sudo ",
    "su ",
    "chown ",
    "chmod ",
    "rm -r",
    "rm -f",
    "mv /* ",
    "cp /* ",
    "ln -s ",
    "wget ",
    "curl ",
    "ssh ",
    "scp ",
    "rsync ",
    "ls ..",
    "ls ../",
    "ls /",
    "ls ~/",
    "cat ../",
    "cat /",
    "cat ~/",
    "grep ../",
    "grep /",
    "grep ~/",
    "find ../",
    "find /",
    "find ~/",
    "head ../",
    "head /",
    "head ~/",
    "tail ../",
    "tail /",
    "tail ~/",
]

# Compile the disallowed patterns for efficiency
COMPILED_DISALLOWED_PATTERNS = [re.compile(pattern) for pattern in DISALLOWED_PATTERNS]


class PermissionScope(Enum):
    """Permission scope levels for trust management."""

    GLOBAL = auto()  # Trust for all paths and instances
    SESSION = auto()  # Trust for the current session only (all paths)
    DIRECTORY = auto()  # Trust for a specific directory and its subdirectories
    FILE = auto()  # Trust for a specific file only
    ONCE = auto()  # Trust for this one call only


@dataclass
class ToolPermission:
    """Represents a permission for a specific tool."""

    tool_name: str
    scope: PermissionScope
    path: Optional[str] = None  # Relevant for DIRECTORY and FILE scopes
    operation_id: Optional[str] = None  # Unique identifier for batch operations


def is_path_within_cwd(path: str) -> bool:
    """Check if a path is within the current working directory.

    Args:
        path: The path to check

    Returns:
        True if the path is within CWD, False otherwise
    """
    try:
        # Get the absolute path and normalize it
        abs_path = os.path.abspath(path)
        # Get the current working directory
        cwd = os.path.abspath(os.getcwd())

        # Check if the path starts with CWD
        # This ensures the path is within the current working directory or its subdirectories
        return abs_path.startswith(cwd)
    except Exception as e:
        logger.warning(f"Error checking path traversal: {e}")
        # If there's an error, assume it's not safe
        return False


def has_path_traversal_patterns(input_str: str) -> bool:
    """Check if a string contains path traversal patterns.

    Args:
        input_str: The string to check

    Returns:
        True if the string contains path traversal patterns, False otherwise
    """
    if not input_str:
        return False

    traversal_patterns = [
        "..",
        "/../",
        "/./",
        "~/",
        "$HOME",
        "${HOME}",
        "$(pwd)",
        "`pwd`",
        "/etc/",
        "/var/",
        "/usr/",
        "/bin/",
        "/tmp/",
        "/root/",
        "/proc/",
        "/sys/",
        "/dev/",
        "/*",
        "~/*",
    ]

    # Check for direct absolute paths
    if input_str.startswith("/") or input_str.startswith("~"):
        return True

    # Check for common path traversal patterns
    for pattern in traversal_patterns:
        if pattern in input_str:
            return True

    # Check for environment variable usage that could lead to path traversal
    if "$(" in input_str or "`" in input_str or "${" in input_str:
        return True

    return False


def sanitize_command_for_path_traversal(command: str) -> bool:
    """Check if a command contains path traversal attempts.

    Args:
        command: The command to check

    Returns:
        True if command is safe, False if it contains path traversal
    """
    # Common commands that involve file access
    file_access_commands = [
        "ls",
        "cat",
        "more",
        "less",
        "head",
        "tail",
        "touch",
        "mkdir",
        "rm",
        "cp",
        "mv",
        "echo",
        "nano",
        "vim",
        "vi",
        "emacs",
        "find",
        "grep",
        "awk",
        "sed",
        "diff",
        "chmod",
        "chown",
        "stat",
        "file",
        "wc",
        "cd",
        "source",
        ".",
        "exec",
        "python",
        "python3",
        "python2",
        "ruby",
        "perl",
        "node",
        "npm",
        "yarn",
    ]

    # Split command into parts
    parts = command.split()
    if not parts:
        return True

    for i, part in enumerate(parts):
        # Skip options/flags (arguments that start with -)
        if part.startswith("-"):
            continue

        # Check for path traversal in parts
        if has_path_traversal_patterns(part):
            command_name = parts[0] if parts else ""
            logger.warning(f"Path traversal pattern detected in command: {command}")
            return False

        # Extra checks for more targeted file operations
        if i > 0 and parts[0] in file_access_commands:
            # If this part appears to be a path argument
            if not part.startswith("-"):
                # Check if it's an absolute path or contains traversal
                if has_path_traversal_patterns(part):
                    logger.warning(
                        f"Path traversal pattern detected in argument: {part}"
                    )
                    return False

                # Final verification for paths that might slip through
                if os.path.isabs(part):
                    if not is_path_within_cwd(part):
                        logger.warning(f"Path outside CWD detected in command: {part}")
                        return False

    return True


def is_command_allowed(command: str) -> bool:
    """Check if a command is allowed to execute.

    Args:
        command: The command to check

    Returns:
        True if the command is allowed, False otherwise
    """
    if not command or not command.strip():
        return False

    normalized_command = command.strip().lower()

    # Check against explicit disallowed commands
    for disallowed in DISALLOWED_COMMANDS:
        if disallowed in normalized_command:
            logger.warning(
                f"Command rejected - matched disallowed pattern: {disallowed}"
            )
            return False

    # Check against regex patterns
    for pattern in COMPILED_DISALLOWED_PATTERNS:
        if pattern.search(normalized_command):
            logger.warning(
                f"Command rejected - matched regex pattern: {pattern.pattern}"
            )
            return False

    # Check for dangerous shell operations
    if "|" in command and ("bash" in command or "sh" in command):
        if "curl" in command or "wget" in command:
            logger.warning("Command rejected - piping curl/wget to bash")
            return False

    # Block commands that would allow viewing files outside CWD
    if not sanitize_command_for_path_traversal(command):
        logger.warning(f"Command rejected - contains path traversal: {command}")
        return False

    # Check for directory traversal attempts
    if "cd" in normalized_command:
        # Extract the directory path from cd command
        parts = command.split("cd ", 1)
        if len(parts) > 1:
            dir_path = parts[1].strip().split()[0]  # Get the first argument after cd
            # Remove quotes if present
            dir_path = dir_path.strip("\"'")

            # Special cases that could lead to directory traversal
            if (
                dir_path == ".."
                or dir_path.startswith("../")
                or dir_path.startswith("/")
                or dir_path.startswith("~")
            ):
                logger.warning(f"Directory traversal attempt detected: {command}")
                return False

            # For relative paths, ensure they don't escape CWD
            if not is_path_within_cwd(dir_path):
                logger.warning(
                    f"Command rejected - would navigate outside CWD: {command}"
                )
                return False

    # Log if this is a sensitive command
    for prefix in SENSITIVE_COMMAND_PREFIXES:
        if normalized_command.startswith(prefix):
            logger.info(
                f"Executing sensitive command (starts with '{prefix}'): {command}"
            )
            break

    # If we passed all checks, the command is allowed
    return True


class TrustManager:
    """Manages trust for tools that need user confirmation."""

    def __init__(self):
        """Initialize the trust manager."""
        # Track trusted tools by name and path
        self.trusted_tools: Dict[str, Set[str]] = {}
        # Auto-confirm flag (dangerous, but useful for scripting)
        self.auto_confirm = False
        # Track pre-approved operations (simpler implementation)
        self.pre_approved_operations: Set[str] = set()

        logger.debug("TrustManager initialized")

    def set_auto_confirm(self, value: bool) -> None:
        """Set the auto-confirm flag."""
        previous = self.auto_confirm
        self.auto_confirm = value
        logger.info(f"Auto-confirm changed from {previous} to {value}")

    def get_operation_key(self, tool_name: str, path: Optional[Any] = None) -> str:
        """Generate a unique key for a tool and path combination."""
        # Special handling for bash commands (simplified)
        if tool_name == "bash":
            if isinstance(path, dict) and "command" in path:
                command = path["command"]
                return f"{tool_name}:{command[:50]}"  # Truncate long commands
            elif isinstance(path, str):
                return f"{tool_name}:{path[:50]}"  # Truncate long commands

        # If path is None, just use the tool name
        if path is None:
            return tool_name

        # If path is a string, normalize it
        if isinstance(path, str):
            try:
                return f"{tool_name}:{os.path.abspath(path)}"
            except (TypeError, ValueError):
                return f"{tool_name}:{path}"

        # For other types, just return the tool name
        return tool_name

    def is_trusted(self, tool_name: str, path: Optional[Any] = None) -> bool:
        """Check if a tool is trusted for the given path."""
        # Always trust in auto-confirm mode
        if self.auto_confirm:
            return True

        logger.debug(f"Checking trust for {tool_name} at path: {path}")

        # Check if this specific operation has been pre-approved
        operation_key = self.get_operation_key(tool_name, path)
        if operation_key in self.pre_approved_operations:
            logger.debug(f"Operation {operation_key} is pre-approved")
            return True

        # Check if the tool is in the globally trusted dictionary
        if tool_name not in self.trusted_tools:
            logger.debug(f"Tool {tool_name} is not generally trusted")
            return False

        # Check for global trust (all paths)
        trusted_paths = self.trusted_tools[tool_name]
        if "*" in trusted_paths:
            logger.debug(f"Tool {tool_name} has global trust")
            return True

        # If no path provided, and no global trust, then not trusted
        if path is None:
            logger.debug(f"Tool {tool_name} has no global trust and no path specified")
            return False

        # Check for specific path trust
        if isinstance(path, (str, bytes, os.PathLike)):
            try:
                normalized_path = os.path.abspath(path)
                if normalized_path in trusted_paths:
                    logger.debug(f"Found exact path match for {normalized_path}")
                    return True

                # Check for parent directories
                path_parts = normalized_path.split(os.sep)
                current_check_path = ""
                for part in path_parts:
                    if not part:  # Handles leading '/'
                        current_check_path = os.sep
                        continue
                    if current_check_path.endswith(os.sep):
                        current_check_path += part
                    else:
                        current_check_path = os.path.join(current_check_path, part)

                    if current_check_path and current_check_path in trusted_paths:
                        logger.debug(
                            f"Found parent directory match: {current_check_path}"
                        )
                        return True
            except (TypeError, ValueError):
                logger.debug(f"Could not normalize path: {path}")
                return False
        else:
            logger.debug(f"Path for {tool_name} is not a string, skipping path checks.")

        logger.debug(f"No specific trust found for {tool_name} at path {path}")
        return False

    def mark_operation_as_approved(
        self, tool_name: str, path: Optional[Any] = None
    ) -> None:
        """Mark a specific operation as pre-approved."""
        operation_key = self.get_operation_key(tool_name, path)
        self.pre_approved_operations.add(operation_key)
        logger.debug(f"Marked operation as pre-approved: {operation_key}")

    def clear_approved_operations(self) -> None:
        """Clear all pre-approved operations."""
        self.pre_approved_operations.clear()
        logger.debug("Cleared all pre-approved operations")

    def trust_tool(self, tool_name: str, path: Optional[str] = None) -> None:
        """Mark a tool as trusted for the given path."""
        if tool_name not in self.trusted_tools:
            self.trusted_tools[tool_name] = set()

        if path is None:
            logger.info(f"Trusting {tool_name} for all paths (session scope)")
            self.trusted_tools[tool_name].add("*")  # Trust for all paths
        else:
            try:
                normalized_path = os.path.abspath(path)
                logger.info(f"Trusting {tool_name} for path: {normalized_path}")
                self.trusted_tools[tool_name].add(normalized_path)
            except (TypeError, ValueError):
                logger.warning(f"Could not normalize path for trusting: {path}")

    def prompt_for_permission(self, tool_name: str, path: Optional[Any] = None) -> bool:
        """Prompt the user for permission to use a tool.

        Returns whether permission was granted. Default is now NO for safety.

        Raises PermissionDeniedError if permission is denied
        """
        # If auto-confirm is enabled or tool is already trusted, skip the prompt
        if self.auto_confirm:
            logger.info(f"Auto-confirming {tool_name} for {path}")
            return True

        # Check if this tool+path is already trusted
        if self.is_trusted(tool_name, path):
            logger.info(f"Tool {tool_name} is already trusted for {path}")
            return True

        # Build the prompt message
        path_display = path if path else "unknown path"

        # For bash tool, handle differently
        if tool_name == "bash" and isinstance(path, dict) and "command" in path:
            command = path["command"]
            prompt = f"Allow {tool_name} to execute command:\n\n{command}"
        elif tool_name == "bash" and isinstance(path, str) and path.strip():
            command = path
            prompt = f"Allow {tool_name} to execute command:\n\n{command}"
        elif path:
            prompt = f"Allow {tool_name} to access {path_display}?"
        else:
            prompt = f"Allow {tool_name} to execute?"

        logger.info(f"Prompting user for permission: {prompt}")

        # Show a visually distinct prompt
        import sys

        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()
        panel_text = Text()

        # Different styling for bash commands
        if tool_name == "bash":
            from rich.console import Group
            from rich.syntax import Syntax

            panel_text.append(
                f"🔐 PERMISSION REQUIRED - BASH COMMAND\n\n", style="bold yellow"
            )

            # Get the command to display
            if isinstance(path, dict) and "command" in path:
                command = path["command"]
            elif isinstance(path, str) and path.strip():
                command = path
            else:
                command = "Unknown command"

            # Format command with syntax highlighting
            command_syntax = Syntax(command, "bash", theme="monokai", word_wrap=True)

            # Create a prompt text component
            prompt_text = Text()
            prompt_text.append("Press ", style="dim")
            prompt_text.append("y", style="bold green")
            prompt_text.append(" for YES, ", style="dim")
            prompt_text.append("ENTER or n", style="bold red")
            prompt_text.append(" for NO, ", style="dim")
            prompt_text.append("a", style="bold blue")
            prompt_text.append(" for ALWAYS ALLOW", style="dim")

            # Create a group with proper renderable items
            panel_content = Group(
                Text(
                    "You are about to execute the following command:",
                    style="bold white",
                ),
                Text(""),  # Empty line as spacer
                command_syntax,
                Text(""),  # Empty line as spacer
                prompt_text,
            )

            console.print(
                Panel(
                    panel_content,
                    title="[bold yellow]🔐 PERMISSION REQUIRED[/]",
                    border_style="yellow",
                    expand=False,
                )
            )

            # Read input with default to no (just pressing enter)
            sys.stdout.write("> ")
            sys.stdout.flush()
            permission = input().lower()

            if permission == "y" or permission == "yes":
                logger.info(f"User granted one-time permission for {tool_name}")
                return True
            elif permission == "a" or permission == "always":
                logger.info(f"User granted permanent permission for {tool_name}")
                # For bash command, just trust the tool itself rather than the specific command
                if tool_name == "bash" and isinstance(path, dict):
                    self.trust_tool(tool_name)
                else:
                    self.trust_tool(tool_name, path)
                return True
            else:
                # Default to no for empty or invalid response
                logger.info(f"User denied permission for {tool_name}")
                console.print(
                    "\n[bold yellow]Permission denied. Enter a new message.[/]"
                )
                raise PermissionDeniedError(f"User denied permission for {tool_name}")
        else:
            # Standard permission panel for other tools
            panel_text.append(f"🔐 PERMISSION REQUIRED\n\n", style="bold yellow")
            panel_text.append(f"{prompt}\n\n", style="bold white")
            panel_text.append("Press ", style="dim")
            panel_text.append("y", style="bold green")
            panel_text.append(" for YES, ", style="dim")
            panel_text.append("ENTER or n", style="bold red")
            panel_text.append(" for NO, ", style="dim")
            panel_text.append("a", style="bold blue")
            panel_text.append(" for ALWAYS ALLOW", style="dim")

            console.print(Panel(panel_text, border_style="yellow", expand=False))

        # Read input with default to no (just pressing enter)
        sys.stdout.write("> ")
        sys.stdout.flush()
        permission = input().lower()

        if permission == "y" or permission == "yes":
            logger.info(f"User granted one-time permission for {tool_name}")
            return True
        elif permission == "a" or permission == "always":
            logger.info(f"User granted permanent permission for {tool_name}")
            self.trust_tool(tool_name)
            return True
        else:
            # Default to no for empty or invalid response
            logger.info(f"User denied permission for {tool_name}")
            console.print("\n[bold yellow]Permission denied. Enter a new message.[/]")
            raise PermissionDeniedError(f"User denied permission for {tool_name}")

    def prompt_for_parallel_operations(
        self, operations: List[Tuple[str, Any]], operations_text: str
    ) -> bool:
        """Prompt for permission to perform multiple operations at once."""
        # If auto-confirm is enabled, skip the prompt
        if self.auto_confirm:
            logger.info(f"Auto-confirming {len(operations)} parallel operations")
            # Mark operations as approved
            for tool_name, path in operations:
                self.mark_operation_as_approved(tool_name, path)
            return True

        # Create a visually distinct panel for the permission prompt
        import sys

        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()
        panel_text = Text()
        panel_text.append(
            f"🔐 PARALLEL OPERATIONS - PERMISSION REQUIRED\n\n", style="bold yellow"
        )
        panel_text.append(f"{operations_text}\n\n", style="bold white")
        panel_text.append("Press ", style="dim")
        panel_text.append("y", style="bold green")
        panel_text.append(" for YES, ", style="dim")
        panel_text.append("ENTER or n", style="bold red")
        panel_text.append(" for NO", style="dim")

        console.print(Panel(panel_text, border_style="yellow", expand=False))

        # Read input with default to no (just pressing enter)
        sys.stdout.write("> ")
        sys.stdout.flush()
        permission = input().lower()

        if permission == "y" or permission == "yes":
            logger.info(
                f"User granted permission for {len(operations)} parallel operations"
            )
            # Mark all operations as approved
            for tool_name, path in operations:
                self.mark_operation_as_approved(tool_name, path)
            return True
        else:
            # Default to no for empty or invalid response
            logger.info(
                f"User denied permission for {len(operations)} parallel operations"
            )
            console.print("\n[bold yellow]Permission denied. Enter a new message.[/]")
            raise PermissionDeniedError(
                "User denied permission for parallel operations"
            )

    def get_permission_description(self, tool_name: str) -> str:
        """Get a human-readable description of the permissions for a tool."""
        if self.auto_confirm:
            return f"Tool '{tool_name}' has auto-confirm enabled (all actions allowed)"

        if tool_name not in self.trusted_tools:
            return f"Tool '{tool_name}' requires confirmation for all actions"

        paths = self.trusted_tools[tool_name]

        if "*" in paths:
            return f"Tool '{tool_name}' is trusted for all paths"

        if not paths:
            return f"Tool '{tool_name}' requires confirmation for all actions"

        # Format the list of trusted paths
        path_list = "\n  - ".join(sorted(paths))
        return (
            f"Tool '{tool_name}' is trusted for the following paths:\n  - {path_list}"
        )
