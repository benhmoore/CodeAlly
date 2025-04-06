"""File: task_planner.py

Provides task planning capabilities for the Code Ally agent.
Enables the agent to define, validate, and execute multi-step plans.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from code_ally.agent.tool_manager import ToolManager

logger = logging.getLogger(__name__)


class TaskPlanner:
    """Task planner for efficiently executing multi-step tool operations.
    
    The TaskPlanner helps the LLM agent organize complex sequences of tool operations
    into structured plans. It supports:
    
    1. Task definition with dependencies and conditions
    2. Validation of task plans
    3. Parallel or sequential execution
    4. Error handling and recovery
    5. Result tracking for each step
    """

    def __init__(self, tool_manager: ToolManager):
        """Initialize the task planner.
        
        Args:
            tool_manager: The tool manager instance for executing tools
        """
        self.tool_manager = tool_manager
        self.execution_history: List[Dict[str, Any]] = []
        self.ui = None  # Will be set by the Agent class
        self.verbose = False
    
    def set_verbose(self, verbose: bool) -> None:
        """Set verbose mode.
        
        Args:
            verbose: Whether to enable verbose logging
        """
        self.verbose = verbose
    
    def validate_plan(self, plan: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate a task plan for structural correctness.
        
        Args:
            plan: The task plan to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        if "name" not in plan:
            return False, "Plan missing 'name' field"
        
        if "description" not in plan:
            return False, "Plan missing 'description' field"
            
        if "tasks" not in plan or not isinstance(plan["tasks"], list):
            return False, "Plan missing 'tasks' list or 'tasks' is not a list"
            
        if not plan["tasks"]:
            return False, "Plan contains no tasks"
            
        # Check task structure
        tasks_by_id = {}
        for i, task in enumerate(plan["tasks"]):
            # Each task needs an id and tool_name
            if "id" not in task:
                return False, f"Task at index {i} missing 'id' field"
                
            if "tool_name" not in task:
                return False, f"Task at index {i} missing 'tool_name' field"
                
            # Arguments must be a dictionary if present
            if "arguments" in task and not isinstance(task["arguments"], dict):
                return False, f"Task '{task['id']}' has invalid 'arguments' (must be a dictionary)"
                
            # Store for dependency validation
            tasks_by_id[task["id"]] = task
                
            # Check that tool exists
            if task["tool_name"] not in self.tool_manager.tools:
                return False, f"Task '{task['id']}' references unknown tool '{task['tool_name']}'"
        
        # Validate dependencies
        for task in plan["tasks"]:
            if "depends_on" in task:
                if not isinstance(task["depends_on"], list):
                    return False, f"Task '{task['id']}' has invalid 'depends_on' (must be a list)"
                    
                for dep_id in task["depends_on"]:
                    if dep_id not in tasks_by_id:
                        return False, f"Task '{task['id']}' depends on unknown task '{dep_id}'"
                        
        # Validate conditional execution
        for task in plan["tasks"]:
            if "condition" in task:
                if not isinstance(task["condition"], dict):
                    return False, f"Task '{task['id']}' has invalid 'condition' (must be a dictionary)"
                    
                if "type" not in task["condition"]:
                    return False, f"Task '{task['id']}' condition missing 'type' field"
                    
                if task["condition"]["type"] not in ["task_result", "expression"]:
                    return False, f"Task '{task['id']}' has invalid condition type '{task['condition']['type']}'"
                    
                if task["condition"]["type"] == "task_result":
                    if "task_id" not in task["condition"]:
                        return False, f"Task '{task['id']}' condition missing 'task_id' field"
                        
                    if task["condition"]["task_id"] not in tasks_by_id:
                        return False, f"Task '{task['id']}' condition references unknown task '{task['condition']['task_id']}'"
                        
        # Check for dependency cycles (TODO: Implement more thorough cycle detection)
        for task in plan["tasks"]:
            if "depends_on" in task:
                for dep_id in task["depends_on"]:
                    dep_task = tasks_by_id[dep_id]
                    if "depends_on" in dep_task and task["id"] in dep_task["depends_on"]:
                        return False, f"Circular dependency detected between tasks '{task['id']}' and '{dep_id}'"
        
        return True, None
        
    def execute_plan(self, plan: Dict[str, Any], client_type: str = None) -> Dict[str, Any]:
        """Execute a complete task plan.
        
        Args:
            plan: The task plan to execute
            client_type: The client type to use for result formatting
            
        Returns:
            Dict containing execution results for the entire plan
        """
        # Reset execution history
        self.execution_history = []
        
        # Validate plan structure
        is_valid, error = self.validate_plan(plan)
        if not is_valid:
            return {
                "success": False,
                "error": f"Invalid plan: {error}",
                "plan_name": plan.get("name", "unknown"),
                "results": {},
                "completed_tasks": [],
                "failed_tasks": []
            }
            
        start_time = time.time()
        
        try:
            # Log plan execution start
            if self.verbose and self.ui:
                self.ui.console.print(
                    f"[dim cyan][Verbose] Starting execution of plan: {plan['name']}[/]"
                )
            
            # Create task lookup and execution mapping
            tasks_by_id = {task["id"]: task for task in plan["tasks"]}
            results = {}
            completed_tasks = []
            failed_tasks = []
            
            # Process tasks in order (we'll handle dependencies)
            for task in plan["tasks"]:
                task_id = task["id"]
                
                # Check dependencies
                if "depends_on" in task:
                    dependencies_met = True
                    for dep_id in task["depends_on"]:
                        if dep_id not in completed_tasks or dep_id in failed_tasks:
                            dependencies_met = False
                            break
                            
                    if not dependencies_met:
                        if self.verbose and self.ui:
                            self.ui.console.print(
                                f"[dim yellow][Verbose] Skipping task '{task_id}' due to unmet dependencies[/]"
                            )
                        failed_tasks.append(task_id)
                        results[task_id] = {
                            "success": False,
                            "error": "Dependencies not met",
                            "skipped": True
                        }
                        continue
                
                # Check conditions
                if "condition" in task:
                    condition = task["condition"]
                    condition_met = self._evaluate_condition(condition, results)
                    
                    if not condition_met:
                        if self.verbose and self.ui:
                            self.ui.console.print(
                                f"[dim yellow][Verbose] Skipping task '{task_id}' as condition not met[/]"
                            )
                        # This isn't a failure, just conditional skipping
                        results[task_id] = {
                            "success": True, 
                            "skipped": True,
                            "reason": "Condition not met"
                        }
                        completed_tasks.append(task_id)
                        continue
                
                # Execute the task
                if self.verbose and self.ui:
                    self.ui.console.print(
                        f"[dim cyan][Verbose] Executing task '{task_id}' with tool '{task['tool_name']}'[/]"
                    )
                    
                tool_name = task["tool_name"]
                arguments = task.get("arguments", {})
                
                # Process any template variables in arguments
                if "template_vars" in task:
                    arguments = self._process_template_vars(arguments, task["template_vars"], results)
                
                # Display that the call is happening
                if self.ui:
                    self.ui.print_tool_call(tool_name, arguments)
                
                # Execute the tool
                raw_result = self.tool_manager.execute_tool(
                    tool_name, arguments, True, client_type
                )
                
                # Store the result
                results[task_id] = raw_result
                
                # Record in execution history
                history_entry = {
                    "task_id": task_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "success": raw_result.get("success", False),
                    "timestamp": time.time()
                }
                self.execution_history.append(history_entry)
                
                # Update tracking
                if raw_result.get("success", False):
                    completed_tasks.append(task_id)
                else:
                    failed_tasks.append(task_id)
                    # Check if we should stop on failure
                    if plan.get("stop_on_failure", False):
                        if self.verbose and self.ui:
                            self.ui.console.print(
                                f"[dim red][Verbose] Task '{task_id}' failed and stop_on_failure is set. Stopping plan execution.[/]"
                            )
                        break
            
            execution_time = time.time() - start_time
            
            if self.verbose and self.ui:
                self.ui.console.print(
                    f"[dim green][Verbose] Plan execution completed in {execution_time:.2f}s. "
                    f"Completed: {len(completed_tasks)}/{len(plan['tasks'])} tasks.[/]"
                )
            
            # Generate plan summary
            return {
                "success": len(failed_tasks) == 0,
                "error": "" if len(failed_tasks) == 0 else f"Failed tasks: {', '.join(failed_tasks)}",
                "plan_name": plan["name"],
                "description": plan.get("description", ""),
                "results": results,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "execution_time": execution_time
            }
            
        except Exception as e:
            logger.exception(f"Error executing plan: {e}")
            if self.verbose and self.ui:
                self.ui.console.print(
                    f"[dim red][Verbose] Error executing plan: {str(e)}[/]"
                )
            
            return {
                "success": False,
                "error": f"Error executing plan: {str(e)}",
                "plan_name": plan.get("name", "unknown"),
                "results": results if 'results' in locals() else {},
                "completed_tasks": completed_tasks if 'completed_tasks' in locals() else [],
                "failed_tasks": failed_tasks if 'failed_tasks' in locals() else []
            }
    
    def _evaluate_condition(self, condition: Dict[str, Any], results: Dict[str, Any]) -> bool:
        """Evaluate a condition to determine if a task should be executed.
        
        Args:
            condition: The condition specification
            results: Results of previous task executions
            
        Returns:
            Whether the condition is met
        """
        condition_type = condition["type"]
        
        if condition_type == "task_result":
            # Check a previous task's success status
            task_id = condition["task_id"]
            if task_id not in results:
                return False
                
            task_result = results[task_id]
            field = condition.get("field", "success")
            expected_value = condition.get("value", True)
            
            # Get the actual value from the task result
            actual_value = task_result.get(field)
            
            # Check if the condition is met
            if condition.get("operator") == "not_equals":
                return actual_value != expected_value
            else:  # Default to equals
                return actual_value == expected_value
                
        elif condition_type == "expression":
            # TODO: Implement expression evaluation if needed
            # This would allow for more complex conditions
            return True
            
        return False
        
    def _process_template_vars(
        self, 
        arguments: Dict[str, Any], 
        template_vars: Dict[str, Any],
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process template variables in task arguments.
        
        Args:
            arguments: The original arguments dictionary
            template_vars: Template variable definitions
            results: Results from previous task executions
            
        Returns:
            Updated arguments with template variables processed
        """
        processed_args = {}
        
        for key, value in arguments.items():
            if isinstance(value, str):
                # Process string templates
                processed_value = value
                for var_name, var_def in template_vars.items():
                    placeholder = f"${{{var_name}}}"
                    if placeholder in processed_value:
                        if var_def.get("type") == "task_result":
                            # Get value from a previous task result
                            task_id = var_def["task_id"]
                            if task_id in results:
                                result_value = results[task_id]
                                
                                # Extract specific field if provided
                                if "field" in var_def:
                                    field_path = var_def["field"].split(".")
                                    field_value = result_value
                                    
                                    # Navigate nested fields
                                    for field in field_path:
                                        if isinstance(field_value, dict) and field in field_value:
                                            field_value = field_value[field]
                                        else:
                                            field_value = var_def.get("default", "")
                                            break
                                    
                                    replacement_value = str(field_value)
                                else:
                                    # Use the whole result (as JSON if it's a dict)
                                    if isinstance(result_value, dict):
                                        replacement_value = json.dumps(result_value)
                                    else:
                                        replacement_value = str(result_value)
                                
                                processed_value = processed_value.replace(placeholder, replacement_value)
                            else:
                                # Use default if provided
                                default_value = var_def.get("default", "")
                                processed_value = processed_value.replace(placeholder, str(default_value))
                        elif var_def.get("type") == "static":
                            # Use static value
                            static_value = var_def.get("value", "")
                            processed_value = processed_value.replace(placeholder, str(static_value))
                
                processed_args[key] = processed_value
            elif isinstance(value, dict):
                # Recursively process nested dictionaries
                processed_args[key] = self._process_template_vars(value, template_vars, results)
            elif isinstance(value, list):
                # Process list items if they're strings or dicts
                processed_list = []
                for item in value:
                    if isinstance(item, str):
                        processed_item = item
                        for var_name, var_def in template_vars.items():
                            placeholder = f"${{{var_name}}}"
                            if placeholder in processed_item:
                                # Same logic as above, but simplified for brevity
                                replacement = str(var_def.get("value", var_def.get("default", "")))
                                processed_item = processed_item.replace(placeholder, replacement)
                        processed_list.append(processed_item)
                    elif isinstance(item, dict):
                        processed_list.append(self._process_template_vars(item, template_vars, results))
                    else:
                        processed_list.append(item)
                processed_args[key] = processed_list
            else:
                # Pass through other value types unchanged
                processed_args[key] = value
                
        return processed_args
        
    def get_plan_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for task plans.
        
        Returns:
            JSON schema as a dictionary
        """
        return {
            "type": "object",
            "required": ["name", "tasks"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the task plan"
                },
                "description": {
                    "type": "string",
                    "description": "Description of what the plan does"
                },
                "stop_on_failure": {
                    "type": "boolean",
                    "description": "Whether to stop execution if a task fails",
                    "default": False
                },
                "tasks": {
                    "type": "array",
                    "description": "List of tasks to execute",
                    "items": {
                        "type": "object",
                        "required": ["id", "tool_name"],
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Unique identifier for the task"
                            },
                            "tool_name": {
                                "type": "string",
                                "description": "Name of the tool to execute"
                            },
                            "description": {
                                "type": "string", 
                                "description": "Description of what the task does"
                            },
                            "arguments": {
                                "type": "object",
                                "description": "Arguments to pass to the tool"
                            },
                            "depends_on": {
                                "type": "array",
                                "description": "List of task IDs that must complete before this task",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "condition": {
                                "type": "object",
                                "description": "Condition that determines if this task should run",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["task_result", "expression"],
                                        "description": "Type of condition to evaluate"
                                    },
                                    "task_id": {
                                        "type": "string",
                                        "description": "ID of task whose result to check (for task_result type)"
                                    },
                                    "field": {
                                        "type": "string",
                                        "description": "Field in the task result to check (default: 'success')"
                                    },
                                    "operator": {
                                        "type": "string",
                                        "enum": ["equals", "not_equals"],
                                        "default": "equals",
                                        "description": "Comparison operator"
                                    },
                                    "value": {
                                        "description": "Value to compare against"
                                    }
                                }
                            },
                            "template_vars": {
                                "type": "object",
                                "description": "Template variables for argument substitution",
                                "additionalProperties": {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "enum": ["task_result", "static"],
                                            "description": "Source type for the variable"
                                        },
                                        "task_id": {
                                            "type": "string",
                                            "description": "ID of task whose result to use (for task_result type)"
                                        },
                                        "field": {
                                            "type": "string",
                                            "description": "Field path in the task result to use (dot notation)"
                                        },
                                        "value": {
                                            "description": "Static value (for static type)"
                                        },
                                        "default": {
                                            "description": "Default value to use if the source is unavailable"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }