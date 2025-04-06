"""File: tool_manager.py

Manages tool registration, validation, and execution.
"""

import inspect
import json
import logging
from typing import Any, Dict, List, Tuple, Union

from code_ally.tools.base import BaseTool
from code_ally.trust import TrustManager

logger = logging.getLogger(__name__)


class ToolManager:
    """Manages tool registration, validation, and execution."""

    def __init__(self, tools: List[BaseTool], trust_manager: TrustManager):
        """Initialize the tool manager.

        Args:
            tools: List of available tools
            trust_manager: Trust manager for permissions
        """
        self.tools = {tool.name: tool for tool in tools}
        self.trust_manager = trust_manager
        self.ui = None  # Will be set by the Agent class
        self.client_type = None  # Will be set by the Agent when initialized

        # Track recent tool calls to avoid redundancy
        self.recent_tool_calls: List[Tuple[str, Tuple]] = []
        self.max_recent_calls = 5  # Remember last 5 calls

        # Initialize tool result formatters
        self._init_tool_formatters()

    def _init_tool_formatters(self):
        """Initialize formatters for converting tool results to natural language."""
        self.tool_formatters = {
            # Filesystem tools
            "file_read": self._format_file_read_result,
            "file_write": self._format_file_write_result,
            "file_edit": self._format_file_edit_result,
            # Search tools
            "glob": self._format_glob_result,
            "grep": self._format_grep_result,
            # Command execution
            "bash": self._format_bash_result,
            # General tools
            "ls": self._format_ls_result,
            "math": self._format_math_result,
        }

    def _format_file_read_result(self, result: Dict[str, Any]) -> str:
        """Format file_read result as natural language."""
        if not result.get("success", False):
            return json.dumps(result)

        content_length = len(result.get("content", ""))
        return json.dumps(
            {
                "content": result.get("content", ""),
                "description": f"Successfully read file with {content_length} characters",
            }
        )

    def _format_file_write_result(self, result: Dict[str, Any]) -> str:
        """Format file_write result as natural language."""
        if result.get("success", False):
            return json.dumps({"success": True, "message": "File written successfully"})
        return json.dumps(result)

    def _format_file_edit_result(self, result: Dict[str, Any]) -> str:
        """Format file_edit result as natural language."""
        if result.get("success", False):
            return json.dumps({"success": True, "message": "File edited successfully"})
        return json.dumps(result)

    def _format_bash_result(self, result: Dict[str, Any]) -> str:
        """Format bash result as natural language."""
        return json.dumps(result)

    def _format_glob_result(self, result: Dict[str, Any]) -> str:
        """Format glob result as natural language."""
        return json.dumps(result)

    def _format_grep_result(self, result: Dict[str, Any]) -> str:
        """Format grep result as natural language."""
        return json.dumps(result)

    def _format_ls_result(self, result: Dict[str, Any]) -> str:
        """Format ls result as natural language."""
        return json.dumps(result)

    def _format_math_result(self, result: Dict[str, Any]) -> str:
        """Format math result as natural language."""
        return json.dumps(result)

    def get_function_definitions(self) -> List[Dict[str, Any]]:
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
            doc = inspect.getdoc(execute_method) or ""

            # Build parameter schema
            parameters = {"type": "object", "properties": {}, "required": []}

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # Default type is string
                param_type = "string"

                # Try to determine type from annotation
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == str:
                        param_type = "string"
                    elif param.annotation == int:
                        param_type = "integer"
                    elif param.annotation == float:
                        param_type = "number"
                    elif param.annotation == bool:
                        param_type = "boolean"
                    elif (
                        param.annotation == list
                        or hasattr(param.annotation, "__origin__")
                        and param.annotation.__origin__ == list
                    ):
                        param_type = "array"
                    # Handle Optional/Union types
                    elif (
                        hasattr(param.annotation, "__origin__")
                        and param.annotation.__origin__ == Union
                    ):
                        args = param.annotation.__args__
                        if type(None) in args:  # This is an Optional
                            for arg in args:
                                if arg != type(None):
                                    if arg == str:
                                        param_type = "string"
                                    elif arg == int:
                                        param_type = "integer"
                                    elif arg == float:
                                        param_type = "number"
                                    elif arg == bool:
                                        param_type = "boolean"
                                    elif (
                                        arg == list
                                        or hasattr(arg, "__origin__")
                                        and arg.__origin__ == list
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
                if param.default == inspect.Parameter.empty:
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

    def is_redundant_call(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """Check if a tool call is redundant.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Whether the call is redundant
        """
        current_call = (tool_name, tuple(sorted(arguments.items())))

        # For LS tool, be even more strict
        if tool_name == "ls" and any(
            call[0] == "ls" for call in self.recent_tool_calls
        ):
            return True

        # Check if this exact call has been made recently
        return current_call in self.recent_tool_calls

    def record_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        """Record a tool call to avoid redundancy.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
        """
        current_call = (tool_name, tuple(sorted(arguments.items())))
        self.recent_tool_calls.append(current_call)

        # Keep only the most recent calls
        if len(self.recent_tool_calls) > self.max_recent_calls:
            self.recent_tool_calls = self.recent_tool_calls[-self.max_recent_calls :]

    def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        check_context_msg: bool = True,
        client_type: str = None,
        batch_id: str = None,
    ) -> Dict[str, Any]:
        """Execute a tool with the given arguments after checking trust.

        Args:
            tool_name: The name of the tool to execute
            arguments: The arguments to pass to the tool
            check_context_msg: Whether to add context check message for redundant calls
            client_type: The client type to use for formatting the result
            batch_id: The batch ID for parallel tool calls

        Returns:
            The result of the tool execution
        """
        import time

        start_time = time.time()
        verbose_mode = self.ui and getattr(self.ui, "verbose", False)

        if verbose_mode:
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in arguments.items())
            self.ui.console.print(
                f"[dim magenta][Verbose] Starting tool execution: {tool_name}({args_str})[/]"
            )

        if tool_name not in self.tools:
            if verbose_mode:
                self.ui.console.print(
                    f"[dim red][Verbose] Tool not found: {tool_name}[/]"
                )
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
            }

        tool = self.tools[tool_name]

        # Check for redundant calls
        if self.is_redundant_call(tool_name, arguments):
            if tool_name == "ls":
                error_msg = (
                    f"Redundant call to {tool_name}. Directory was already shown."
                )
                if check_context_msg:
                    error_msg += " Please check your context for the previous result."

                if verbose_mode:
                    self.ui.console.print(
                        f"[dim yellow][Verbose] Redundant tool call detected: {tool_name}[/]"
                    )

                return {
                    "success": False,
                    "error": error_msg,
                }

        # Record this call
        self.record_tool_call(tool_name, arguments)

        # Check permissions if tool requires confirmation
        if tool.requires_confirmation:
            if verbose_mode:
                self.ui.console.print(
                    f"[dim blue][Verbose] Tool {tool_name} requires confirmation[/]"
                )

            # For bash tool, pass arguments.command as the path
            if tool_name == "bash" and "command" in arguments:
                permission_path = arguments
            else:
                # Use the first string argument as the path, if any
                permission_path = None
                for arg_name, arg_value in arguments.items():
                    if isinstance(arg_value, str) and arg_name in ("path", "file_path"):
                        permission_path = arg_value
                        break

            if not self.trust_manager.is_trusted(
                tool_name, permission_path, batch_id
            ) and not self.trust_manager.prompt_for_permission(
                tool_name, permission_path
            ):
                if verbose_mode:
                    self.ui.console.print(
                        f"[dim red][Verbose] Permission denied for {tool_name}[/]"
                    )
                return {
                    "success": False,
                    "error": f"Permission denied for {tool_name}",
                }

        # Execute the tool
        try:
            if verbose_mode:
                self.ui.console.print(
                    f"[dim green][Verbose] Executing tool: {tool_name}[/]"
                )
            result = tool.execute(**arguments)
            execution_time = time.time() - start_time

            if verbose_mode:
                self.ui.console.print(
                    f"[dim green][Verbose] Tool {tool_name} executed in {execution_time:.2f}s "
                    f"(success: {result.get('success', False)})[/]"
                )

            logger.debug("Tool %s executed in %.2fs", tool_name, execution_time)
            return result
        except json.JSONDecodeError as json_exc:
            logger.exception("Error parsing JSON in tool execution for %s", tool_name)
            return {
                "success": False,
                "error": f"JSON Error executing {tool_name}: {str(json_exc)}",
            }
        except Exception as exc:
            logger.exception("Error executing tool %s", tool_name)
            if verbose_mode:
                self.ui.console.print(
                    f"[dim red][Verbose] Error executing {tool_name}: {str(exc)}[/]"
                )
            return {
                "success": False,
                "error": f"Error executing {tool_name}: {str(exc)}",
            }

    def format_tool_result(
        self, result: Dict[str, Any], client_type: str = None
    ) -> Dict[str, Any]:
        """Format the tool result based on the client type.

        Args:
            result: The result to format
            client_type: The client type to use for formatting

        Returns:
            The formatted result
        """
        client_type = client_type or self.client_type
        # In the future, add any client-specific formatting logic here.
        return result
