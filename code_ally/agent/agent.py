"""File: agent.py

The main Agent class that manages the conversation and handles tool execution.
"""

import json
import logging
import re
import time
import threading
import concurrent.futures
from typing import Any, Dict, List, Optional, Tuple

from code_ally.llm_client import ModelClient
from code_ally.trust import TrustManager
from code_ally.agent.token_manager import TokenManager
from code_ally.agent.ui_manager import UIManager
from code_ally.agent.tool_manager import ToolManager
from code_ally.agent.command_handler import CommandHandler
from code_ally.config import load_config

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
        parallel_tools: bool = True,
        check_context_msg: bool = True,
        auto_dump: bool = True,
    ):
        """Initialize the agent.

        Args:
            model_client: The LLM client to use
            tools: List of available tools
            client_type: The client type to use for formatting the result
            system_prompt: The system prompt to use (optional)
            verbose: Whether to enable verbose mode
            parallel_tools: Whether to enable parallel tool execution
            check_context_msg: Encourage LLM to check context to prevent redundant calls
            auto_dump: Automatically dump conversation on exit
        """
        self.model_client = model_client
        self.trust_manager = TrustManager()
        self.messages: List[Dict[str, Any]] = []
        self.check_context_msg = check_context_msg
        self.parallel_tools = parallel_tools
        self.auto_dump = auto_dump

        # Initialize UI
        self.ui = UIManager()
        self.ui.set_verbose(verbose)

        # Initialize Token Manager
        self.token_manager = TokenManager(model_client.context_size)
        self.token_manager.ui = self.ui

        # Initialize Tool Manager
        self.tool_manager = ToolManager(tools, self.trust_manager)
        self.tool_manager.ui = self.ui

        # Initialize Command Handler
        self.command_handler = CommandHandler(
            self.ui, self.token_manager, self.trust_manager
        )
        self.command_handler.set_verbose(verbose)
        self.command_handler.agent = self

        # Determine client type
        if client_type is None:
            client_type = "ollama"
        self.client_type = client_type
        self.tool_manager.client_type = self.client_type

        # Optionally add an initial system prompt
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})
            self.token_manager.update_token_count(self.messages)

    def process_llm_response(self, response: Dict[str, Any]) -> None:
        """Process the LLM's response and execute any tool calls if present.

        Args:
            response: The LLM's response
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
            if self.parallel_tools and len(tool_calls) > 1:
                self._process_parallel_tool_calls(tool_calls)
            else:
                self._process_sequential_tool_calls(tool_calls)

            # Get a follow-up response
            animation_thread = self.ui.start_thinking_animation(
                self.token_manager.get_token_percentage()
            )

            if self.ui.verbose:
                functions_count = len(self.tool_manager.get_function_definitions())
                message_count = len(self.messages)
                tokens = self.token_manager.estimated_tokens
                self.ui.console.print(
                    f"[dim blue][Verbose] Sending follow-up request to LLM with {message_count} messages, "
                    f"{tokens} tokens, {functions_count} available functions[/]"
                )

            follow_up_response = self.model_client.send(
                self.messages,
                functions=self.tool_manager.get_function_definitions(),
                include_reasoning=self.ui.verbose,
            )

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
            animation_thread.join(timeout=1.0)

            # Recursively process the follow-up
            self.process_llm_response(follow_up_response)

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
        # so handle either: tool_call["function"] or tool_call["name"]
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
                raw_result = self.tool_manager.execute_tool(
                    tool_name, arguments, self.check_context_msg, self.client_type
                )
                result = self.tool_manager.format_tool_result(
                    raw_result, self.client_type
                )
                content = self._format_tool_result_as_natural_language(
                    tool_name, result
                )

                # Add to history
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "content": content,
                    }
                )

            except Exception as e:
                logger.exception(f"Error processing tool call: {e}")
                self.ui.print_error(f"Error processing tool call: {str(e)}")

        self.token_manager.update_token_count(self.messages)

    def _process_parallel_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> None:
        """Process tool calls in parallel."""
        self.ui.print_content(
            f"Processing {len(tool_calls)} tool calls in parallel...", style="dim cyan"
        )

        normalized_calls = []
        for tc in tool_calls:
            try:
                call_id, tool_name, arguments = self._normalize_tool_call(tc)
                if tool_name:
                    normalized_calls.append((call_id, tool_name, arguments))
                    self.ui.print_tool_call(tool_name, arguments)
                    logger.debug(f"Queued parallel tool call: {tool_name}")
                else:
                    self.ui.print_warning(
                        "Invalid tool call: missing tool name. Skipping."
                    )
            except Exception as e:
                logger.exception(f"Error normalizing tool call: {e}")
                self.ui.print_error(f"Error normalizing tool call: {e}")

        # Collect all protected tools that require permission
        protected_tools = []
        batch_id = f"parallel-{int(time.time())}"
        for _, tool_name, arguments in normalized_calls:
            if (
                tool_name in self.tool_manager.tools
                and self.tool_manager.tools[tool_name].requires_confirmation
            ):
                if tool_name == "bash" and "command" in arguments:
                    permission_path = arguments
                else:
                    permission_path = None
                    for arg_name, arg_value in arguments.items():
                        if isinstance(arg_value, str) and arg_name in (
                            "path",
                            "file_path",
                        ):
                            permission_path = arg_value
                            break
                protected_tools.append((tool_name, permission_path))

        # Single permission for all protected calls
        if protected_tools:
            permission_text = "Permission required for the following operations:\n"
            for i, (tname, ppath) in enumerate(protected_tools, 1):
                if tname == "bash":
                    permission_text += (
                        f"{i}. Execute command: {ppath.get('command', 'unknown')}\n"
                    )
                elif ppath:
                    permission_text += f"{i}. {tname} on path: {ppath}\n"
                else:
                    permission_text += f"{i}. {tname} operation\n"

            # Pass the batch_id when prompting
            if not self.trust_manager.prompt_for_parallel_operations(
                protected_tools, permission_text, batch_id
            ):
                self.ui.print_warning("Permission denied for parallel operations")
                return

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(normalized_calls), 5)
        ) as executor:
            future_to_call = {
                executor.submit(
                    self.tool_manager.execute_tool,
                    tool_name,
                    arguments,
                    self.check_context_msg,
                    self.client_type,
                    batch_id,
                ): (call_id, tool_name)
                for (call_id, tool_name, arguments) in normalized_calls
            }

            for future in concurrent.futures.as_completed(future_to_call):
                call_id, tool_name = future_to_call[future]
                try:
                    raw_result = future.result()
                    result = self.tool_manager.format_tool_result(
                        raw_result, self.client_type
                    )
                    content = self._format_tool_result_as_natural_language(
                        tool_name, result
                    )
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": tool_name,
                            "content": content,
                        }
                    )
                except Exception as e:
                    logger.exception(
                        f"Error processing parallel tool call {tool_name}: {e}"
                    )
                    self.ui.print_error(
                        f"Error processing parallel tool call {tool_name}: {e}"
                    )

        self.token_manager.update_token_count(self.messages)

    def _cleanup_contextual_guidance(self) -> None:
        """Remove any 'Based on the user's request...' system messages."""
        i = len(self.messages) - 1
        removed = False
        while i >= 0:
            msg = self.messages[i]
            if msg.get("role") == "system" and msg.get("content", "").startswith(
                "Based on the user's request, consider using these tools:"
            ):
                self.messages.pop(i)
                removed = True
                break
            i -= 1

        if removed and self.ui.verbose:
            self.ui.console.print(
                "[dim cyan][Verbose] Removed follow-up contextual tool guidance from conversation history[/]"
            )
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

            self.messages.append(
                {"role": "user", "content": user_input}
            )  # Keep this line

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

            response = self.model_client.send(
                self.messages,
                functions=self.tool_manager.get_function_definitions(),
                include_reasoning=self.ui.verbose,
            )

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
            animation_thread.join(timeout=1.0)

            self.process_llm_response(response)
