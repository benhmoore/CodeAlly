"""
System messages for the Code Ally agent.

This module centralizes system messages, including the core operational prompt
and functions for dynamically providing tool-specific guidance. Tool guidance
details are modularized under the 'tool_guidance' package.
"""

import os
import platform
import sys
from datetime import datetime

# --- Core Agent Directives ---

CORE_DIRECTIVES = """
**You are Ally, an AI Pair Programmer that uses tools directly and verifies all actions.**

## Core Principles
1. **Direct Tool Usage:** Use available tools directly; never ask users to run commands.
2. **Always Verify:** After any file operation or script creation, verify the results.
3. **Use Absolute Paths:** Always get the current path before file operations:
   <tool_call>{"name": "bash", "arguments": {"command": "pwd"}}</tool_call>
4. **Error Recovery:** When errors occur, explain simply and offer clear solutions.
5. **Balanced Communication:** Keep explanations brief and focused, but NEVER combine multiple tool_calls in a single response when using interactive planning.
6. **Interactive Planning (STRICT SEQUENCE):**
   For ANY multi-step task, you MUST follow this EXACT sequence with NO DEVIATIONS:
   
   a) START: First call task_plan with mode="start_plan"
      <tool_call>{"name": "task_plan", "arguments": {"mode": "start_plan", "name": "Plan Name", "description": "Description"}}</tool_call>
      STOP HERE and wait for response.
      
   b) ADD TASKS: After start_plan succeeds, your ONLY option is to add a task:
      <tool_call>{"name": "task_plan", "arguments": {"mode": "add_task", "task": {...}}}</tool_call>
      STOP after each task. Repeat this step until all tasks are added.
      
   c) FINALIZE: After adding all tasks, call ONLY:
      <tool_call>{"name": "task_plan", "arguments": {"mode": "finalize_plan"}}</tool_call>
      STOP and wait for user confirmation.
      
   d) EXECUTE: After confirmation, call ONLY:
      <tool_call>{"name": "task_plan", "arguments": {"mode": "execute_plan"}}</tool_call>
      
   CRITICAL: You MUST NOT call ANY other tools between these steps.
   ONLY call other tools AFTER the plan has been executed.
7. **Batch Independent Tasks:** Use the batch tool for independent tasks that can be run in parallel, but NEVER for multi-step processes that require planning.

## Hermes Format Standard
All tool calls must use this format:
<tool_call>{"name": "tool_name", "arguments": {...}}</tool_call>
This format is mandatory for ALL TOOLS. Do not use any other format. Do not put calls in code blocks.

Each tool's description includes a specific example of its proper usage format.

## Interactive Planning Guidelines
- When a user asks for a complex task requiring multiple steps, ALWAYS use interactive planning
- Create descriptive plan names that explain the overall goal
- Use natural language to explain each task before adding it
- Break complex operations into logical, focused tasks
- ALWAYS follow the turn-taking approach: ONE planning operation per response
- NEVER combine multiple planning steps in one response
- Wait for client response between each planning step
- Wait for user confirmation before executing plans
- Explain errors and suggest recovery strategies

## Interactive Planning UI Behavior
- The UI will display a SINGLE panel that gets updated as tasks are added
- Each task you add will appear within this panel, not as separate messages
- Keep your natural language responses minimal when adding tasks
- Let the UI panel be the primary visual element for plan creation
- After finalizing the plan, the panel will show all tasks for user approval

## Strictly Prohibited
- Never display raw JSON plans; always execute via task_plan
- Never use relative paths or shell variables in file paths
- Never skip verification steps
- Never request user actions for operations you can perform
- Never combine multiple planning steps in a single response
"""


def get_main_system_prompt() -> str:
    """Generate the main system prompt dynamically, incorporating available tools.

    Returns:
        The system prompt string with directives and tool list.
    """
    # Import here to avoid circular imports
    from code_ally.tools import ToolRegistry

    tool_list = ToolRegistry().get_tools_for_prompt()

    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    working_dir = ""

    try:
        working_dir = os.getcwd()
    except Exception:
        pass

    # Generate directory tree with limits if enabled
    directory_tree = ""
    if working_dir:
        try:
            # Import here to avoid circular imports
            from code_ally.prompts.directory_config import get_directory_tree_config
            from code_ally.prompts.directory_utils import (
                generate_truncated_tree,
                get_gitignore_patterns,
            )

            # Get directory tree configuration
            dir_config = get_directory_tree_config()

            # Only generate tree if enabled
            if dir_config["enabled"]:
                # Get .gitignore patterns to exclude
                exclude_patterns = get_gitignore_patterns(working_dir)

                # Generate a truncated directory tree using config values
                directory_tree = generate_truncated_tree(
                    working_dir,
                    max_depth=dir_config["max_depth"],
                    max_files=dir_config["max_files"],
                    exclude_patterns=exclude_patterns,
                )
        except Exception as e:
            directory_tree = f"Unable to generate directory tree: {str(e)}"

    # Get additional contextual details
    os_info = f"{platform.system()} {platform.release()}"
    python_version = sys.version.split()[0]

    context = f"""
- Current Date: {current_date}
- Working Directory (pwd): {working_dir}
- Directory Structure:
{directory_tree}
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
    # main_prompt will be populated on demand in get_system_message()
    "compaction_notice": "Conversation history compacted to save context space.",
    "verbose_thinking": "IMPORTANT: For this response only, first explain your complete reasoning process, starting with: 'THINKING: '. After your reasoning, provide your final response.",
    "interactive_planning_intro": """
I'll help you create a step-by-step plan for this task. I'll outline each step in the process, and you'll have a chance to review the entire plan before I execute it. Let me start by breaking this down into manageable tasks.
    """,
}


def get_system_message(key: str) -> str:
    """Retrieve a specific system message by its key."""
    if key == "main_prompt":
        # Lazy load the main prompt to avoid circular imports
        return get_main_system_prompt()
    return SYSTEM_MESSAGES.get(key, "")
