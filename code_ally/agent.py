"""Agent implementation with refactored architecture.

This module contains the Agent class and supporting components that handle
the conversation flow, tool execution, and user interaction.
"""

import inspect
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table

from code_ally.config import load_config, save_config
from code_ally.llm_client import ModelClient
from code_ally.prompts import get_system_message, get_contextual_guidance, detect_relevant_tools
from code_ally.tools.base import BaseTool
from code_ally.trust import TrustManager

# Configure logging
logger = logging.getLogger(__name__)


class TokenManager:
    """Manages token counting and context window utilization."""

    def __init__(self, context_size: int):
        """Initialize the token manager.

        Args:
            context_size: Maximum context size in tokens
        """
        self.context_size = context_size
        self.estimated_tokens = 0
        self.token_buffer_ratio = 0.95  # Compact when at 95% of context size
        self.tokens_per_message = 4  # Tokens for message formatting
        self.tokens_per_name = 1  # Tokens for role names
        self.chars_per_token = 4.0  # Simple approximation (4 chars per token)
        self.last_compaction_time = 0
        self.min_compaction_interval = 300  # Seconds between auto-compactions
        self.ui = None  # Will be set by the Agent class

    def estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate token usage for a list of messages.

        Args:
            messages: List of messages to estimate

        Returns:
            Estimated token count
        """
        token_count = 0

        for message in messages:
            # Count tokens for message structure
            token_count += self.tokens_per_message

            # Count tokens for role
            if "role" in message:
                token_count += self.tokens_per_name

            # Count tokens for content (4 chars per token approximation)
            if "content" in message and message["content"]:
                content = message["content"]
                token_count += len(content) / self.chars_per_token

            # Count tokens for function calls
            if "function_call" in message and message["function_call"]:
                function_call = message["function_call"]
                # Count function name
                if "name" in function_call:
                    token_count += len(function_call["name"]) / self.chars_per_token
                # Count arguments
                if "arguments" in function_call:
                    token_count += (
                        len(function_call["arguments"]) / self.chars_per_token
                    )

        return int(token_count)

    def update_token_count(self, messages: List[Dict[str, Any]]) -> None:
        """Update the token count for the current messages.

        Args:
            messages: Current message list
        """
        previous_tokens = self.estimated_tokens
        self.estimated_tokens = self.estimate_tokens(messages)
        
        # Log in verbose mode if there's a significant change
        if self.ui and hasattr(self.ui, 'verbose') and self.ui.verbose:
            if abs(self.estimated_tokens - previous_tokens) > 100:
                token_percentage = self.get_token_percentage()
                change = self.estimated_tokens - previous_tokens
                change_sign = "+" if change > 0 else ""
                self.ui.console.print(
                    f"[dim yellow][Verbose] Token usage: {self.estimated_tokens} ({token_percentage}% of context) "
                    f"[{change_sign}{change} tokens][/]"
                )

    def should_compact(self) -> bool:
        """Check if the conversation should be compacted.

        Returns:
            True if compaction is needed, False otherwise
        """
        # Don't compact if we've recently compacted
        if time.time() - self.last_compaction_time < self.min_compaction_interval:
            return False

        # Compact if we're over the buffer threshold
        return (self.estimated_tokens / self.context_size) > self.token_buffer_ratio

    def get_token_percentage(self) -> int:
        """Get the percentage of context window used.

        Returns:
            Percentage (0-100) of context window used
        """
        if self.context_size <= 0:
            return 0
        return int(self.estimated_tokens / self.context_size * 100)


class UIManager:
    """Manages UI rendering and user interaction."""

    def __init__(self):
        """Initialize the UI manager."""
        self.console = Console()
        self.thinking_spinner = Spinner("dots2", text="[cyan]Thinking[/]")
        self.thinking_event = threading.Event()
        self.verbose = False

        # Create history directory if it doesn't exist
        history_dir = os.path.expanduser("~/.code_ally")
        os.makedirs(history_dir, exist_ok=True)

        # Initialize prompt session with command history
        history_file = os.path.join(history_dir, "command_history")
        self.prompt_session = PromptSession(history=FileHistory(history_file))

    def set_verbose(self, verbose: bool) -> None:
        """Set verbose mode.

        Args:
            verbose: Whether to enable verbose mode
        """
        self.verbose = verbose

    def start_thinking_animation(self, token_percentage: int = 0) -> threading.Thread:
        """Start the thinking animation in a separate thread.

        Args:
            token_percentage: Percentage of context window used

        Returns:
            The animation thread
        """
        self.thinking_event.clear()

        def animate():
            # Regular animation for non-verbose mode
            if not self.verbose:
                # Create spinner with token usage if available
                if token_percentage > 0:
                    if token_percentage > 80:
                        color = "red"
                    elif token_percentage > 50:
                        color = "yellow"
                    else:
                        color = "green"
                    context_info = f"({token_percentage}% context used)"
                    thinking_text = f"[cyan]Thinking[/] [dim {color}]{context_info}[/]"
                else:
                    thinking_text = "[cyan]Thinking[/]"

                thinking_spinner = Spinner("dots2", text=thinking_text)

                with Live(
                    thinking_spinner, refresh_per_second=10, console=self.console
                ) as live:
                    while not self.thinking_event.is_set():
                        live.update(thinking_spinner)
                        time.sleep(0.1)
            else:
                # In verbose mode, show a spinner with a message
                self.console.print(
                    "[bold cyan]🤔 VERBOSE MODE: Waiting for model to respond[/]",
                    highlight=False,
                )
                self.console.print(
                    "[dim]Complete model reasoning will be shown with the response[/]",
                    highlight=False,
                )

                with Live(
                    self.thinking_spinner, refresh_per_second=10, console=self.console
                ) as live:
                    while not self.thinking_event.is_set():
                        live.update(self.thinking_spinner)
                        time.sleep(0.1)

        # Start animation in a daemon thread
        thread = threading.Thread(target=animate, daemon=True)
        thread.start()
        return thread

    def stop_thinking_animation(self) -> None:
        """Stop the thinking animation."""
        self.thinking_event.set()

    def get_user_input(self) -> str:
        """Get user input with history navigation support.

        Returns:
            The user input string
        """
        return self.prompt_session.prompt("\n> ")

    def print_markdown(self, content: str) -> None:
        """Print markdown-formatted content.

        Args:
            content: The markdown content to print
        """
        self.console.print(Markdown(content))

    def print_assistant_response(self, content: str) -> None:
        """Print an assistant's response with proper formatting.

        Args:
            content: The content to print
        """
        # Check if the response includes thinking (verbose mode)
        if self.verbose and "THINKING:" in content:
            # Split into thinking and response
            parts = content.split("\n\n", 1)
            if len(parts) == 2 and parts[0].startswith("THINKING:"):
                thinking = parts[0]
                response = parts[1]

                # Display thinking in a panel
                thinking_panel = Panel(
                    Markdown(thinking),
                    title="[bold cyan]Thinking Process[/]",
                    border_style="cyan",
                )
                self.console.print(thinking_panel)

                # Display final response
                self.print_markdown(response)
            else:
                # Fall back to regular markdown if format is unexpected
                self.print_markdown(content)
        else:
            # Regular response
            self.print_markdown(content)

    def print_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        """Print a tool call notification.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
        """
        # Create a compact representation of the arguments
        args_str = ", ".join(f"{k}={v}" for k, v in arguments.items())
        self.console.print(f"[dim yellow]> Running {tool_name}({args_str})[/]")

    def print_error(self, message: str) -> None:
        """Print an error message.

        Args:
            message: The error message
        """
        self.console.print(f"[bold red]Error:[/] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message.

        Args:
            message: The warning message
        """
        self.console.print(f"[bold yellow]Warning:[/] {message}")

    def print_success(self, message: str) -> None:
        """Print a success message.

        Args:
            message: The success message
        """
        self.console.print(f"[bold green]✓[/] {message}")

    def print_help(self) -> None:
        """Print help information."""
        help_text = """
# Code Ally Commands

- `/help` - Show this help message
- `/clear` - Clear the conversation history
- `/config` - Show or update configuration settings
- `/debug` - Toggle debug mode
- `/dump` - Dump the conversation history to file
- `/compact` - Compact the conversation to reduce context size
- `/trust` - Show trust status for tools
- `/verbose` - Toggle verbose mode (show model thinking)

Type a message to chat with the AI assistant.
Use up/down arrow keys to navigate through command history.
"""
        self.console.print(Markdown(help_text))


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

        # Track recent tool calls to avoid redundancy
        self.recent_tool_calls: List[Tuple[str, Dict[str, Any]]] = []
        self.max_recent_calls = 5  # Remember last 5 calls

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
                    # Handle Optional types
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
        # Check for redundant calls - with special handling for LS
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
        self, tool_name: str, arguments: Dict[str, Any], check_context_msg: bool = True
    ) -> Dict[str, Any]:
        """Execute a tool with the given arguments after checking trust.

        Args:
            tool_name: The name of the tool to execute
            arguments: The arguments to pass to the tool
            check_context_msg: Whether to add context check message for redundant calls

        Returns:
            The result of the tool execution
        """
        # Track execution time
        start_time = time.time()
        
        # Verbose logging - start
        verbose_mode = hasattr(self, 'ui') and getattr(self, 'ui', None) and getattr(self.ui, 'verbose', False)
        if verbose_mode:
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in arguments.items())
            self.ui.console.print(f"[dim magenta][Verbose] Starting tool execution: {tool_name}({args_str})[/]")

        # Check if the tool exists
        if tool_name not in self.tools:
            if verbose_mode:
                self.ui.console.print(f"[dim red][Verbose] Tool not found: {tool_name}[/]")
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
            }

        tool = self.tools[tool_name]

        # Check for redundant calls
        if self.is_redundant_call(tool_name, arguments):
            # For LS tool with redundant calls
            if tool_name == "ls":
                # Return a response with guidance if enabled
                error_msg = (
                    f"Redundant call to {tool_name}. Directory was already shown."
                )
                if check_context_msg:
                    error_msg += " Please check your context for the previous result."
                
                if verbose_mode:
                    self.ui.console.print(f"[dim yellow][Verbose] Redundant tool call detected: {tool_name}[/]")

                return {
                    "success": False,
                    "error": error_msg,
                }

        # Add to recent calls list
        self.record_tool_call(tool_name, arguments)

        # Check permissions if tool requires confirmation
        if tool.requires_confirmation:
            if verbose_mode:
                self.ui.console.print(f"[dim blue][Verbose] Tool {tool_name} requires confirmation[/]")
                
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

            # Check if the user has given permission
            if not self.trust_manager.prompt_for_permission(tool_name, permission_path):
                if verbose_mode:
                    self.ui.console.print(f"[dim red][Verbose] Permission denied for {tool_name}[/]")
                return {
                    "success": False,
                    "error": f"Permission denied for {tool_name}",
                }

        # Execute the tool
        try:
            if verbose_mode:
                self.ui.console.print(f"[dim green][Verbose] Executing tool: {tool_name}[/]")
                
            result = tool.execute(**arguments)
            execution_time = time.time() - start_time
            
            if verbose_mode:
                self.ui.console.print(
                    f"[dim green][Verbose] Tool {tool_name} executed in {execution_time:.2f}s "
                    f"(success: {result.get('success', False)})[/]"
                )
                
            logger.debug("Tool %s executed in %.2fs", tool_name, execution_time)
            return result
        except Exception as exc:
            logger.exception("Error executing tool %s", tool_name)
            if verbose_mode:
                self.ui.console.print(f"[dim red][Verbose] Error executing {tool_name}: {str(exc)}[/]")
            return {
                "success": False,
                "error": f"Error executing {tool_name}: {str(exc)}",
            }


