"""Permission management for Code Ally tools."""

import logging
import os
import re
from typing import Any

from code_ally.trust import (
    DirectoryTraversalError,
    TrustManager,
    has_path_traversal_patterns,
)

logger = logging.getLogger(__name__)


class PermissionManager:
    """Manages permission checks for tools."""

    def __init__(self, trust_manager: TrustManager) -> None:
        """Initialize the permission manager."""
        self.trust_manager = trust_manager
        # Store the starting directory at initialization time
        self.start_directory = os.path.abspath(os.getcwd())
        logger.info(
            f"PermissionManager initialized with starting directory: {self.start_directory}",
        )

        # Create a set of allowed file paths (paths within the working directory)
        self.allowed_paths = set()
        self.allowed_paths.add(self.start_directory)

        # Initialize disallowed patterns
        self._initialize_path_restrictions()

    def _initialize_path_restrictions(self) -> None:
        """Initialize path restriction patterns."""
        # Pattern to detect common path traversal attempts
        self.path_traversal_patterns = [
            r"\.\.",
            r"\.\.\/",
            r"~\/",
            r"\$HOME",
            r"\$\{HOME\}",
            r"\$\(pwd\)",
            r"`pwd`",
            r"\/etc\/",
            r"\/var\/",
            r"\/usr\/",
            r"\/bin\/",
            r"\/tmp\/",
            r"\/root\/",
            r"\/proc\/",
            r"\/sys\/",
            r"\/dev\/",
            r"\/\*",
            r"~\/\*",
        ]

        # Compile regex patterns for efficiency
        self.path_traversal_regexes = [
            re.compile(pattern) for pattern in self.path_traversal_patterns
        ]

    def check_permission(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Check if a tool has permission to execute."""
        # Get permission path based on the tool and arguments
        permission_path = self._get_permission_path(tool_name, arguments)

        # Check all arguments for path traversal attempts
        self._check_all_arguments_for_traversal(tool_name, arguments)

        # Verify the path is within allowed directory bounds
        self._verify_directory_access(tool_name, permission_path)

        # Check if already trusted
        if self.trust_manager.is_trusted(tool_name, permission_path):
            logger.info(f"Tool {tool_name} is already trusted")
            return True

        logger.info(f"Requesting permission for {tool_name}")

        # Prompt for permission (this may raise PermissionDeniedError)
        return self.trust_manager.prompt_for_permission(tool_name, permission_path)

    def _check_all_arguments_for_traversal(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        """Check all string arguments for path traversal patterns.

        Args:
            tool_name: The name of the tool being used
            arguments: The arguments for the tool

        Raises:
            DirectoryTraversalError: If any argument contains path traversal patterns
        """
        # For bash commands, the command is validated separately
        if tool_name == "bash" and "command" in arguments:
            return

        # Check all string arguments for path traversal patterns
        for arg_name, arg_value in arguments.items():
            if isinstance(arg_value, str):
                # Skip empty strings
                if not arg_value or arg_value.strip() == "":
                    continue

                # Check for path traversal patterns
                if has_path_traversal_patterns(arg_value):
                    logger.warning(
                        f"Path traversal pattern detected in {tool_name} argument {arg_name}: {arg_value}",
                    )
                    raise DirectoryTraversalError(
                        f"Access denied: The argument '{arg_name}' contains path traversal patterns. "
                        f"Operations are restricted to '{self.start_directory}' and its subdirectories.",
                    )

                # Check if it's a potential file path
                if "/" in arg_value or "\\" in arg_value or "." in arg_value:
                    try:
                        # Verify it doesn't resolve to a path outside CWD
                        abs_path = os.path.abspath(arg_value)
                        if not abs_path.startswith(self.start_directory):
                            logger.warning(
                                f"Path outside CWD detected in {tool_name} argument {arg_name}: {arg_value}",
                            )
                            raise DirectoryTraversalError(
                                f"Access denied: The path '{arg_value}' in argument '{arg_name}' is outside the working directory. "
                                f"Operations are restricted to '{self.start_directory}' and its subdirectories.",
                            )
                    except Exception as e:
                        if isinstance(e, DirectoryTraversalError):
                            raise
                        # If we can't parse it as a path, log and continue
                        logger.debug(
                            f"Could not validate potential path in {tool_name} argument {arg_name}: {e}",
                        )

            # Check string arrays recursively
            elif isinstance(arg_value, list):
                for item in arg_value:
                    if isinstance(item, str) and has_path_traversal_patterns(item):
                        logger.warning(
                            f"Path traversal pattern detected in {tool_name} list argument {arg_name}: {item}",
                        )
                        raise DirectoryTraversalError(
                            f"Access denied: The list argument '{arg_name}' contains path traversal patterns. "
                            f"Operations are restricted to '{self.start_directory}' and its subdirectories.",
                        )

            # Check nested dictionaries recursively
            elif isinstance(arg_value, dict):
                self._check_all_arguments_for_traversal(
                    f"{tool_name}.{arg_name}",
                    arg_value,
                )

    def _verify_directory_access(
        self, tool_name: str, path_info: str | dict[str, str] | None,
    ) -> None:
        """Verify that the operation doesn't access files outside the starting directory.

        Args:
            tool_name: The name of the tool being used
            path_info: Path information from arguments

        Raises:
            DirectoryTraversalError: If the operation would access files outside allowed bounds
        """
        # For bash commands with cd, validation is already done in is_command_allowed
        if (
            tool_name == "bash"
            and isinstance(path_info, dict)
            and "command" in path_info
        ):
            # The command content is checked by trust.is_command_allowed
            return

        # For file/directory operations, check the path
        if isinstance(path_info, str):
            path = path_info

            # Skip empty paths
            if not path or path.strip() == "":
                return

            # Check for path traversal patterns first
            if has_path_traversal_patterns(path):
                logger.warning(
                    f"Path traversal pattern detected for {tool_name}: {path}",
                )
                raise DirectoryTraversalError(
                    f"Access denied: The path '{path}' contains path traversal patterns. "
                    f"Operations are restricted to '{self.start_directory}' and its subdirectories.",
                )

            # Normalize path
            try:
                abs_path = os.path.abspath(path)

                # Check if the path is within our starting directory
                if not abs_path.startswith(self.start_directory):
                    logger.warning(
                        f"Directory traversal attempt detected for {tool_name}: {path}",
                    )
                    raise DirectoryTraversalError(
                        f"Access denied: The path '{path}' is outside the working directory. "
                        f"Operations are restricted to '{self.start_directory}' and its subdirectories.",
                    )
            except Exception as e:
                if isinstance(e, DirectoryTraversalError):
                    raise
                logger.warning(f"Error checking path for {tool_name}: {e}")

    def resolve_paths_in_string(self, input_str: str) -> list[tuple[str, str]]:
        """Extract and resolve potential file paths in a string.

        Args:
            input_str: The string to analyze

        Returns:
            List of tuples containing (original_text, resolved_path)
        """
        resolved_paths = []

        # Look for potential paths in the string
        path_pattern = re.compile(r"(?:^|\s+)([\.\/\w\-~]+\/?[\w\-\.\/]+)(?:\s+|$)")
        matches = path_pattern.findall(input_str)

        for match in matches:
            # Skip empty matches
            if not match.strip():
                continue

            # Try to resolve as a path
            try:
                resolved = os.path.abspath(match)
                # Only include if it looks like a valid path
                if os.path.exists(resolved) or "/" in match or "\\" in match:
                    resolved_paths.append((match, resolved))
            except Exception:
                # Ignore paths we can't resolve
                pass

        return resolved_paths

    def _get_permission_path(
        self, tool_name: str, arguments: dict[str, Any],
    ) -> str | dict[str, str] | None:
        """Extract the path from tool arguments for permission checking."""
        # Handle bash commands differently
        if tool_name == "bash" and "command" in arguments:
            return arguments

        # For other tools, look for path arguments
        for arg_name, arg_value in arguments.items():
            if isinstance(arg_value, str) and arg_name in (
                "path",
                "file_path",
                "directory",
                "src",
                "dest",
                "source",
                "destination",
                "input",
                "output",
            ):
                return arg_value

        return None
