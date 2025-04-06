"""File: command_handler.py

Handles special (slash) commands in the conversation.
"""

import json
import os
import time
import logging
from typing import Any, Dict, List, Tuple

from rich.table import Table

from code_ally.config import load_config, save_config
from code_ally.prompts import get_system_message
from code_ally.trust import TrustManager


logger = logging.getLogger(__name__)


class CommandHandler:
    """Handles special commands in the conversation."""

    def __init__(
        self,
        ui_manager,
        token_manager,
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

        # Handle special cases with type conversion
        try:
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

            # LLM model client settings
            elif key == "temperature" and self.agent and self.agent.model_client:
                try:
                    temp_value = float(value)
                    self.agent.model_client.temperature = temp_value
                    config["temperature"] = temp_value
                    self.ui.print_success(
                        f"Temperature updated to {temp_value} for current session"
                    )
                except ValueError:
                    self.ui.print_error(
                        f"Invalid temperature value: {value}. Must be a number."
                    )
                    return True, messages

            elif key == "context_size" and self.agent and self.agent.model_client:
                try:
                    ctx_value = int(value)
                    self.agent.model_client.context_size = ctx_value
                    self.agent.token_manager.context_size = (
                        ctx_value  # Update token manager too
                    )
                    config["context_size"] = ctx_value
                    self.ui.print_success(
                        f"Context size updated to {ctx_value} for current session"
                    )
                except ValueError:
                    self.ui.print_error(
                        f"Invalid context_size value: {value}. Must be a number."
                    )
                    return True, messages

            elif key == "max_tokens" and self.agent and self.agent.model_client:
                try:
                    max_tok_value = int(value)
                    self.agent.model_client.max_tokens = max_tok_value
                    config["max_tokens"] = max_tok_value
                    self.ui.print_success(
                        f"Max tokens updated to {max_tok_value} for current session"
                    )
                except ValueError:
                    self.ui.print_error(
                        f"Invalid max_tokens value: {value}. Must be a number."
                    )
                    return True, messages

            elif key == "model" and self.agent and self.agent.model_client:
                current_model = self.agent.model_client.model_name
                self.ui.print_warning(
                    f"Model can't be changed in current session (current: {current_model}). "
                    f"This setting will apply on restart."
                )
                config["model"] = value

            elif key == "check_context_msg" and self.agent:
                value_lower = value.lower()
                if value_lower in ("true", "yes", "y", "1"):
                    self.agent.check_context_msg = True
                    config["check_context_msg"] = True
                    self.ui.print_success(
                        "Check context message enabled for current session"
                    )
                elif value_lower in ("false", "no", "n", "0"):
                    self.agent.check_context_msg = False
                    config["check_context_msg"] = False
                    self.ui.print_success(
                        "Check context message disabled for current session"
                    )
                else:
                    self.ui.print_error(
                        "Invalid value for check_context_msg. Use 'true' or 'false'."
                    )
                    return True, messages

            elif key == "parallel_tools" and self.agent:
                value_lower = value.lower()
                if value_lower in ("true", "yes", "y", "1"):
                    self.agent.parallel_tools = True
                    config["parallel_tools"] = True
                    self.ui.print_success("Parallel tools enabled for current session")
                elif value_lower in ("false", "no", "n", "0"):
                    self.agent.parallel_tools = False
                    config["parallel_tools"] = False
                    self.ui.print_success("Parallel tools disabled for current session")
                else:
                    self.ui.print_error(
                        "Invalid value for parallel_tools. Use 'true' or 'false'."
                    )
                    return True, messages

            elif key == "compact_threshold" and self.agent and self.agent.token_manager:
                try:
                    threshold = int(value)
                    self.agent.token_manager.token_buffer_ratio = threshold / 100.0
                    config["compact_threshold"] = threshold
                    self.ui.print_success(
                        f"Compact threshold updated to {threshold}% for current session"
                    )
                except ValueError:
                    self.ui.print_error(
                        f"Invalid compact_threshold value: {value}. Must be a number."
                    )
                    return True, messages

            elif key == "verbose" and self.agent:
                value_lower = value.lower()
                if value_lower in ("true", "yes", "y", "1"):
                    self.agent.ui.set_verbose(True)
                    self.set_verbose(True)
                    config["verbose"] = True
                    self.ui.print_success("Verbose mode enabled for current session")
                elif value_lower in ("false", "no", "n", "0"):
                    self.agent.ui.set_verbose(False)
                    self.set_verbose(False)
                    config["verbose"] = False
                    self.ui.print_success("Verbose mode disabled for current session")
                else:
                    self.ui.print_error(
                        "Invalid value for verbose. Use 'true' or 'false'."
                    )
                    return True, messages

            else:
                # For other settings, just update the config file
                config[key] = value
                self.ui.print_success(
                    f"Configuration {key}={value} will apply on restart"
                )

        except Exception as e:
            self.ui.print_error(f"Error updating configuration: {str(e)}")
            return True, messages

        # Save to config file
        save_config(config)
        self.ui.print_success(f"Configuration updated and saved: {key}={value}")
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

        self.token_manager.last_compaction_time = time.time()

        if self.verbose:
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
        config = load_config()
        dump_dir = config.get("dump_dir", "ally")
        os.makedirs(dump_dir, exist_ok=True)

        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_{timestamp}.json"

        filepath = os.path.join(dump_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as file:
                json.dump(messages, file, indent=2)
            self.ui.print_success(f"Conversation saved to {filepath}")
        except Exception as exc:
            self.ui.print_error(f"Error saving conversation: {str(exc)}")

    def show_trust_status(self) -> None:
        """Show trust status for all tools."""
        from rich.table import Table

        table = Table(title="Tool Trust Status")
        table.add_column("Tool", style="cyan")
        table.add_column("Status", style="green")

        if self.trust_manager.auto_confirm:
            self.ui.print_warning(
                "Auto-confirm is enabled - all actions are automatically approved"
            )

        for tool_name in sorted(self.trust_manager.trusted_tools.keys()):
            description = self.trust_manager.get_permission_description(tool_name)
            table.add_row(tool_name, description)

        self.ui.console.print(table)
