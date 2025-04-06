"""File: plan.py

Task planning tool for the Code Ally agent.
Allows the agent to execute complex multi-step operations.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from code_ally.agent.task_planner import TaskPlanner
from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool

logger = logging.getLogger(__name__)


@register_tool
class TaskPlanTool(BaseTool):
    """Tool for executing multi-step task plans."""

    name = "task_plan"
    description = """Execute a multi-step task plan with dependencies and conditions.
    
    Supports:
    - Sequential and conditional execution of multiple tools
    - Dependencies between tasks
    - Variable substitution between tasks
    - Error handling and recovery
    - Parallel-friendly execution
    """
    requires_confirmation = False

    def __init__(self):
        """Initialize the task plan tool."""
        super().__init__()
        self.task_planner: Optional[TaskPlanner] = None
    
    def set_task_planner(self, task_planner: TaskPlanner) -> None:
        """Set the task planner instance for this tool.
        
        Args:
            task_planner: The task planner to use
        """
        self.task_planner = task_planner
    
    def execute(
        self,
        plan: Dict[str, Any] = None,
        plan_json: str = "",
        validate_only: bool = False,
        client_type: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute a multi-step task plan.
        
        Args:
            plan: The task plan definition as a dictionary
            plan_json: The task plan definition as a JSON string (alternative to plan)
            validate_only: Whether to only validate the plan without executing it
            client_type: The client type to use for formatting results
            **kwargs: Additional arguments (unused)
            
        Returns:
            Dict with keys:
                success: Whether the plan execution was successful
                error: Error message if any
                plan_name: Name of the executed plan
                results: Results of individual tasks
                completed_tasks: List of completed task IDs
                failed_tasks: List of failed task IDs
                execution_time: Time taken to execute the plan (in seconds)
        """
        if not self.task_planner:
            return self._format_error_response(
                "Task planner not initialized. This is an internal error."
            )
        
        # Parse plan from JSON string if provided
        if not plan and plan_json:
            try:
                plan = json.loads(plan_json)
            except json.JSONDecodeError as e:
                return self._format_error_response(
                    f"Invalid plan JSON: {str(e)}"
                )
                
        # Validate plan existence
        if not plan:
            return self._format_error_response(
                "No plan provided. Either 'plan' or 'plan_json' must be specified."
            )
            
        # Validate plan structure
        is_valid, error = self.task_planner.validate_plan(plan)
        if not is_valid:
            return self._format_error_response(
                f"Invalid plan: {error}"
            )
            
        # If validate_only is True, just return validation success
        if validate_only:
            return self._format_success_response(
                plan_name=plan.get("name", ""),
                description=plan.get("description", ""),
                task_count=len(plan.get("tasks", [])),
                message="Plan validation successful"
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
                "execution_time": result.get("execution_time", 0)
            }
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the schema for task plans.
        
        Returns:
            The task plan schema as a dictionary
        """
        if not self.task_planner:
            return {"error": "Task planner not initialized"}
            
        return self.task_planner.get_plan_schema()