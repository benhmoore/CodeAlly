"""Trust management for security-sensitive operations.

This module provides security features for Code Ally, including:
1. Command allowlist/denylist checking for bash operations
2. User permission management for sensitive operations
3. Path-based trust scoping
"""

import logging
import os
import re
import textwrap
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple, Union

# Configure logging
logger = logging.getLogger(__name__)

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
    """Manages trust for tools that need user confirmation.

    This class handles permission decisions for security-sensitive operations,
    allowing the user to grant permissions at various scopes (one-time, session,
    directory, etc.) and persisting those decisions as appropriate.
    """

    def __init__(self):
        """Initialize the trust manager."""
        # Track trusted tools by name and path
        self.trusted_tools: Dict[str, Set[str]] = {}

        # Auto-confirm flag (dangerous, but useful for scripting)
        self.auto_confirm = False

        # Track approved batch operations
        self.approved_operations: Dict[str, Set[str]] = {}

        logger.debug("TrustManager initialized")

    def set_auto_confirm(self, value: bool) -> None:
        """Set the auto-confirm flag.

        Args:
            value: Whether to automatically confirm all actions
        """
        previous = self.auto_confirm
        self.auto_confirm = value
        logger.info(f"Auto-confirm changed from {previous} to {value}")

    def is_trusted(
        self,
        tool_name: str,
        path: Optional[str] = None,
        operation_id: Optional[str] = None,  # This is the batch_id
    ) -> bool:
        """Check if a tool is trusted for the given path or operation ID.

        Args:
            tool_name: The name of the tool
            path: The path being accessed (if applicable)
            operation_id: The unique identifier for batch operations

        Returns:
            Whether the tool is trusted for the path or operation
        """
        # Always trust in auto-confirm mode
        if self.auto_confirm:
            return True

        logger.debug(
            f"Checking trust for {tool_name} at path: {path} (Op ID: {operation_id})"
        )  # Added Op ID to log

        # PRIORITY 1: Check if the specific operation was approved in a batch
        if operation_id and operation_id in self.approved_operations:
            tool_path_key = self._get_tool_path_key(tool_name, path)
            if tool_path_key in self.approved_operations[operation_id]:
                logger.debug(
                    f"Operation {operation_id} is approved for {tool_path_key}"
                )
                return True

        # Check if the tool is in the globally trusted dictionary
        if tool_name not in self.trusted_tools:
            logger.debug(f"Tool {tool_name} is not generally trusted")
            return False

        # At this point, the tool *might* be generally trusted for some paths
        trusted_paths = self.trusted_tools[tool_name]

        # Global trust (all paths)?
        if "*" in trusted_paths:
            logger.debug(f"Tool {tool_name} has global trust")
            return True

        # If no path provided, and no global trust, then not trusted for session
        if path is None:
            logger.debug(f"Tool {tool_name} has no global trust and no path specified")
            return False

        # Check for the specific path trust
        if isinstance(path, (str, bytes, os.PathLike)):
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
                    logger.debug(f"Found parent directory match: {current_check_path}")
                    return True
        else:
            logger.debug(f"Path for {tool_name} is not a string, skipping path checks.")

        logger.debug(f"No specific trust found for {tool_name} at path {path}")
        return False

    def _get_tool_path_key(self, tool_name: str, path: Optional[Any] = None) -> str:
        """Generate a unique key for a tool and path combination.

        Args:
            tool_name: The name of the tool
            path: The path being accessed (if applicable, could be dict for bash)

        Returns:
            A unique key representing the tool and path combination
        """
        # If path is None or not a string (e.g., dict for bash command args),
        # just use the tool name as the key component.
        if path is None or not isinstance(path, (str, bytes, os.PathLike)):
            return tool_name
        # Only call abspath if path is a valid path type
        return f"{tool_name}:{os.path.abspath(path)}"

    def trust_tool(self, tool_name: str, path: Optional[str] = None) -> None:
        """Mark a tool as trusted for the given path.

        Args:
            tool_name: The name of the tool
            path: The path to trust (if None, trust for the session)
        """
        if tool_name not in self.trusted_tools:
            self.trusted_tools[tool_name] = set()

        if path is None:
            logger.info(f"Trusting {tool_name} for all paths (session scope)")
            self.trusted_tools[tool_name].add("*")  # Trust for all paths
        else:
            normalized_path = os.path.abspath(path)
            logger.info(f"Trusting {tool_name} for path: {normalized_path}")
            self.trusted_tools[tool_name].add(normalized_path)

    def prompt_for_permission(self, tool_name: str, path: Optional[str] = None) -> bool:
        """Prompt the user for permission to use a tool.

        Args:
            tool_name: The name of the tool
            path: The path being accessed (if applicable)

        Returns:
            Whether permission was granted
        """
        # If auto-confirm is enabled or tool is already trusted, skip the prompt
        if self.auto_confirm:
            logger.info(f"Auto-confirming {tool_name} for {path}")
            return True

        if self.is_trusted(tool_name, path):
            logger.info(f"Tool {tool_name} is already trusted for {path}")
            return True

        # Build the prompt message with visual emphasis and special handling for bash
        path_display = path if path else "unknown path"

        # For bash tool, we handle it differently
        if tool_name == "bash" and isinstance(path, dict) and "command" in path:
            # Extract the command from the path (which is actually a dict for bash)
            command = path["command"]
            prompt = f"Allow {tool_name} to execute command:\n\n{command}"
        elif tool_name == "bash" and isinstance(path, str) and path.strip():
            # For backwards compatibility, sometimes path is the command directly
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

        # Create a visually distinct panel for the permission prompt
        panel_text = Text()

        # Different styling for bash commands
        if tool_name == "bash":
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

            # Create the panel with the command highlighted
            # Rich expects specific renderable types, we need to create a Group
            from rich.console import Group

            # Create a prompt text component
            prompt_text = Text()
            prompt_text.append("Press ", style="dim")
            prompt_text.append("ENTER", style="bold green")
            prompt_text.append(" for YES, ", style="dim")
            prompt_text.append("n", style="bold red")
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

            # Return after this panel since we already displayed custom formatting
            # Read input with default to yes (just pressing enter)
            sys.stdout.write("> ")
            sys.stdout.flush()
            permission = input().lower()

            if permission == "" or permission == "y" or permission == "yes":
                logger.info(f"User granted one-time permission for {tool_name}")
                return True
            elif permission == "n" or permission == "no":
                logger.info(f"User denied permission for {tool_name}")
                return False
            elif permission == "a" or permission == "always":
                logger.info(f"User granted permanent permission for {tool_name}")
                # For bash command, just trust the tool itself rather than the specific command
                if tool_name == "bash" and isinstance(path, dict):
                    self.trust_tool(tool_name)
                else:
                    self.trust_tool(tool_name, path)
                return True
            else:
                console.print("[yellow]Invalid response. Using default (yes).[/]")
                logger.warning(
                    f"Invalid response to permission prompt, using default (yes)"
                )
                return True
        else:
            # Standard permission panel for other tools
            panel_text.append(f"🔐 PERMISSION REQUIRED\n\n", style="bold yellow")
            panel_text.append(f"{prompt}\n\n", style="bold white")
            panel_text.append("Press ", style="dim")
            panel_text.append("ENTER", style="bold green")
            panel_text.append(" for YES, ", style="dim")
            panel_text.append("n", style="bold red")
            panel_text.append(" for NO, ", style="dim")
            panel_text.append("a", style="bold blue")
            panel_text.append(" for ALWAYS ALLOW", style="dim")

            console.print(Panel(panel_text, border_style="yellow", expand=False))

        # Read input with default to yes (just pressing enter)
        sys.stdout.write("> ")
        sys.stdout.flush()
        permission = input().lower()

        if permission == "" or permission == "y" or permission == "yes":
            logger.info(f"User granted one-time permission for {tool_name}")
            return True
        elif permission == "n" or permission == "no":
            logger.info(f"User denied permission for {tool_name}")
            return False
        elif permission == "a" or permission == "always":
            logger.info(f"User granted permanent permission for {tool_name}")
            # Just trust the tool itself rather than the specific path
            self.trust_tool(tool_name)
            return True
        else:
            console.print("[yellow]Invalid response. Using default (yes).[/]")
            logger.warning(
                f"Invalid response to permission prompt, using default (yes)"
            )
            return True

    def prompt_for_parallel_operations(
        self, operations: List[Tuple[str, Any]], operations_text: str, batch_id: str
    ) -> bool:
        """Prompt the user for permission to perform multiple operations at once.

        Args:
            operations: List of tuples containing tool names and paths
            operations_text: Description of all operations that need permission
            batch_id: The unique identifier for this batch of operations

        Returns:
            Whether permission was granted
        """
        # If auto-confirm is enabled, skip the prompt
        if self.auto_confirm:
            logger.info(
                f"Auto-confirming {len(operations)} parallel operations (ID: {batch_id})"
            )
            # Still need to populate the approved cache even in auto-confirm mode
            self.approved_operations[batch_id] = set()
            for tool_name, path in operations:
                tool_path_key = self._get_tool_path_key(tool_name, path)
                self.approved_operations[batch_id].add(tool_path_key)
            return True

        # Create a visually distinct panel for the permission prompt
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
        panel_text.append("ENTER", style="bold green")
        panel_text.append(" for YES, ", style="dim")
        panel_text.append("n", style="bold red")
        panel_text.append(" for NO", style="dim")

        console.print(Panel(panel_text, border_style="yellow", expand=False))

        # Read input with default to yes (just pressing enter)
        import sys

        sys.stdout.write("> ")
        sys.stdout.flush()
        permission = input().lower()

        if permission == "" or permission == "y" or permission == "yes":
            logger.info(
                f"User granted permission for {len(operations)} parallel operations (ID: {batch_id})"
            )
            self.approved_operations[batch_id] = set()
            for tool_name, path in operations:
                tool_path_key = self._get_tool_path_key(tool_name, path)
                self.approved_operations[batch_id].add(tool_path_key)
            return True
        else:
            logger.info(
                f"User denied permission for {len(operations)} parallel operations (ID: {batch_id})"
            )
            return False

    def get_permission_description(self, tool_name: str) -> str:
        """Get a human-readable description of the permissions for a tool.

        Args:
            tool_name: The name of the tool

        Returns:
            A string describing the trust status of the tool
        """
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
