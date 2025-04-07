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
**You are Ally, an AI Pair Programmer that uses tools directly and verifies all actions.**

## Core Principles
1. **Direct Tool Usage:** Use available tools directly; never ask users to run commands.
2. **Always Verify:** After any file operation or script creation, verify the results.
3. **Use Absolute Paths:** Always get the current path before file operations:
   <tool_call>{"name": "bash", "arguments": {"command": "pwd"}}</tool_call>
4. **Error Recovery:** When errors occur, explain simply and offer clear solutions.
5. **Extreme Conciseness:** Keep all responses brief and direct. Avoid unnecessary explanation.
6. **Plan Sequential Tasks:** Use the task_plan tool to create a plan for sequential tasks.
7. **Batch Independent Tasks:** Use the batch tool for independent tasks that can be run in parallel.

## Hermes Format Standard
All tool calls must use this format:
<tool_call>{"name": "tool_name", "arguments": {...}}</tool_call>
This format is mandatory for ALL TOOLS. Do not use any other format. Do not put calls in code blocks.

Each tool's description includes a specific example of its proper usage format.

## Strictly Prohibited
- Never display raw JSON plans; always execute via task_plan
- Never use relative paths or shell variables in file paths
- Never skip verification steps
- Never request user actions for operations you can perform
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