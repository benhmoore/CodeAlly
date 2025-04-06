"""File: task_planner.py

Provides task planning capabilities for the Code Ally agent.
Enables the agent to define, validate, and execute multi-step plans.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from code_ally.agent.tool_manager import ToolManager
from code_ally.agent.error_handler import display_error
from code_ally.tools.base import BaseTool

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
            
        # Display plan summary to the user (informational only, no confirmation)
        if self.ui:
            self._display_plan_summary(plan)
        
        # Pre-check all permissions needed for the plan
        batch_id = f"task-plan-{int(time.time())}"
        permission_operations = self._collect_permission_operations(plan)
        if permission_operations and not self._request_plan_permissions(permission_operations, plan["name"], batch_id):
            return {
                "success": False,
                "error": "Permission denied for task plan operations",
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
            
            # Display task execution progress overview
            if self.ui:
                from rich.table import Table
                
                # Create a progress overview
                progress_table = Table(title="Task Execution Plan", box=None, pad_edge=False)
                progress_table.add_column("#", style="dim", width=3)
                progress_table.add_column("Status", width=8)
                progress_table.add_column("Task ID", style="cyan")
                progress_table.add_column("Description", style="yellow")
                
                for i, task in enumerate(plan["tasks"], 1):
                    task_id = task.get("id", f"task{i}")
                    description = task.get("description", f"Execute {task.get('tool_name', 'unknown')}")
                    progress_table.add_row(
                        str(i),
                        "[dim]Pending[/]",
                        task_id,
                        description
                    )
                
                self.ui.console.print(progress_table)
                self.ui.console.print("")  # Add a blank line
            
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
                if self.ui:
                    # Show task execution status
                    task_desc = task.get("description", f"Execute {task['tool_name']}")
                    self.ui.print_content(
                        f"[cyan]⏳ Task {len(completed_tasks) + 1}/{len(plan['tasks'])}: {task_desc}[/]",
                        style="cyan"
                    )
                
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
                
                # Execute the tool - pass the batch_id for permission tracking
                # Log to help debug the permission issue
                logger.info(f"Executing task '{task_id}' with tool '{tool_name}' using batch_id: {batch_id}")
                raw_result = self.tool_manager.execute_tool(
                    tool_name, arguments, True, client_type, batch_id
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
                
                # Update tracking and show result status
                if raw_result.get("success", False):
                    completed_tasks.append(task_id)
                    if self.ui:
                        self.ui.print_content(
                            f"[green]✓ Task '{task_id}' completed successfully[/]",
                            style=None
                        )
                else:
                    failed_tasks.append(task_id)
                    error_msg = raw_result.get("error", "Unknown error")
                    
                    # Get task details for error context
                    tool_name = task.get("tool_name", "unknown")
                    task_desc = task.get("description", f"Execute {tool_name}")
                    
                    if self.ui:
                        # Print the error status
                        self.ui.print_content(
                            f"[red]✗ Task '{task_id}' failed: {error_msg}[/]"
                        )
                        
                        # Display formatted error with suggestions
                        display_error(
                            self.ui, 
                            error_msg, 
                            tool_name, 
                            arguments, 
                            task_id, 
                            task_desc
                        )
                    
                    # Check if we should stop on failure
                    if plan.get("stop_on_failure", False):
                        if self.ui:
                            self.ui.print_content(
                                f"[yellow]⚠ Stopping plan execution due to task failure (stop_on_failure=True)[/]"
                            )
                        if self.verbose and self.ui:
                            self.ui.console.print(
                                f"[dim red][Verbose] Task '{task_id}' failed and stop_on_failure is set. Stopping plan execution.[/]"
                            )
                        break
            
            execution_time = time.time() - start_time
            
            # Display final summary
            if self.ui:
                # Create a summary message
                if len(failed_tasks) == 0:
                    color = "green"
                    icon = "✓"
                    status = "Successfully"
                    recovery_needed = False
                elif len(completed_tasks) > 0:
                    color = "yellow"
                    icon = "⚠"
                    status = "Partially"
                    recovery_needed = True
                else:
                    color = "red"
                    icon = "✗"
                    status = "Failed to"
                    recovery_needed = True
                
                self.ui.print_content(
                    f"[{color}]{icon} {status} completed plan '{plan['name']}' in {execution_time:.2f}s. "
                    f"Completed {len(completed_tasks)}/{len(plan['tasks'])} tasks.[/]"
                )
                
                # Add guidance for error recovery if needed
                if recovery_needed and failed_tasks:
                    failed_tasks_info = []
                    for task_id in failed_tasks:
                        task = tasks_by_id.get(task_id)
                        if task:
                            task_tool = task.get("tool_name", "unknown")
                            task_desc = task.get("description", f"Execute {task_tool}")
                            error = results.get(task_id, {}).get("error", "Unknown error")
                            failed_tasks_info.append(f"- Task '{task_id}' ({task_desc}): {error}")
                    
                    if failed_tasks_info:
                        # Create error summary without rich formatting in text
                        failed_summary = "\n".join(failed_tasks_info)
                        self.ui.print_content(
                            f"[yellow bold]Error Summary:[/]\n{failed_summary}\n\n"
                            f"[blue bold]Next Steps:[/] The LLM should analyze these errors and attempt recovery "
                            f"by modifying the approach or creating a new plan."
                        )
            
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
                                    
                                    # Clean up the value - replace newlines with empty string to handle paths properly
                                    replacement_value = str(field_value).replace("\n", "")
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
        
    def _display_plan_summary(self, plan: Dict[str, Any]) -> None:
        """Display a summary of the plan to the user.
        
        Args:
            plan: The task plan to display
        """
        from rich.table import Table
        from rich.panel import Panel
        from rich.console import Console
        from rich.text import Text
        import time
        
        # Create a formatted table of tasks
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="dim")
        table.add_column("Task ID", style="cyan")
        table.add_column("Tool", style="green")
        table.add_column("Description", style="yellow")
        table.add_column("Dependencies", style="blue")
        table.add_column("Conditional", style="magenta")
        
        for i, task in enumerate(plan.get("tasks", []), 1):
            task_id = task.get("id", f"task{i}")
            tool_name = task.get("tool_name", "unknown")
            description = task.get("description", f"Execute {tool_name}")
            
            # Format dependencies if present
            dependencies = ""
            if "depends_on" in task:
                dependencies = ", ".join(task["depends_on"])
            
            # Check if this task has conditions
            conditional = "No"
            if "condition" in task:
                condition = task["condition"]
                if condition.get("type") == "task_result":
                    task_id_ref = condition.get("task_id", "")
                    field = condition.get("field", "success")
                    operator = condition.get("operator", "equals")
                    value = condition.get("value", True)
                    conditional = f"Yes ({task_id_ref}.{field} {operator} {value})"
                else:
                    conditional = "Yes (custom)"
            
            table.add_row(
                str(i),
                task_id,
                tool_name,
                description,
                dependencies,
                conditional
            )
        
        # Create a summary panel content
        panel_content = []
        panel_content.append(Text("🔄 TASK PLAN: ", style="bold blue"))
        panel_content.append(Text(plan.get('name', 'Unnamed Plan'), style="bold white"))
        panel_content.append(Text("\n\n"))
        
        panel_content.append(Text("Description: ", style="bold"))
        panel_content.append(Text(plan.get("description", "No description provided")))
        panel_content.append(Text("\n"))
        
        panel_content.append(Text("Number of Tasks: ", style="bold"))
        panel_content.append(Text(str(len(plan.get("tasks", [])))))
        panel_content.append(Text("\n"))
        
        panel_content.append(Text("Stop on Failure: ", style="bold"))
        panel_content.append(Text("Yes" if plan.get("stop_on_failure", False) else "No"))
        
        # Combine all text segments
        panel_text = Text.assemble(*panel_content)
        
        # Create the panel
        panel = Panel(panel_text, border_style="blue", expand=False)
        
        # Display the plan to the user
        if self.ui:
            self.ui.console.print("\n")
            self.ui.console.print(panel)
            self.ui.console.print(table)
            self.ui.console.print("\n")
            
            # Display execution message
            execution_msg = Text.assemble(
                Text("Starting execution", style="bold green"),
                Text("..."), 
                Text(" Task plan will be executed in sequence with dependencies.", style="dim")
            )
            self.ui.console.print(execution_msg)
    
    def _collect_permission_operations(self, plan: Dict[str, Any]) -> List[Tuple[str, Any, str]]:
        """Collect all operations in the plan that require permission.
        
        Args:
            plan: The task plan to analyze
            
        Returns:
            List of (tool_name, path, description) tuples for operations requiring permission
        """
        permission_operations = []
        
        # Find all tools that require confirmation
        tools_requiring_permission = {}
        for tool_name, tool in self.tool_manager.tools.items():
            if tool.requires_confirmation:
                tools_requiring_permission[tool_name] = tool
        
        # Process all tasks in the plan
        for task in plan.get("tasks", []):
            tool_name = task.get("tool_name")
            
            if tool_name in tools_requiring_permission:
                arguments = task.get("arguments", {})
                
                # For bash tool, pass arguments.command as the path
                if tool_name == "bash" and "command" in arguments:
                    permission_path = arguments
                    task_desc = task.get("description", f"Execute command: {arguments.get('command')}")
                else:
                    # Use the first string argument as the path, if any
                    permission_path = None
                    for arg_name, arg_value in arguments.items():
                        if isinstance(arg_value, str) and arg_name in ("path", "file_path"):
                            permission_path = arg_value
                            break
                    
                    task_desc = task.get("description", f"Execute {tool_name}")
                
                # Add to the list with a detailed description
                permission_operations.append((tool_name, permission_path, task_desc))
        
        return permission_operations
    
    def _request_plan_permissions(self, operations: List[Tuple[str, Any, str]], plan_name: str, batch_id: str) -> bool:
        """Request permission for all operations in a plan at once.
        
        Args:
            operations: List of (tool_name, path, description) tuples requiring permission
            plan_name: Name of the task plan
            batch_id: Unique ID for this batch of operations
            
        Returns:
            Whether all permissions were granted
        """
        if not operations:
            return True
            
        if not self.tool_manager.trust_manager:
            logger.warning("Trust manager not initialized, can't request permissions")
            return False
            
        # Format the permission text
        operations_text = f"The task plan '{plan_name}' requires permission for the following operations:\n"
        for i, (tool_name, path, description) in enumerate(operations, 1):
            operations_text += f"{i}. {description}\n"
        
        # Strip out the description for the actual trust manager call
        trust_operations = [(tool_name, path) for tool_name, path, _ in operations]
            
        # Use the trust manager to request all permissions at once
        return self.tool_manager.trust_manager.prompt_for_parallel_operations(
            trust_operations, operations_text, batch_id
        )
    
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