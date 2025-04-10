"""File: plan.py.

Task planning tool for the Code Ally agent.
Allows the agent to execute complex multi-step operations.
"""

import json
import logging
from typing import Any

from code_ally.agent.task_planner import TaskPlanner
from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool

logger = logging.getLogger(__name__)


@register_tool
class TaskPlanTool(BaseTool):
    """Tool for executing multi-step task plans."""

    name = "task_plan"
    description = """Execute a multi-step task plan with dependencies and conditions.

    This tool supports both direct execution and interactive planning:

    1. Direct execution (complete plan):
    <tool_call>{"name": "task_plan", "arguments": {"plan": {
      "name": "Task Name",
      "description": "Task description",
      "stop_on_failure": true,
      "tasks": [...]
    }}}</tool_call>

    2. Interactive planning (step by step):
    a) Start a new plan:
    <tool_call>{"name": "task_plan", "arguments": {"mode": "start_plan", "name": "Plan Name", "description": "Plan description"}}</tool_call>
    
    b) Add a task to the current plan:
    <tool_call>{"name": "task_plan", "arguments": {"mode": "add_task", "task": {"tool_name": "bash", "description": "Run command", "arguments": {"command": "echo hello"}}}}</tool_call>
    
    c) Finalize the plan (prepare for execution):
    <tool_call>{"name": "task_plan", "arguments": {"mode": "finalize_plan"}}</tool_call>
    
    d) Execute the finalized plan:
    <tool_call>{"name": "task_plan", "arguments": {"mode": "execute_plan"}}</tool_call>

    ## Example Planning Conversation Flow
    USER: "Create a Spider-Man fan site"

    ASSISTANT: [FIRST TURN - ONLY starts the plan]
    <tool_call>{"name": "task_plan", "arguments": {"mode": "start_plan", "name": "Create Spider-Man Fan Site", "description": "Create a simple Spider-Man themed website"}}</tool_call>

    TOOL RESPONSE: [Plan started successfully]

    ASSISTANT: [SECOND TURN - ONLY adds first task]
    <tool_call>{"name": "task_plan", "arguments": {"mode": "add_task", "task": {"tool_name": "directory", "description": "Create project structure", "arguments": {"operation": "create", "path": "/path/to/site", "structure": {"css": {}, "images": {}}}}}}</tool_call>

    TOOL RESPONSE: [Task added successfully]

    ASSISTANT: [THIRD TURN - ONLY adds second task]
    <tool_call>{"name": "task_plan", "arguments": {"mode": "add_task", "task": {"tool_name": "file_write", "description": "Create index.html", "arguments": {"path": "/path/to/site/index.html", "content": "<!DOCTYPE html>..."}}}}</tool_call>

    [CONTINUE ADDING TASKS ONE BY ONE]

    ASSISTANT: [AFTER ALL TASKS - ONLY finalizes plan]
    <tool_call>{"name": "task_plan", "arguments": {"mode": "finalize_plan"}}</tool_call>

    TOOL RESPONSE: [Plan finalized, user confirmed]

    ASSISTANT: [FINAL TURN - ONLY executes plan]
    <tool_call>{"name": "task_plan", "arguments": {"mode": "execute_plan"}}</tool_call>

    Supports:
    - Sequential and conditional execution of multiple tools
    - Dependencies between tasks
    - Variable substitution between tasks
    - Error handling and recovery
    - Consolidated permission prompts for all operations
    """
    requires_confirmation = False

    def __init__(self) -> None:
        """Initialize the task plan tool."""
        super().__init__()
        self.task_planner: TaskPlanner | None = None

    def set_task_planner(self, task_planner: TaskPlanner) -> None:
        """Set the task planner instance for this tool.

        Args:
            task_planner: The task planner to use
        """
        self.task_planner = task_planner

    def execute(
        self,
        plan: dict[str, Any] = None,
        plan_json: str = "",
        validate_only: bool = False,
        client_type: str = None,
        mode: str = None,
        name: str = "",
        description: str = "",
        task: dict[str, Any] = None,
        **kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a task plan or perform an interactive planning operation.

        Args:
            plan: The complete task plan definition as a dictionary
            plan_json: The task plan definition as a JSON string (alternative to plan)
            validate_only: Whether to only validate the plan without executing it
            client_type: The client type to use for formatting results
            mode: The operation mode ("start_plan", "add_task", "finalize_plan", "execute_plan")
            name: The name of the plan (for start_plan mode)
            description: The description of the plan (for start_plan mode)
            task: A task to add to the plan (for add_task mode)
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with operation results
        """
        if not self.task_planner:
            return self._format_error_response(
                "Task planner not initialized. This is an internal error.",
            )

        # Handle interactive planning operations
        if mode:
            return self._handle_interactive_planning(
                mode,
                name,
                description,
                task,
                client_type,
            )

        # Otherwise, handle direct plan execution (traditional mode)
        # Parse plan from JSON string if provided
        if not plan and plan_json:
            try:
                plan = json.loads(plan_json)
            except json.JSONDecodeError as e:
                return self._format_error_response(f"Invalid plan JSON: {str(e)}")

        # Validate plan existence
        if not plan:
            return self._format_error_response(
                "No plan provided. Either 'plan' or 'plan_json' must be specified.",
            )

        # Validate plan structure
        is_valid, error = self.task_planner.validate_plan(plan)
        if not is_valid:
            return self._format_error_response(f"Invalid plan: {error}")

        # If validate_only is True, just return validation success
        if validate_only:
            return self._format_success_response(
                plan_name=plan.get("name", ""),
                description=plan.get("description", ""),
                task_count=len(plan.get("tasks", [])),
                message="Plan validation successful",
            )

        # Execute the plan
        result = self.task_planner.execute_plan(plan, client_type)

        # Return all details
        if result.get("success", False):
            return self._format_success_response(**result)
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "plan_name": result.get("plan_name", ""),
                "results": result.get("results", {}),
                "completed_tasks": result.get("completed_tasks", []),
                "failed_tasks": result.get("failed_tasks", []),
                "execution_time": result.get("execution_time", 0),
            }

    def _handle_interactive_planning(
        self,
        mode: str,
        name: str = "",
        description: str = "",
        task: dict[str, Any] = None,
        client_type: str = None,
    ) -> dict[str, Any]:
        """Handle interactive planning modes.

        Args:
            mode: The operation mode
            name: The name of the plan (for start_plan mode)
            description: The description of the plan (for start_plan mode)
            task: A task to add to the plan (for add_task mode)
            client_type: The client type to use for formatting results

        Returns:
            Dict with operation results
        """
        if mode == "start_plan":
            return self.task_planner.start_interactive_plan(name, description)
        elif mode == "add_task":
            if not task:
                return self._format_error_response("No task provided for add_task mode")
            return self.task_planner.add_task_to_interactive_plan(task)
        elif mode == "finalize_plan":
            return self.task_planner.finalize_interactive_plan()
        elif mode == "execute_plan":
            return self.task_planner.execute_interactive_plan(client_type)
        else:
            return self._format_error_response(f"Unknown planning mode: {mode}")

    def get_schema(self) -> dict[str, Any]:
        """Get the schema for task plans.

        Returns:
            The task plan schema as a dictionary
        """
        if not self.task_planner:
            return {"error": "Task planner not initialized"}

        return self.task_planner.get_plan_schema()
