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
from typing import Dict, List, Optional, Pattern, Set, Tuple, Union

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
    expires_at: Optional[float] = None  # Unix timestamp for expiration


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

        logger.debug("TrustManager initialized")

    def set_auto_confirm(self, value: bool) -> None:
        """Set the auto-confirm flag.

        Args:
            value: Whether to automatically confirm all actions
        """
        previous = self.auto_confirm
        self.auto_confirm = value
        logger.info(f"Auto-confirm changed from {previous} to {value}")

    def is_trusted(self, tool_name: str, path: Optional[str] = None) -> bool:
        """Check if a tool is trusted for the given path.

        Args:
            tool_name: The name of the tool
            path: The path being accessed (if applicable)

        Returns:
            Whether the tool is trusted for the path
        """
        # Always trust in auto-confirm mode
        if self.auto_confirm:
            return True

        logger.debug(f"Checking trust for {tool_name} at path: {path}")

        # Check if the tool is in the trusted dictionary
        if tool_name not in self.trusted_tools:
            logger.debug(f"Tool {tool_name} is not in the trusted_tools dictionary")
            return False

        # If no path provided, check if trusted for all paths (session scope)
        if path is None:
            is_trusted = "*" in self.trusted_tools[tool_name]
            logger.debug(f"Tool {tool_name} trusted for all paths: {is_trusted}")
            return is_trusted

        # At this point, we have a path and the tool is in the trusted list
        trusted_paths = self.trusted_tools[tool_name]

        # Global trust (all paths)
        if "*" in trusted_paths:
            logger.debug(f"Tool {tool_name} has global trust")
            return True

        # Check for the specific path
        normalized_path = os.path.abspath(path)
        if normalized_path in trusted_paths:
            logger.debug(f"Found exact path match for {normalized_path}")
            return True

        # Check for parent directories
        path_parts = normalized_path.split(os.sep)
        for i in range(len(path_parts)):
            parent_path = os.sep.join(path_parts[: i + 1])
            if parent_path and parent_path in trusted_paths:
                logger.debug(f"Found parent directory match: {parent_path}")
                return True

        logger.debug(f"No trust found for {tool_name} at path {path}")
        return False

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