class CommandHandler:
    """Handles special commands in the conversation."""

    def __init__(
        self,
        ui_manager: UIManager,
        token_manager: TokenManager,
        trust_manager: TrustManager,
    ):
        """Initialize the command handler.

        Args:
            ui_manager: UI manager for display
            token_manager: Token manager for context tracking
            trust_manager: Trust manager for permissions
        """
        self.ui = ui_manager
        self.token_manager = token_manager
        self.trust_manager = trust_manager
        self.verbose = False
        self.agent = None  # Will be set by Agent class after initialization

    def set_verbose(self, verbose: bool) -> None:
        """Set verbose mode.

        Args:
            verbose: Whether to enable verbose mode
        """
        self.verbose = verbose

    def handle_command(
        self, command: str, arg: str, messages: List[Dict[str, Any]]
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Handle a special command.

        Args:
            command: The command (without the leading slash)
            arg: Arguments provided with the command
            messages: Current message list

        Returns:
            Tuple (handled, updated_messages)
        """
        command = command.lower()

        if command == "help":
            self.ui.print_help()
            return True, messages

        if command == "clear":
            # Keep only the system message if present
            cleared_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    cleared_messages.append(msg)

            self.ui.print_success("Conversation history cleared")
            # Update token count
            self.token_manager.update_token_count(cleared_messages)
            return True, cleared_messages

        if command == "compact":
            compacted = self.compact_conversation(messages)
            self.token_manager.update_token_count(compacted)
            token_pct = self.token_manager.get_token_percentage()
            self.ui.print_success(
                f"Conversation compacted: {token_pct}% of context window used"
            )
            return True, compacted

        if command == "config":
            return self.handle_config_command(arg, messages)

        if command == "debug":
            # Toggle verbose mode
            self.verbose = not self.verbose
            self.ui.set_verbose(self.verbose)
            if self.verbose:
                self.ui.print_success("Debug mode enabled")
            else:
                self.ui.print_success("Debug mode disabled")
            return True, messages

        if command == "verbose":
            # Toggle verbose mode
            self.verbose = not self.verbose
            self.ui.set_verbose(self.verbose)
            if self.verbose:
                self.ui.print_success("Verbose mode enabled")
            else:
                self.ui.print_success("Verbose mode disabled")
            return True, messages

        if command == "dump":
            self.dump_conversation(messages, arg)
            return True, messages

        if command == "trust":
            self.show_trust_status()
            return True, messages

        # Handle unknown commands
        self.ui.print_error(f"Unknown command: /{command}")
        return True, messages

    def handle_config_command(
        self, arg: str, messages: List[Dict[str, Any]]
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Handle the config command.

        Args:
            arg: Command arguments
            messages: Current message list

        Returns:
            Tuple (handled, updated_messages)
        """
        # Load current config
        config = load_config()

        # Show current config if no arguments
        if not arg:
            # Display config in a table
            table = Table(title="Current Configuration")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="green")

            for key, value in sorted(config.items()):
                table.add_row(key, str(value))

            self.ui.console.print(table)
            return True, messages

        # Parse key=value format
        parts = arg.split("=", 1)
        if len(parts) != 2:
            self.ui.print_error(
                "Invalid format. Use /config key=value or /config to show all settings."
            )
            return True, messages

        key, value = parts[0].strip(), parts[1].strip()

        # Handle special case for auto_confirm
        if key == "auto_confirm":
            value_lower = value.lower()
            if value_lower in ("true", "yes", "y", "1"):
                self.trust_manager.set_auto_confirm(True)
                config["auto_confirm"] = True
            elif value_lower in ("false", "no", "n", "0"):
                self.trust_manager.set_auto_confirm(False)
                config["auto_confirm"] = False
            else:
                self.ui.print_error(
                    "Invalid value for auto_confirm. Use 'true' or 'false'."
                )
                return True, messages
        # Handle special case for auto_dump
        elif key == "auto_dump":
            value_lower = value.lower()
            if value_lower in ("true", "yes", "y", "1"):
                if self.agent:
                    self.agent.auto_dump = True
                config["auto_dump"] = True
            elif value_lower in ("false", "no", "n", "0"):
                if self.agent:
                    self.agent.auto_dump = False
                config["auto_dump"] = False
            else:
                self.ui.print_error(
                    "Invalid value for auto_dump. Use 'true' or 'false'."
                )
                return True, messages
        else:
            # Update config with the new value
            config[key] = value

        # Save config
        save_config(config)
        self.ui.print_success(f"Configuration updated: {key}={value}")
        return True, messages

    def compact_conversation(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Compact the conversation to reduce context size.

        Args:
            messages: Current message list

        Returns:
            Compacted message list
        """
        # Log compaction start in verbose mode
        if self.verbose:
            message_count = len(messages)
            tokens_before = self.token_manager.estimated_tokens
            percent_used = self.token_manager.get_token_percentage()
            self.ui.console.print(
                f"[dim cyan][Verbose] Starting conversation compaction. "
                f"Current state: {message_count} messages, {tokens_before} tokens "
                f"({percent_used}% of context)[/]"
            )
            
        # Preserve system message
        system_message = None
        for msg in messages:
            if msg.get("role") == "system":
                system_message = msg
                break

        # If we have fewer than 4 messages, nothing to compact
        if len(messages) < 4:
            if self.verbose:
                self.ui.console.print(
                    f"[dim yellow][Verbose] Not enough messages to compact (only {len(messages)} messages)[/]"
                )
            return messages

        # Start with the system message if present
        compacted = []
        if system_message:
            compacted.append(system_message)

        # Keep first user message for context
        first_user_msg_found = False
        for msg in messages:
            if msg.get("role") == "user" and not first_user_msg_found:
                compacted.append(msg)
                first_user_msg_found = True
                break

        # Add a summary marker
        compacted.append(
            {
                "role": "system",
                "content": get_system_message("compaction_notice"),
            }
        )

        # Keep the last 6 messages for recent context
        compacted.extend(messages[-6:])

        # Update the last compaction time
        self.token_manager.last_compaction_time = time.time()
        
        # Log compaction results in verbose mode
        if self.verbose:
            # Calculate the impact
            messages_removed = len(messages) - len(compacted)
            self.token_manager.update_token_count(compacted)
            tokens_after = self.token_manager.estimated_tokens
            tokens_saved = tokens_before - tokens_after
            new_percent = self.token_manager.get_token_percentage()
            
            self.ui.console.print(
                f"[dim green][Verbose] Compaction complete. Removed {messages_removed} messages, "
                f"saved {tokens_saved} tokens. New usage: {tokens_after} tokens "
                f"({new_percent}% of context)[/]"
            )

        return compacted

    def dump_conversation(self, messages: List[Dict[str, Any]], filename: str) -> None:
        """Dump the conversation history to a file.

        Args:
            messages: Current message list
            filename: Filename to use (or auto-generate if empty)
        """
        # Load dump directory from config
        config = load_config()
        dump_dir = config.get("dump_dir", "ally")

        # Create the directory if it doesn't exist
        os.makedirs(dump_dir, exist_ok=True)

        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_{timestamp}.json"

        # Create the full path with the dump directory
        filepath = os.path.join(dump_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as file:
                json.dump(messages, file, indent=2)
            self.ui.print_success(f"Conversation saved to {filepath}")
        except Exception as exc:
            self.ui.print_error(f"Error saving conversation: {str(exc)}")

    def show_trust_status(self) -> None:
        """Show trust status for all tools."""
        table = Table(title="Tool Trust Status")
        table.add_column("Tool", style="cyan")
        table.add_column("Status", style="green")

        # Auto-confirm status
        if self.trust_manager.auto_confirm:
            self.ui.print_warning(
                "Auto-confirm is enabled - all actions are automatically approved"
            )

        # Display trust status for each tool
        for tool_name in sorted(self.trust_manager.trusted_tools.keys()):
            description = self.trust_manager.get_permission_description(tool_name)
            table.add_row(tool_name, description)

        self.ui.console.print(table)


class Agent:
    """The main agent class that manages the conversation and tool execution."""

    def __init__(
        self,
        model_client: ModelClient,
        tools: List[BaseTool],
        system_prompt: Optional[str] = None,
        verbose: bool = False,
        check_context_msg: bool = True,
        auto_dump: bool = True,
    ):
        """Initialize the agent.

        Args:
            model_client: The LLM client to use
            tools: List of available tools
            system_prompt: The system prompt to use (optional)
            verbose: Whether to enable verbose mode (defaults to False)
            check_context_msg: Whether to encourage LLM to check context when redundant
                              tool calls are detected (defaults to True)
            auto_dump: Whether to automatically dump conversation on exit (defaults to True)
        """
        self.model_client = model_client
        self.trust_manager = TrustManager()
        self.messages: List[Dict[str, Any]] = []
        self.check_context_msg = check_context_msg
        self.auto_dump = auto_dump

        # Initialize component managers
        self.ui = UIManager()
        self.ui.set_verbose(verbose)

        self.token_manager = TokenManager(model_client.context_size)
        self.token_manager.ui = self.ui  # Set UI reference in token manager

        self.tool_manager = ToolManager(tools, self.trust_manager)
        self.tool_manager.ui = self.ui  # Set UI reference in tool manager

        self.command_handler = CommandHandler(
            self.ui, self.token_manager, self.trust_manager
        )
        self.command_handler.set_verbose(verbose)
        self.command_handler.agent = self  # Set the reference to this agent

        # Add system prompt if provided
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})
            self.token_manager.update_token_count(self.messages)

    def process_llm_response(self, response: Dict[str, Any]) -> None:
        """Process the LLM's response and execute any tool calls.

        Args:
            response: The LLM's response
        """
        # Extract content and tool calls
        content = response.get("content", "")

        # Handle tool calls if present
        tool_calls = response.get("tool_calls", [])

        if tool_calls:
            # Add assistant message with tool calls to history
            self.messages.append(response)
            self.token_manager.update_token_count(self.messages)

            # Execute each tool call
            for tool_call in tool_calls:
                # Extract tool information
                call_id = tool_call.get("id", "")
                function_call = tool_call.get("function", {})
                tool_name = function_call.get("name", "")

                # Parse arguments
                arguments_raw = function_call.get("arguments", "{}")
                if isinstance(arguments_raw, dict):
                    arguments = arguments_raw
                else:
                    try:
                        arguments = json.loads(arguments_raw)
                    except json.JSONDecodeError:
                        arguments = {}

                # Show tool call
                self.ui.print_tool_call(tool_name, arguments)

                # Execute the tool
                result = self.tool_manager.execute_tool(
                    tool_name, arguments, self.check_context_msg
                )

                # Add tool result to message history
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "content": json.dumps(result),
                    }
                )

            # Update token count
            self.token_manager.update_token_count(self.messages)

            # Find the last user message to extract context
            last_user_message = ""
            for msg in reversed(self.messages):
                if msg.get("role") == "user":
                    last_user_message = msg.get("content", "")
                    break
            
            # Add contextual tool guidance for follow-up if appropriate
            if last_user_message:
                tool_guidance = get_contextual_guidance(last_user_message)
                relevant_tools = detect_relevant_tools(last_user_message)
                
                if tool_guidance and relevant_tools:
                    tool_names = ", ".join(relevant_tools)
                    guidance_message = f"Based on the user's request, consider using these tools: {tool_names}. Here is specific guidance for these tools:\n\n{tool_guidance}"
                    self.messages.append({"role": "system", "content": guidance_message})
                    
                    # Log in verbose mode
                    if self.ui.verbose:
                        self.ui.console.print(f"[dim cyan][Verbose] Added follow-up contextual guidance for tools: {tool_names}[/]")
                    
                    self.token_manager.update_token_count(self.messages)

            # Get a follow-up response from the LLM
            animation_thread = self.ui.start_thinking_animation(
                self.token_manager.get_token_percentage()
            )
            
            # Verbose logging before follow-up LLM request
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
            
            # Verbose logging after follow-up LLM response
            if self.ui.verbose:
                has_tool_calls = "tool_calls" in follow_up_response and follow_up_response["tool_calls"]
                tool_names = []
                if has_tool_calls:
                    for tool_call in follow_up_response["tool_calls"]:
                        if "function" in tool_call and "name" in tool_call["function"]:
                            tool_names.append(tool_call["function"]["name"])
                
                response_type = "tool calls" if has_tool_calls else "text response"
                tools_info = f" ({', '.join(tool_names)})" if tool_names else ""
                
                self.ui.console.print(
                    f"[dim blue][Verbose] Received follow-up {response_type}{tools_info} from LLM[/]"
                )

            self.ui.stop_thinking_animation()
            animation_thread.join(timeout=1.0)

            # Process the follow-up response recursively
            self.process_llm_response(follow_up_response)
            
            # Clean up the contextual tool guidance message if it was added
            if last_user_message:
                # Find and remove the contextual guidance system message
                i = len(self.messages) - 1
                removed = False
                while i >= 0:
                    msg = self.messages[i]
                    if (msg.get("role") == "system" and 
                        msg.get("content", "").startswith("Based on the user's request, consider using these tools:")):
                        self.messages.pop(i)
                        removed = True
                        break
                    i -= 1
                
                # Log in verbose mode
                if removed and self.ui.verbose:
                    self.ui.console.print("[dim cyan][Verbose] Removed follow-up contextual tool guidance from conversation history[/]")
                
                # Update token count after removing guidance
                self.token_manager.update_token_count(self.messages)

        else:
            # Regular text response
            self.messages.append(response)
            self.token_manager.update_token_count(self.messages)

            # Display the response
            self.ui.print_assistant_response(content)

    def run_conversation(self) -> None:
        """Run the conversation loop."""
        self.ui.print_help()

        while True:
            # Check if we need to compact the conversation
            if self.token_manager.should_compact():
                old_percentage = self.token_manager.get_token_percentage()
                self.messages = self.command_handler.compact_conversation(self.messages)
                self.token_manager.update_token_count(self.messages)
                new_percentage = self.token_manager.get_token_percentage()

                compact_msg = f"Auto-compacted: {old_percentage}% → {new_percentage}%"
                self.ui.print_warning(compact_msg)

            # Get user input with history navigation
            try:
                user_input = self.ui.get_user_input()
            except EOFError:
                # Only dump conversation if auto_dump is enabled
                if self.auto_dump:
                    self.command_handler.dump_conversation(self.messages, "")
                break

            # Handle empty input
            if not user_input.strip():
                continue

            # Check for special commands (starting with /)
            if user_input.startswith("/"):
                parts = user_input[1:].split(" ", 1)
                command = parts[0].strip()
                arg = parts[1].strip() if len(parts) > 1 else ""

                handled, self.messages = self.command_handler.handle_command(
                    command, arg, self.messages
                )

                if handled:
                    continue

            # Get contextual tool guidance based on user input
            tool_guidance = get_contextual_guidance(user_input)
            relevant_tools = detect_relevant_tools(user_input)
            
            # Add user message to history
            self.messages.append({"role": "user", "content": user_input})
            
            # Add contextual tool guidance if appropriate
            if tool_guidance and relevant_tools:
                tool_names = ", ".join(relevant_tools)
                guidance_message = f"Based on the user's request, consider using these tools: {tool_names}. Here is specific guidance for these tools:\n\n{tool_guidance}"
                self.messages.append({"role": "system", "content": guidance_message})
                
                # Log in verbose mode
                if self.ui.verbose:
                    self.ui.console.print(f"[dim cyan][Verbose] Added contextual guidance for tools: {tool_names}[/]")
            
            self.token_manager.update_token_count(self.messages)

            # Start thinking animation
            animation_thread = self.ui.start_thinking_animation(
                self.token_manager.get_token_percentage()
            )

            # Verbose logging before LLM request
            if self.ui.verbose:
                functions_count = len(self.tool_manager.get_function_definitions())
                message_count = len(self.messages)
                tokens = self.token_manager.estimated_tokens
                self.ui.console.print(
                    f"[dim blue][Verbose] Sending request to LLM with {message_count} messages, "
                    f"{tokens} tokens, {functions_count} available functions[/]"
                )
            
            # Get response from LLM
            response = self.model_client.send(
                self.messages,
                functions=self.tool_manager.get_function_definitions(),
                include_reasoning=self.ui.verbose,
            )
            
            # Verbose logging after LLM response
            if self.ui.verbose:
                has_tool_calls = "tool_calls" in response and response["tool_calls"]
                tool_names = []
                if has_tool_calls:
                    for tool_call in response["tool_calls"]:
                        if "function" in tool_call and "name" in tool_call["function"]:
                            tool_names.append(tool_call["function"]["name"])
                
                response_type = "tool calls" if has_tool_calls else "text response"
                tools_info = f" ({', '.join(tool_names)})" if tool_names else ""
                
                self.ui.console.print(
                    f"[dim blue][Verbose] Received {response_type}{tools_info} from LLM[/]"
                )

            # Stop animation
            self.ui.stop_thinking_animation()
            animation_thread.join(timeout=1.0)

            # Process the response
            self.process_llm_response(response)
            
            # Clean up the contextual tool guidance message if it was added
            # This prevents accumulation of guidance messages in the history
            if relevant_tools:
                # Find and remove the contextual guidance system message
                i = len(self.messages) - 1
                removed = False
                while i >= 0:
                    msg = self.messages[i]
                    if (msg.get("role") == "system" and 
                        msg.get("content", "").startswith("Based on the user's request, consider using these tools:")):
                        self.messages.pop(i)
                        removed = True
                        break
                    i -= 1
                
                # Log in verbose mode
                if removed and self.ui.verbose:
                    self.ui.console.print("[dim cyan][Verbose] Removed contextual tool guidance from conversation history[/]")
                
                # Update token count after removing guidance
                self.token_manager.update_token_count(self.messages)
