"""File: agent.py

The main Agent class that manages the conversation and handles tool execution.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from code_ally.agent.command_handler import CommandHandler
from code_ally.agent.error_handler import display_error
from code_ally.agent.permission_manager import PermissionManager
from code_ally.agent.task_planner import TaskPlanner
from code_ally.agent.token_manager import TokenManager
from code_ally.agent.tool_manager import ToolManager
from code_ally.agent.ui_manager import UIManager
from code_ally.llm_client import ModelClient
from code_ally.service_registry import ServiceRegistry
from code_ally.trust import PermissionDeniedError, TrustManager

logger = logging.getLogger(__name__)


class Agent:
    """The main agent class that manages the conversation and tool execution."""

    def __init__(
        self,
        model_client: ModelClient,
        tools: List[Any],
        client_type: str = None,
        system_prompt: Optional[str] = None,
        verbose: bool = False,
        check_context_msg: bool = True,
        auto_dump: bool = True,
        service_registry: Optional[ServiceRegistry] = None,
    ):
        """Initialize the agent.

        Args:
            model_client: The LLM client to use
            tools: List of available tools
            client_type: The client type to use for formatting the result
            system_prompt: The system prompt to use (optional)
            verbose: Whether to enable verbose mode
            check_context_msg: Encourage LLM to check context to prevent redundant calls
            auto_dump: Automatically dump conversation on exit
            service_registry: Optional service registry instance
        """
        # Use provided service registry or create one
        self.service_registry = service_registry or ServiceRegistry.get_instance()

        # Store basic configuration
        self.model_client = model_client
        self.messages = []
        self.check_context_msg = check_context_msg
        self.auto_dump = auto_dump
        self.request_in_progress = False

        # Determine client type
        self.client_type = client_type or "ollama"

        # Create and register components
        self._initialize_components(tools, verbose)

        # Optionally add an initial system prompt
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})
            self.token_manager.update_token_count(self.messages)

    def _initialize_components(self, tools, verbose):
        """Initialize and register all agent components.

        Args:
            tools: List of available tools
            verbose: Whether to enable verbose mode
        """
        # Create UI Manager
        self.ui = UIManager()
        self.ui.set_verbose(verbose)
        self.ui.agent = self
        self.service_registry.register("ui_manager", self.ui)

        # Create Trust Manager
        self.trust_manager = TrustManager()
        self.service_registry.register("trust_manager", self.trust_manager)

        # Create Permission Manager
        self.permission_manager = PermissionManager(self.trust_manager)
        self.service_registry.register("permission_manager", self.permission_manager)

        # Create Token Manager
        self.token_manager = TokenManager(self.model_client.context_size)
        self.token_manager.ui = self.ui
        self.service_registry.register("token_manager", self.token_manager)

        # Create Tool Manager
        self.tool_manager = ToolManager(tools, self.trust_manager)
        self.tool_manager.ui = self.ui
        self.tool_manager.client_type = self.client_type
        self.service_registry.register("tool_manager", self.tool_manager)

        # Create Task Planner
        self.task_planner = TaskPlanner(self.tool_manager)
        self.task_planner.ui = self.ui
        self.task_planner.set_verbose(verbose)
        self.service_registry.register("task_planner", self.task_planner)

        # Create Command Handler
        self.command_handler = CommandHandler(
            self.ui, self.token_manager, self.trust_manager
        )
        self.command_handler.set_verbose(verbose)
        self.command_handler.agent = self
        self.service_registry.register("command_handler", self.command_handler)

    def process_llm_response(self, response: Dict[str, Any]) -> None:
        """Process the LLM's response and execute any tool calls if present.

        Args:
            response: The LLM's response dictionary containing content and any tool calls
        """
        content = response.get("content", "")
        tool_calls = []

        # Possible location of tool calls
        if "tool_calls" in response:
            # Standard multi-call format
            tool_calls = response.get("tool_calls", [])
        elif "function_call" in response:
            # Qwen-Agent style single call
            if response["function_call"]:
                tool_calls = [
                    {
                        "id": f"manual-id-{int(time.time())}",
                        "type": "function",
                        "function": response["function_call"],
                    }
                ]

        if tool_calls:
            # Add assistant message with the tool calls
            assistant_message = response.copy()
            self.messages.append(assistant_message)
            self.token_manager.update_token_count(self.messages)

            # Process tools
            try:
                self._process_sequential_tool_calls(tool_calls)
            except PermissionDeniedError:
                # Permission was denied by user; return to main conversation loop
                return

            # Get a follow-up response
            follow_up_response = None
            was_interrupted = False

            # Clear the current turn's tool calls for follow-up responses
            self.tool_manager.current_turn_tool_calls = []

            try:
                self.request_in_progress = True  # Signal that a request is starting
                try:
                    follow_up_response = self.model_client.send(
                        self.messages,
                        functions=self.tool_manager.get_function_definitions(),
                        include_reasoning=self.ui.verbose,
                    )
                    was_interrupted = follow_up_response.get("interrupted", False)
                except KeyboardInterrupt:
                    logger.warning(
                        "KeyboardInterrupt caught during model_client.send call."
                    )
                    was_interrupted = True
                except Exception as e:
                    logger.error(f"Error during model_client.send: {e}", exc_info=True)
                    self.ui.print_error(f"Failed to get response from model: {e}")
            finally:
                self.request_in_progress = False  # Ensure flag is always reset

            if was_interrupted:
                self.ui.stop_thinking_animation()
                self.ui.print_content("[yellow]Request interrupted by user[/]")
                return

            if follow_up_response:
                # Define the interruption marker message
                interruption_markers = [
                    "[Request interrupted by user]",
                    "[Request interrupted by user for tool use]",
                    "[Request interrupted by user due to permission denial]",
                ]

                response_content = follow_up_response.get("content", "").strip()
                was_interrupted = (
                    follow_up_response.get("interrupted", False)
                    or response_content in interruption_markers
                )
                if was_interrupted:
                    self.ui.stop_thinking_animation()
                    self.ui.print_content("[yellow]Request interrupted by user[/]")
                    return

                if self.ui.verbose:
                    has_tool_calls = (
                        "tool_calls" in follow_up_response
                        and follow_up_response["tool_calls"]
                    )
                    tool_names = []
                    if has_tool_calls:
                        for tc in follow_up_response["tool_calls"]:
                            if "function" in tc and "name" in tc["function"]:
                                tool_names.append(tc["function"]["name"])

                    resp_type = "tool calls" if has_tool_calls else "text response"
                    tools_info = f" ({', '.join(tool_names)})" if tool_names else ""
                    self.ui.console.print(
                        f"[dim blue][Verbose] Received follow-up {resp_type}{tools_info} from LLM[/]"
                    )

                self.ui.stop_thinking_animation()

                # Recursively process the follow-up
                self.process_llm_response(follow_up_response)
            else:
                self.ui.stop_thinking_animation()

        else:
            # Normal text response
            self.messages.append(response)
            self.token_manager.update_token_count(self.messages)
            self.ui.print_assistant_response(content)

    def _normalize_tool_call(
        self, tool_call: Dict[str, Any]
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Normalize a tool call dict to (call_id, tool_name, arguments)."""
        call_id = tool_call.get("id", f"auto-id-{int(time.time())}")
        function_call = tool_call.get("function", {})

        # In some LLM outputs, the 'function' dict might exist at top-level
        if not function_call and "name" in tool_call:
            function_call = tool_call

        tool_name = function_call.get("name", "")
        arguments_raw = function_call.get("arguments", "{}")

        if isinstance(arguments_raw, dict):
            arguments = arguments_raw
        else:
            # Attempt to parse as JSON
            try:
                arguments = json.loads(arguments_raw)
            except json.JSONDecodeError:
                # Fallback attempts
                try:
                    # Replace single quotes and parse
                    fixed_json = arguments_raw.replace("'", '"')
                    arguments = json.loads(fixed_json)
                except Exception:
                    # Last resort: parse naive key-value pairs
                    arguments = {"raw_args": arguments_raw}

        return call_id, tool_name, arguments

    def _process_sequential_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> None:
        """Process tool calls one by one."""
        for tool_call in tool_calls:
            try:
                call_id, tool_name, arguments = self._normalize_tool_call(tool_call)
                if not tool_name:
                    self.ui.print_warning(
                        "Invalid tool call: missing tool name. Skipping."
                    )
                    continue

                # Display that the call is happening
                self.ui.print_tool_call(tool_name, arguments)

                # Execute
                try:
                    raw_result = self.tool_manager.execute_tool(
                        tool_name, arguments, self.check_context_msg, self.client_type
                    )
                except PermissionDeniedError:
                    # User denied permission, add a special message to history
                    self.messages.append(
                        {
                            "role": "assistant",
                            "content": "[Request interrupted by user due to permission denial]",
                        }
                    )
                    self.token_manager.update_token_count(self.messages)
                    raise  # Re-raise to exit the entire process

                # Check for errors and provide acknowledgement if needed
                if not raw_result.get("success", False):
                    error_msg = raw_result.get("error", "Unknown error")

                    # Display formatted error with suggestions
                    display_error(self.ui, error_msg, tool_name, arguments)

                result = self.tool_manager.format_tool_result(
                    raw_result, self.client_type
                )
                content = self._format_tool_result_as_natural_language(
                    tool_name, result
                )

                # Create tool response message
                tool_message = {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": tool_name,
                    "content": content,
                }

                # Check for duplicate file reads (from file_read tool)
                previous_message_id = None
                if (
                    tool_name == "file_read"
                    and raw_result.get("_needs_duplicate_check")
                    and raw_result.get("file_path")
                    and raw_result.get("success", False)
                ):
                    # Check if we've seen this file before
                    file_path = raw_result.get("file_path")
                    file_content = content

                    # If we register the file and it already exists, we'll get back the previous message ID
                    previous_message_id = self.token_manager.register_file_read(
                        file_path, file_content, call_id
                    )

                    if (
                        previous_message_id
                        and self.ui
                        and getattr(self.ui, "verbose", False)
                    ):
                        self.ui.console.print(
                            f"[dim yellow][Verbose] Detected duplicate file read for {file_path}. "
                            f"Removing previous version from context.[/]"
                        )

                # Check if we need to remove a previous file read from context
                if previous_message_id:
                    # Filter out the previous message with this content
                    self.messages = [
                        msg
                        for msg in self.messages
                        if not (
                            msg.get("role") == "tool"
                            and msg.get("tool_call_id") == previous_message_id
                        )
                    ]

                # Add to history
                self.messages.append(tool_message)

                # If we removed a previous message, update token count immediately
                if previous_message_id:
                    # Clear token cache to ensure accurate token count after removal
                    self.token_manager.clear_cache()
                    self.token_manager.update_token_count(self.messages)

                    if self.ui and getattr(self.ui, "verbose", False):
                        token_pct = self.token_manager.get_token_percentage()
                        self.ui.console.print(
                            f"[dim green][Verbose] Updated context after duplicate removal. "
                            f"Context usage: {token_pct}% of window[/]"
                        )

            except PermissionDeniedError:
                # Let this propagate up to abort the whole process
                raise
            except Exception as e:
                logger.exception(f"Error processing tool call: {e}")
                self.ui.print_error(f"Error processing tool call: {str(e)}")

        self.token_manager.update_token_count(self.messages)

    def _format_tool_result_as_natural_language(
        self, tool_name: str, result: Any
    ) -> str:
        """Convert a tool result dict into a user-readable string if appropriate."""
        if not isinstance(result, str):
            result_str = json.dumps(result)
        else:
            result_str = result

        if isinstance(result_str, str) and (
            "<tool_response>" in result_str or "<search_reminders>" in result_str
        ):
            # Attempt to strip out any leftover tags if a special client was used
            if hasattr(self.model_client, "_extract_tool_response"):
                cleaned_result = self.model_client._extract_tool_response(result_str)
                if isinstance(cleaned_result, dict):
                    return json.dumps(cleaned_result)
                return cleaned_result
            else:
                # Fallback removal
                result_str = re.sub(
                    r"<tool_response>(.*?)</tool_response>",
                    r"\1",
                    result_str,
                    flags=re.DOTALL,
                )
                result_str = re.sub(
                    r"<search_reminders>.*?</search_reminders>",
                    "",
                    result_str,
                    flags=re.DOTALL,
                )
                result_str = re.sub(
                    r"<automated_reminder_from_anthropic>.*?</automated_reminder_from_anthropic>",
                    "",
                    result_str,
                    flags=re.DOTALL,
                )

        return result_str

    def run_conversation(self) -> None:
        """Run the interactive conversation loop."""
        self.ui.print_help()

        while True:
            # Auto-compact if needed
            if self.token_manager.should_compact():
                old_pct = self.token_manager.get_token_percentage()
                self.messages = self.command_handler.compact_conversation(self.messages)
                self.token_manager.update_token_count(self.messages)
                new_pct = self.token_manager.get_token_percentage()
                self.ui.print_warning(f"Auto-compacted: {old_pct}% → {new_pct}%")

            # Wait for user input
            try:
                user_input = self.ui.get_user_input()
            except EOFError:
                # Dump conversation if enabled
                if self.auto_dump:
                    self.command_handler.dump_conversation(self.messages, "")
                break

            # Skip empty input
            if not user_input.strip():
                continue

            # Check for slash commands
            if user_input.startswith("/"):
                parts = user_input[1:].split(" ", 1)
                cmd = parts[0].strip()
                arg = parts[1].strip() if len(parts) > 1 else ""
                handled, self.messages = self.command_handler.handle_command(
                    cmd, arg, self.messages
                )
                if handled:
                    continue

            # Check for special messages after permission denial
            last_message = self.messages[-1] if self.messages else None
            if (
                last_message
                and last_message.get("role") == "assistant"
                and last_message.get("content", "").strip()
                == "[Request interrupted by user due to permission denial]"
            ):
                # Replace the permission denial message with a more useful one
                self.messages[-1] = {
                    "role": "assistant",
                    "content": "I understand you denied permission. Let me know how I can better assist you.",
                }

            self.messages.append({"role": "user", "content": user_input})

            self.token_manager.update_token_count(self.messages)

            # Start "thinking" animation
            animation_thread = self.ui.start_thinking_animation(
                self.token_manager.get_token_percentage()
            )

            if self.ui.verbose:
                functions_count = len(self.tool_manager.get_function_definitions())
                message_count = len(self.messages)
                tokens = self.token_manager.estimated_tokens
                self.ui.console.print(
                    f"[dim blue][Verbose] Sending request to LLM with {message_count} messages, "
                    f"{tokens} tokens, {functions_count} available functions[/]"
                )

            response = None
            was_interrupted = False

            # Clear the current turn's tool calls at the start of each new conversation turn
            self.tool_manager.current_turn_tool_calls = []

            try:
                self.request_in_progress = True
                try:
                    response = self.model_client.send(
                        self.messages,
                        functions=self.tool_manager.get_function_definitions(),
                        include_reasoning=self.ui.verbose,
                    )
                    was_interrupted = response.get("interrupted", False)
                except KeyboardInterrupt:
                    logger.warning(
                        "KeyboardInterrupt caught during model_client.send call."
                    )
                    was_interrupted = True
                except Exception as e:
                    logger.error(f"Error during model_client.send: {e}", exc_info=True)
                    self.ui.print_error(f"Failed to get response from model: {e}")
            finally:
                self.request_in_progress = False

            if was_interrupted:
                self.ui.stop_thinking_animation()
                if animation_thread and animation_thread.is_alive():
                    animation_thread.join(timeout=1.0)
                self.ui.print_content("[yellow]Request interrupted by user[/]")
                continue

            if response:
                # Define the interruption marker message
                interruption_markers = [
                    "[Request interrupted by user]",
                    "[Request interrupted by user for tool use]",
                    "[Request interrupted by user due to permission denial]",
                ]

                response_content = response.get("content", "").strip()
                was_interrupted = (
                    response.get("interrupted", False)
                    or response_content in interruption_markers
                )

                if was_interrupted:
                    self.ui.stop_thinking_animation()
                    animation_thread.join(timeout=1.0)
                    self.ui.print_content("[yellow]Request interrupted by user[/]")
                    continue

                if self.ui.verbose:
                    has_tool_calls = "tool_calls" in response and response["tool_calls"]
                    tool_names = []
                    if has_tool_calls:
                        for tc in response["tool_calls"]:
                            if "function" in tc and "name" in tc["function"]:
                                tool_names.append(tc["function"]["name"])
                    resp_type = "tool calls" if has_tool_calls else "text response"
                    tools_info = f" ({', '.join(tool_names)})" if tool_names else ""
                    self.ui.console.print(
                        f"[dim blue][Verbose] Received {resp_type}{tools_info} from LLM[/]"
                    )

                self.ui.stop_thinking_animation()
                if animation_thread and animation_thread.is_alive():
                    animation_thread.join(timeout=1.0)

                self.process_llm_response(response)
            else:
                self.ui.stop_thinking_animation()
                if animation_thread and animation_thread.is_alive():
                    animation_thread.join(timeout=1.0)
