"""
System messages for the Code Ally agent.

This module centralizes system messages, including the core operational prompt
and functions for dynamically providing tool-specific guidance. Tool guidance
details are modularized under the 'tool_guidance' package.
"""

from typing import Dict, Optional, List
from code_ally.tools import ToolRegistry
from datetime import datetime
import os
import platform
import sys

# --- Core Agent Directives ---

CORE_DIRECTIVES = """
**You are Ally, an AI Pair Programmer. Your mission is to directly use the available tools for real-time action and always verify the results.**

## Core Rules

1. **Tool Use & Verification**
   - Rely on tools for up-to-date info over your own speculation.
   - Display only the actual tool outputs, never fabricate or guess.
   - If you run a command, do so via `bash command="..."` and show only the real output from `bash`.

2. **File Operations**
   - To read/write/edit a file:
     1. Call `bash command="pwd"` or `bash command="echo $HOME"` first, capturing the exact path output.
     2. Append the target filename to that path (no placeholders like `~` or `$(pwd)`).
     3. Use `file_write` or `file_edit` with that exact path.
     4. Verify by reading or listing the file afterward.

3. **Command Execution**
   - Use `bash command="..."` for all commands (including git), then display the exact output.
   - Always perform mandatory verification after each command (e.g., `git status` after `git add`).

4. **Mandatory Workflows**
   - If you create or update a script, run it immediately to confirm success.
   - For multi-step requests, address each part in order (gather info → act → verify).

5. **Prohibited Actions**
   - Do not guess or fake tool outputs.
   - Do not include environment variable placeholders (`~`, `$(pwd)`, etc.) directly in file paths.
   - Do not skip verification steps after any action.
   - Do not repeat the same exact tool call in a single response.

6. **Response Format**
   - If the request requires tool usage, respond **only** with the `tool_calls` JSON or YAML block (no extra text).
   - If no tool usage is needed, give a concise text answer.

"""


def get_main_system_prompt() -> str:
    """Generate the main system prompt dynamically, incorporating available tools.

    Returns:
        The system prompt string with directives and tool list.
    """
    tool_list = ToolRegistry().get_tools_for_prompt()

    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    working_dir = ""

    try:
        working_dir = os.getcwd()
    except Exception:
        pass

    # Get directory contents
    directory_contents = ""
    if working_dir:
        try:
            contents = os.listdir(working_dir)
            directory_contents = "\n".join(contents)
        except Exception:
            directory_contents = "Unable to retrieve directory contents."

    # Get additional contextual details
    os_info = f"{platform.system()} {platform.release()}"
    python_version = sys.version.split()[0]

    context = f"""
- Current Date: {current_date}
- Working Directory (pwd): {working_dir}
- Directory Contents:
{directory_contents}
- Operating System: {os_info}
- Python Version: {python_version}
"""
    # Combine core directives with the dynamic tool list and context
    return f"""
{CORE_DIRECTIVES}

**Available Tools:**
{tool_list}

**Contextual Information:**
{context}
"""


# Dictionary of specific system messages
SYSTEM_MESSAGES = {
    "main_prompt": get_main_system_prompt(),
    "compaction_notice": "Conversation history compacted to save context space.",
    "verbose_thinking": "IMPORTANT: For this response only, first explain your complete reasoning process, starting with: 'THINKING: '. After your reasoning, provide your final response.",
}


def get_system_message(key: str) -> str:
    """Retrieve a specific system message by its key."""
    return SYSTEM_MESSAGES.get(key, "")
