"""Prompt templates for Code Ally."""

from code_ally.prompts.system_messages import (
    SYSTEM_MESSAGES,
    get_system_message,
    get_main_system_prompt,
    get_contextual_guidance,
    detect_relevant_tools,
)

# Only expose the necessary functions and constants
__all__ = [
    "get_system_message",
    "get_main_system_prompt",
    "get_contextual_guidance",
    "detect_relevant_tools",
]
