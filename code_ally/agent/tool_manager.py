"""File: tool_manager.py.

Manages tool registration, validation, and execution.
"""

import inspect
import logging
from typing import Any, Union

from code_ally.agent.permission_manager import PermissionManager
from code_ally.tools.base import BaseTool
from code_ally.trust import PermissionDeniedError, TrustManager

logger = logging.getLogger(__name__)


class ToolManager:
    """Manages tool registration, validation, and execution."""

    def __init__(
        self,
        tools: list[BaseTool],
        trust_manager: TrustManager,
        permission_manager: PermissionManager = None,
    ) -> None:
        """Initialize the tool manager.

        Args:
            tools: List of available tools
            trust_manager: Trust manager for permissions
            permission_manager: Permission manager for permissions
        """
        self.tools = {tool.name: tool for tool in tools}
        self.trust_manager = trust_manager
        # Create PermissionManager if not provided
        self.permission_manager = permission_manager or PermissionManager(trust_manager)
        self.ui = None  # Will be set by the Agent class
        self.client_type = None  # Will be set by the Agent when initialized

        # Track recent tool calls to avoid redundancy
        self.recent_tool_calls: list[tuple[str, tuple]] = []
        self.max_recent_calls = 5  # Remember last 5 calls
        self.current_turn_tool_calls: list[tuple[str, tuple]] = (
            []
        )  # For the current conversation turn only

    def get_function_definitions(self) -> list[dict[str, Any]]:
        """Create function definitions for tools in the format expected by the LLM.

        Returns:
            List of function definitions
        """
        function_defs = []
        for tool in self.tools.values():
            # Get the execute method
            execute_method = tool.execute

            # Extract information from the method
            sig = inspect.signature(execute_method)
            # get docstring but not used here
            _ = inspect.getdoc(execute_method) or ""

            # Build parameter schema
            parameters = {"type": "object", "properties": {}, "required": []}

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # Default type is string
                param_type = "string"

                # Try to determine type from annotation
                if param.annotation is not inspect.Parameter.empty:
                    if param.annotation is str:
                        param_type = "string"
                    elif param.annotation is int:
                        param_type = "integer"
                    elif param.annotation is float:
                        param_type = "number"
                    elif param.annotation is bool:
                        param_type = "boolean"
                    elif (
                        param.annotation is list
                        or hasattr(param.annotation, "__origin__")
                        and param.annotation.__origin__ is list
                    ):
                        param_type = "array"
                    # Handle Optional/Union types
                    elif (
                        hasattr(param.annotation, "__origin__")
                        and param.annotation.__origin__ is Union
                    ):
                        args = param.annotation.__args__
                        if type(None) in args:  # This is an Optional
                            for arg in args:
                                if arg is not type(None):
                                    if arg is str:
                                        param_type = "string"
                                    elif arg is int:
                                        param_type = "integer"
                                    elif arg is float:
                                        param_type = "number"
                                    elif arg is bool:
                                        param_type = "boolean"
                                    elif (
                                        arg is list
                                        or hasattr(arg, "__origin__")
                                        and arg.__origin__ is list
                                    ):
                                        param_type = "array"

                # Set parameter description
                param_desc = f"Parameter {param_name}"

                # Add to properties
                parameters["properties"][param_name] = {
                    "type": param_type,
                    "description": param_desc,
                }

                # If the parameter has no default value, it's required
                if param.default is inspect.Parameter.empty:
                    parameters["required"].append(param_name)

            # Create the function definition
            function_def = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": parameters,
                },
            }
            function_defs.append(function_def)

        return function_defs

    def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        check_context_msg: bool = True,
        client_type: str | None = None,
        pre_approved: bool = False,
    ) -> dict[str, Any]:
        """Execute a tool with the given arguments after checking trust.

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments to pass to the tool
            check_context_msg: Whether to remind about checking context for redundant calls
            client_type: Optional client type to use for formatting results
            pre_approved: Whether the operation was pre-approved in a batch

        Returns:
            Dictionary containing the result of tool execution

        Raises:
            PermissionDeniedError: If permission is denied for protected operations
        """
        verbose_mode = self.ui and getattr(self.ui, "verbose", False)

        if verbose_mode:
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in arguments.items())
            self.ui.console.print(
                f"[dim magenta][Verbose] Starting tool execution: {tool_name}({args_str})[/]",
            )

        # Validate tool existence
        if not self._is_valid_tool(tool_name):
            return self._create_error_result(f"Unknown tool: {tool_name}")

        # Check for redundancy
        if self._is_redundant_call(tool_name, arguments):
            return self._handle_redundant_call(tool_name, check_context_msg)

        # Record this call
        self._record_tool_call(tool_name, arguments)

        # Check permissions if not pre-approved
        tool = self.tools[tool_name]
        if tool.requires_confirmation and not pre_approved:
            # Get permission path based on the tool and arguments
            permission_path = self._get_permission_path(tool_name, arguments)

            try:
                # Check if already trusted
                if not self.trust_manager.is_trusted(tool_name, permission_path):
                    logger.info(f"Requesting permission for {tool_name}")

                    # Prompt for permission (this may raise PermissionDeniedError)
                    if not self.trust_manager.prompt_for_permission(
                        tool_name,
                        permission_path,
                    ):
                        return self._create_error_result(
                            f"Permission denied for {tool_name}",
                        )
            except PermissionDeniedError:
                # Let exceptions propagate upward
                raise

        # Execute the tool
        return self._perform_tool_execution(tool_name, arguments)

    def _is_valid_tool(self, tool_name: str) -> bool:
        """Check if a tool exists."""
        valid = tool_name in self.tools

        if not valid and self.ui and getattr(self.ui, "verbose", False):
            self.ui.console.print(f"[dim red][Verbose] Tool not found: {tool_name}[/]")

        return valid

    def _is_redundant_call(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Check if a tool call is redundant.

        Only considers calls made in the current conversation turn as redundant.
        """
        # Create a hashable representation of the current call
        current_call = (tool_name, tuple(sorted(arguments.items())))

        # Only check for redundancy within the current conversation turn
        return current_call in self.current_turn_tool_calls

    def _handle_redundant_call(
        self,
        tool_name: str,
        check_context_msg: bool,
    ) -> dict[str, Any]:
        """Handle a redundant tool call."""
        # Simple consistent message for redundancy
        error_msg = f"Identical {tool_name} call was already executed in this conversation turn."

        # Add context check suggestion if enabled
        if check_context_msg:
            error_msg += " Please check your context for the previous result."

        if self.ui and getattr(self.ui, "verbose", False):
            self.ui.console.print(
                f"[dim yellow][Verbose] Redundant tool call detected: {tool_name}[/]",
            )

        return {
            "success": False,
            "error": error_msg,
        }

    def _record_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Record a tool call to avoid redundancy."""
        current_call = (tool_name, tuple(sorted(arguments.items())))

        # Add to both lists
        self.recent_tool_calls.append(current_call)
        self.current_turn_tool_calls.append(current_call)

        # Keep only the most recent calls in the history
        if len(self.recent_tool_calls) > self.max_recent_calls:
            self.recent_tool_calls = self.recent_tool_calls[-self.max_recent_calls :]

    def _get_permission_path(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str | None:
        """Get the permission path for a tool."""
        # For bash tool, pass arguments.command as the path
        if tool_name == "bash" and "command" in arguments:
            return arguments

        # Use the first string argument as the path, if any
        for arg_name, arg_value in arguments.items():
            if isinstance(arg_value, str) and arg_name in (
                "path",
                "file_path",
                "directory",
            ):
                return arg_value

        return None

    def _perform_tool_execution(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool with the given arguments."""
        import time

        tool = self.tools[tool_name]
        verbose_mode = self.ui and getattr(self.ui, "verbose", False)
        start_time = time.time()

        try:
            if verbose_mode:
                self.ui.console.print(
                    f"[dim green][Verbose] Executing tool: {tool_name}[/]",
                )

            result = tool.execute(**arguments)
            execution_time = time.time() - start_time

            if verbose_mode:
                self.ui.console.print(
                    f"[dim green][Verbose] Tool {tool_name} executed in {execution_time:.2f}s "
                    f"(success: {result.get('success', False)})[/]",
                )

            logger.debug("Tool %s executed in %.2fs", tool_name, execution_time)
            return result
        except Exception as exc:
            logger.exception("Error executing tool %s", tool_name)
            if verbose_mode:
                self.ui.console.print(
                    f"[dim red][Verbose] Error executing {tool_name}: {str(exc)}[/]",
                )
            return self._create_error_result(f"Error executing {tool_name}: {str(exc)}")

    def _create_error_result(self, error_message: str) -> dict[str, Any]:
        """Create a standardized error result."""
        return {
            "success": False,
            "error": error_message,
        }

    def format_tool_result(
        self,
        result: dict[str, Any],
        client_type: str = None,
    ) -> dict[str, Any]:
        """Format the tool result.

        Args:
            result: The result to format
            client_type: The client type (unused)

        Returns:
            The unmodified result
        """
        return result
