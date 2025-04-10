"""File: error_handler.py.

Provides error handling and formatting utilities for agents.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def format_error_message(
    error_msg: str,
    tool_name: str,
    arguments: dict[str, Any],
    task_id: str | None = None,
    task_desc: str | None = None,
) -> dict[str, Any]:
    """Format an error message with context details.

    Args:
        error_msg: The raw error message
        tool_name: The name of the tool that failed
        arguments: The arguments used in the tool call
        task_id: Optional task ID (for task plan errors)
        task_desc: Optional task description (for task plan errors)

    Returns:
        Dictionary with formatted error messages and suggestions
    """
    # Format arguments string (excluding large content values)
    args_str = ", ".join(
        f"{k}={v}" for k, v in arguments.items() if k != "content" and len(str(v)) < 50
    )

    # Build context message
    if task_id and task_desc:
        context = f"The task '{task_id}' ({task_desc}) failed while using the '{tool_name}' tool"
    else:
        context = f"The tool '{tool_name}' failed"

    error_note = f"{context} with arguments {args_str}. The error was: {error_msg}"

    # Determine possible fixes based on error type
    possible_fix = None
    if "file not found" in error_msg.lower() or "no such file" in error_msg.lower():
        possible_fix = "Check that the file path is correct and the file exists."
    elif "permission denied" in error_msg.lower():
        possible_fix = "Check file permissions or try a different approach."
    elif "syntax error" in error_msg.lower():
        possible_fix = "Review the syntax and fix any errors."
    elif "command not found" in error_msg.lower():
        possible_fix = "Verify the command exists and is spelled correctly."
    elif "timeout" in error_msg.lower():
        possible_fix = (
            "The operation took too long. Consider optimizing or breaking it down."
        )

    return {"error_note": error_note, "possible_fix": possible_fix}


def display_error(
    ui_manager: "UIManager",
    error_msg: str,
    tool_name: str,
    arguments: dict[str, Any],
    task_id: str | None = None,
    task_desc: str | None = None,
) -> None:
    """Display formatted error messages to the user.

    Args:
        ui_manager: The UI manager instance
        error_msg: The raw error message
        tool_name: The name of the tool that failed
        arguments: The arguments used in the tool call
        task_id: Optional task ID (for task plan errors)
        task_desc: Optional task description (for task plan errors)
    """
    if not ui_manager:
        return

    # Get formatted error messages
    formatted = format_error_message(
        error_msg,
        tool_name,
        arguments,
        task_id,
        task_desc,
    )

    # Use Rich formatting for the error note
    ui_manager.print_content(f"[yellow bold]Error Note:[/] {formatted['error_note']}")

    # Display suggestion if available
    if formatted["possible_fix"]:
        ui_manager.print_content(f"[blue]Possible fix:[/] {formatted['possible_fix']}")
