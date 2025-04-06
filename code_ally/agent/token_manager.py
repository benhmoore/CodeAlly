"""File: token_manager.py

Manages token counting and context window utilization.
"""

import time
import json
from typing import Any, Dict, List


class TokenManager:
    """Manages token counting and context window utilization."""

    def __init__(self, context_size: int):
        """Initialize the token manager.

        Args:
            context_size: Maximum context size in tokens.
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
        # Cache for token counts to avoid re-estimation
        self._token_cache = {}

    def estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate token usage for a list of messages.

        Args:
            messages: List of messages to estimate

        Returns:
            Estimated token count
        """
        token_count = 0

        for message in messages:
            # Create a message cache key based on content and role
            cache_key = None
            if "role" in message and "content" in message:
                cache_key = (message["role"], message["content"])

            # Use cached count if available
            if cache_key and cache_key in self._token_cache:
                token_count += self._token_cache[cache_key]
                continue

            # Otherwise calculate the token count
            message_tokens = 0
            # Count tokens for message structure
            message_tokens += self.tokens_per_message

            # Count tokens for role
            if "role" in message:
                message_tokens += self.tokens_per_name

            # Count tokens for content (4 chars per token approximation)
            if "content" in message and message["content"]:
                content = message["content"]
                message_tokens += len(content) / self.chars_per_token

            # Count tokens for function calls
            if "function_call" in message and message["function_call"]:
                function_call = message["function_call"]
                # Count function name
                if "name" in function_call:
                    message_tokens += len(function_call["name"]) / self.chars_per_token
                # Count arguments
                if "arguments" in function_call:
                    message_tokens += (
                        len(function_call["arguments"]) / self.chars_per_token
                    )

            # Count tokens for tool calls
            if "tool_calls" in message and message["tool_calls"]:
                for tool_call in message["tool_calls"]:
                    if "function" in tool_call:
                        function = tool_call["function"]
                        if "name" in function:
                            message_tokens += (
                                len(function["name"]) / self.chars_per_token
                            )
                        if "arguments" in function:
                            if isinstance(function["arguments"], str):
                                message_tokens += (
                                    len(function["arguments"]) / self.chars_per_token
                                )
                            elif isinstance(function["arguments"], dict):
                                message_tokens += (
                                    len(json.dumps(function["arguments"]))
                                    / self.chars_per_token
                                )

            # Store in cache if we have a key
            if cache_key:
                self._token_cache[cache_key] = message_tokens

            # Add to total count
            token_count += message_tokens

        return max(1, int(token_count))  # Ensure at least 1 token

    def clear_cache(self) -> None:
        """Clear the token count cache."""
        self._token_cache = {}

    def update_token_count(self, messages: List[Dict[str, Any]]) -> None:
        """Update the token count for the current messages.

        Args:
            messages: Current message list
        """
        previous_tokens = self.estimated_tokens
        self.estimated_tokens = self.estimate_tokens(messages)

        # Log in verbose mode if there's a significant change
        if self.ui and hasattr(self.ui, "verbose") and self.ui.verbose:
            if abs(self.estimated_tokens - previous_tokens) > 100:
                token_percentage = self.get_token_percentage()
                change = self.estimated_tokens - previous_tokens
                change_sign = "+" if change > 0 else ""
                self.ui.console.print(
                    f"[dim yellow][Verbose] Token usage: {self.estimated_tokens} "
                    f"({token_percentage}% of context) [{change_sign}{change} tokens][/]"
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
