"""File: task_planner.py.

Provides task planning capabilities for the Code Ally agent.
Enables the agent to define, validate, and execute multi-step plans.
"""

import json
import logging
import time
from typing import Any

# Import only what we need at the module level
from code_ally.agent.error_handler import display_error
from code_ally.trust import PermissionDeniedError

# Forward references for type hints
ToolManager = Any  # Will be imported inside methods

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
    6. Interactive plan creation with user confirmation
    """

    def __init__(self, tool_manager: "ToolManager") -> None:
        """Initialize the task planner.

        Args:
            tool_manager: The tool manager instance for executing tools
        """
        self.tool_manager = tool_manager
        self.execution_history: list[dict[str, Any]] = []
        self.ui = None  # Will be set by the Agent class
        self.verbose = False

        # Interactive planning state
        self.interactive_plan: dict[str, Any] | None = None
        self.interactive_plan_tasks: list[dict[str, Any]] = []
        self.interactive_plan_finalized = False

    def set_verbose(self, verbose: bool) -> None:
        """Set verbose mode.

        Args:
            verbose: Whether to enable verbose logging
        """
        self.verbose = verbose

    def validate_plan(self, plan: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate a task plan for structural correctness.

        Args:
            plan: The task plan to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if "name" not in plan:
            return False, "Plan missing 'name' field"

        if "description" not in plan:
            return False, "Plan missing 'description' field"

        if "tasks" not in plan or not isinstance(plan["tasks"], list):
            return False, "Plan missing 'tasks' list or 'tasks' is not a list"

        if not plan["tasks"]:
            return False, "Plan contains no tasks"

        tasks_by_id = {}
        for i, task in enumerate(plan["tasks"]):
            if "id" not in task:
                return False, f"Task at index {i} missing 'id' field"

            if "tool_name" not in task:
                return False, f"Task at index {i} missing 'tool_name' field"

            if "arguments" in task and not isinstance(task["arguments"], dict):
                return (
                    False,
                    f"Task '{task['id']}' has invalid 'arguments' (must be a dictionary)",
                )

            tasks_by_id[task["id"]] = task

            if task["tool_name"] not in self.tool_manager.tools:
                return (
                    False,
                    f"Task '{task['id']}' references unknown tool '{task['tool_name']}'",
                )

        for task in plan["tasks"]:
            if "depends_on" in task:
                if not isinstance(task["depends_on"], list):
                    return (
                        False,
                        f"Task '{task['id']}' has invalid 'depends_on' (must be a list)",
                    )

                for dep_id in task["depends_on"]:
                    if dep_id not in tasks_by_id:
                        return (
                            False,
                            f"Task '{task['id']}' depends on unknown task '{dep_id}'",
                        )

        for task in plan["tasks"]:
            if "condition" in task:
                if not isinstance(task["condition"], dict):
                    return (
                        False,
                        f"Task '{task['id']}' has invalid 'condition' (must be a dictionary)",
                    )

                if "type" not in task["condition"]:
                    return False, f"Task '{task['id']}' condition missing 'type' field"

                if task["condition"]["type"] not in ["task_result", "expression"]:
                    return (
                        False,
                        f"Task '{task['id']}' has invalid condition type '{task['condition']['type']}'",
                    )

                if task["condition"]["type"] == "task_result":
                    if "task_id" not in task["condition"]:
                        return (
                            False,
                            f"Task '{task['id']}' condition missing 'task_id' field",
                        )

                    if task["condition"]["task_id"] not in tasks_by_id:
                        return (
                            False,
                            f"Task '{task['id']}' condition references unknown task '{task['condition']['task_id']}'",
                        )

        for task in plan["tasks"]:
            if "depends_on" in task:
                for dep_id in task["depends_on"]:
                    dep_task = tasks_by_id[dep_id]
                    if (
                        "depends_on" in dep_task
                        and task["id"] in dep_task["depends_on"]
                    ):
                        return (
                            False,
                            f"Circular dependency detected between tasks '{task['id']}' and '{dep_id}'",
                        )

        return True, None

    def validate_task(self, task: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate a single task for structural correctness.

        Args:
            task: The task to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if "tool_name" not in task:
            return False, "Task missing 'tool_name' field"

        if task["tool_name"] not in self.tool_manager.tools:
            return False, f"Task references unknown tool '{task['tool_name']}'"

        if "arguments" in task and not isinstance(task["arguments"], dict):
            return False, "Task has invalid 'arguments' (must be a dictionary)"

        return True, None

    def execute_plan(
        self,
        plan: dict[str, Any],
        client_type: str = None,
    ) -> dict[str, Any]:
        """Execute a complete task plan.

        Args:
            plan: The task plan to execute
            client_type: The client type to use for result formatting

        Returns:
            Dict containing execution results for the entire plan
        """
        self.execution_history = []

        if self.ui and plan is not self.interactive_plan:
            self._display_plan_summary(plan)

        is_valid, error = self.validate_plan(plan)
        if not is_valid:
            return {
                "success": False,
                "error": f"Invalid plan: {error}",
                "plan_name": plan.get("name", "unknown"),
                "results": {},
                "completed_tasks": [],
                "failed_tasks": [],
            }

        permission_operations = self._collect_permission_operations(plan)
        operations_pre_approved = False

        if permission_operations:
            operations_text = f"The task plan '{plan['name']}' requires permission for the following operations:\n"
            for i, (_tool_name, _path, description) in enumerate(
                permission_operations,
                1,
            ):
                operations_text += f"{i}. {description}\n"

            try:
                trust_operations = [
                    (tool_name, path) for tool_name, path, _ in permission_operations
                ]

                if self.tool_manager.trust_manager.prompt_for_parallel_operations(
                    trust_operations,
                    operations_text,
                ):
                    operations_pre_approved = True
                else:
                    return {
                        "success": False,
                        "error": "Permission denied for task plan operations",
                        "plan_name": plan.get("name", "unknown"),
                        "results": {},
                        "completed_tasks": [],
                        "failed_tasks": [],
                    }
            except PermissionDeniedError:
                return {
                    "success": False,
                    "error": "Permission denied for task plan operations",
                    "plan_name": plan.get("name", "unknown"),
                    "results": {},
                    "completed_tasks": [],
                    "failed_tasks": [],
                }

        start_time = time.time()

        try:
            if self.verbose and self.ui:
                self.ui.console.print(
                    f"[dim cyan][Verbose] Starting execution of plan: {plan['name']}[/]",
                )

            tasks_by_id = {task["id"]: task for task in plan["tasks"]}
            results = {}
            completed_tasks = []
            failed_tasks = []

            if self.ui:
                from rich.table import Table

                progress_table = Table(
                    title="Task Execution Plan",
                    box=None,
                    pad_edge=False,
                )
                progress_table.add_column("#", style="dim", width=3)
                progress_table.add_column("Status", width=8)
                progress_table.add_column("Task ID", style="cyan")
                progress_table.add_column("Description", style="yellow")

                for i, task in enumerate(plan["tasks"], 1):
                    task_id = task.get("id", f"task{i}")
                    description = task.get(
                        "description",
                        f"Execute {task.get('tool_name', 'unknown')}",
                    )
                    progress_table.add_row(
                        str(i),
                        "[dim]Pending[/]",
                        task_id,
                        description,
                    )

                self.ui.console.print(progress_table)
                self.ui.console.print("")

            for task in plan["tasks"]:
                task_id = task["id"]

                if "depends_on" in task:
                    dependencies_met = True
                    for dep_id in task["depends_on"]:
                        if dep_id not in completed_tasks or dep_id in failed_tasks:
                            dependencies_met = False
                            break

                    if not dependencies_met:
                        if self.verbose and self.ui:
                            self.ui.console.print(
                                f"[dim yellow][Verbose] Skipping task '{task_id}' due to unmet dependencies[/]",
                            )
                        failed_tasks.append(task_id)
                        results[task_id] = {
                            "success": False,
                            "error": "Dependencies not met",
                            "skipped": True,
                        }
                        continue

                if "condition" in task:
                    condition = task["condition"]
                    condition_met = self._evaluate_condition(condition, results)

                    if not condition_met:
                        if self.verbose and self.ui:
                            self.ui.console.print(
                                f"[dim yellow][Verbose] Skipping task '{task_id}' as condition not met[/]",
                            )
                        results[task_id] = {
                            "success": True,
                            "skipped": True,
                            "reason": "Condition not met",
                        }
                        completed_tasks.append(task_id)
                        continue

                if self.ui:
                    task_desc = task.get("description", f"Execute {task['tool_name']}")
                    self.ui.print_content(
                        f"[cyan]⏳ Task {len(completed_tasks) + 1}/{len(plan['tasks'])}: {task_desc}[/]",
                        style="cyan",
                    )

                if self.verbose and self.ui:
                    self.ui.console.print(
                        f"[dim cyan][Verbose] Executing task '{task_id}' with tool '{task['tool_name']}'[/]",
                    )

                tool_name = task["tool_name"]
                arguments = task.get("arguments", {})

                if "template_vars" in task:
                    arguments = self._process_template_vars(
                        arguments,
                        task["template_vars"],
                        results,
                    )

                if self.ui:
                    self.ui.print_tool_call(tool_name, arguments)

                batch_id = plan.get("batch_id", "default_batch")
                logger.info(
                    f"Executing task '{task_id}' with tool '{tool_name}' using batch_id: {batch_id}",
                )
                try:
                    raw_result = self.tool_manager.execute_tool(
                        tool_name,
                        arguments,
                        True,
                        client_type,
                        operations_pre_approved,
                    )
                except PermissionDeniedError:
                    failed_tasks.append(task_id)
                    results[task_id] = {
                        "success": False,
                        "error": "Permission denied",
                        "skipped": True,
                    }
                    continue

                results[task_id] = raw_result

                history_entry = {
                    "task_id": task_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "success": raw_result.get("success", False),
                    "timestamp": time.time(),
                }
                self.execution_history.append(history_entry)

                if raw_result.get("success", False):
                    completed_tasks.append(task_id)
                    if self.ui:
                        self.ui.print_content(
                            f"[green]✓ Task '{task_id}' completed successfully[/]",
                            style=None,
                        )
                else:
                    failed_tasks.append(task_id)
                    error_msg = raw_result.get("error", "Unknown error")

                    tool_name = task.get("tool_name", "unknown")
                    task_desc = task.get("description", f"Execute {tool_name}")

                    if self.ui:
                        self.ui.print_content(
                            f"[red]✗ Task '{task_id}' failed: {error_msg}[/]",
                        )

                        display_error(
                            self.ui,
                            error_msg,
                            tool_name,
                            arguments,
                            task_id,
                            task_desc,
                        )

                    if plan.get("stop_on_failure", False):
                        if self.ui:
                            self.ui.print_content(
                                "[yellow]⚠ Stopping plan execution due to task failure (stop_on_failure=True)[/]",
                            )
                        if self.verbose and self.ui:
                            self.ui.console.print(
                                f"[dim red][Verbose] Task '{task_id}' failed and stop_on_failure is set. Stopping plan execution.[/]",
                            )
                        break

            execution_time = time.time() - start_time

            if self.ui:
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
                    f"Completed {len(completed_tasks)}/{len(plan['tasks'])} tasks.[/]",
                )

                if recovery_needed and failed_tasks:
                    failed_tasks_info = []
                    for task_id in failed_tasks:
                        task = tasks_by_id.get(task_id)
                        if task:
                            task_tool = task.get("tool_name", "unknown")
                            task_desc = task.get("description", f"Execute {task_tool}")
                            error = results.get(task_id, {}).get(
                                "error",
                                "Unknown error",
                            )
                            failed_tasks_info.append(
                                f"- Task '{task_id}' ({task_desc}): {error}",
                            )

                    if failed_tasks_info:
                        failed_summary = "\n".join(failed_tasks_info)
                        self.ui.print_content(
                            f"[yellow bold]Error Summary:[/]\n{failed_summary}\n\n"
                            f"[blue bold]Next Steps:[/] The LLM should analyze these errors and attempt recovery "
                            f"by modifying the approach or creating a new plan.",
                        )

            if self.verbose and self.ui:
                self.ui.console.print(
                    f"[dim green][Verbose] Plan execution completed in {execution_time:.2f}s. "
                    f"Completed: {len(completed_tasks)}/{len(plan['tasks'])} tasks.[/]",
                )

            return {
                "success": len(failed_tasks) == 0,
                "error": (
                    ""
                    if len(failed_tasks) == 0
                    else f"Failed tasks: {', '.join(failed_tasks)}"
                ),
                "plan_name": plan["name"],
                "description": plan.get("description", ""),
                "results": results,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "execution_time": execution_time,
            }

        except Exception as e:
            logger.exception(f"Error executing plan: {e}")
            if self.verbose and self.ui:
                self.ui.console.print(
                    f"[dim red][Verbose] Error executing plan: {str(e)}[/]",
                )

            return {
                "success": False,
                "error": f"Error executing plan: {str(e)}",
                "plan_name": plan.get("name", "unknown"),
                "results": results if "results" in locals() else {},
                "completed_tasks": (
                    completed_tasks if "completed_tasks" in locals() else []
                ),
                "failed_tasks": failed_tasks if "failed_tasks" in locals() else [],
            }
        finally:
            if operations_pre_approved:
                self.tool_manager.trust_manager.clear_approved_operations()

    def start_interactive_plan(self, name: str, description: str) -> dict[str, Any]:
        """Start an interactive planning session.

        Args:
            name: The name of the plan
            description: The description of the plan

        Returns:
            Dict with the result of starting the plan
        """
        self.interactive_plan = {
            "name": name,
            "description": description,
            "stop_on_failure": True,
            "tasks": [],
        }
        self.interactive_plan_tasks = []
        self.interactive_plan_finalized = False

        if self.ui:
            self.ui.display_interactive_plan_started(name, description)

        return {
            "success": True,
            "plan_name": name,
            "message": f"Started creating plan: {name}",
            "task_count": 0,
        }

    def add_task_to_interactive_plan(self, task: dict[str, Any]) -> dict[str, Any]:
        """Add a task to the interactive plan.

        Args:
            task: The task to add

        Returns:
            Dict with the result of adding the task
        """
        if not self.interactive_plan:
            return {
                "success": False,
                "error": "No active plan. Start a plan first with mode='start_plan'.",
            }

        is_valid, error = self.validate_task(task)
        if not is_valid:
            return {"success": False, "error": f"Invalid task: {error}"}

        if "id" not in task:
            task["id"] = f"task{len(self.interactive_plan_tasks) + 1}"

        self.interactive_plan_tasks.append(task)

        if self.ui:
            task_index = len(self.interactive_plan_tasks)
            tool_name = task.get("tool_name", "???")
            depends_on = task.get("depends_on", [])
            condition_dict = task.get("condition", {})
            self.ui.display_interactive_plan_task_added(
                task_index,
                task["id"],
                tool_name,
                task.get("description", f"Execute {tool_name}"),
                depends_on,
                condition_dict,
            )

        return {
            "success": True,
            "task_id": task["id"],
            "task_index": len(self.interactive_plan_tasks),
            "message": f"Added task {task['id']} to plan",
        }

    def finalize_interactive_plan(self) -> dict[str, Any]:
        """Finalize the interactive plan, preparing it for execution.

        Returns:
            Dict with the result of finalizing the plan
        """
        if not self.interactive_plan:
            return {
                "success": False,
                "error": "No active plan. Start a plan first with mode='start_plan'.",
            }

        if not self.interactive_plan_tasks:
            return {
                "success": False,
                "error": "Plan has no tasks. Add tasks first with mode='add_task'.",
            }

        self.interactive_plan["tasks"] = self.interactive_plan_tasks
        is_valid, error = self.validate_plan(self.interactive_plan)
        if not is_valid:
            return {"success": False, "error": f"Invalid plan: {error}"}

        self.interactive_plan_finalized = True
        confirmed = (
            self.ui.confirm_interactive_plan(self.interactive_plan["name"])
            if self.ui
            else True
        )
        if not confirmed:
            self.interactive_plan = None
            self.interactive_plan_tasks = []
            self.interactive_plan_finalized = False
            return {
                "success": False,
                "error": "Plan rejected by user",
                "user_action": "rejected",
            }

        return {
            "success": True,
            "plan_name": self.interactive_plan["name"],
            "task_count": len(self.interactive_plan_tasks),
            "message": "Plan finalized and ready for execution",
            "user_action": "confirmed",
        }

    def execute_interactive_plan(self, client_type: str = None) -> dict[str, Any]:
        """Execute the finalized interactive plan.

        Args:
            client_type: The client type to use for result formatting

        Returns:
            Dict with execution results
        """
        if not self.interactive_plan or not self.interactive_plan_finalized:
            return {
                "success": False,
                "error": "No finalized plan. Finalize a plan first with mode='finalize_plan'.",
            }

        result = self.execute_plan(self.interactive_plan, client_type)

        self.interactive_plan = None
        self.interactive_plan_tasks = []
        self.interactive_plan_finalized = False

        return result

    def _evaluate_condition(
        self,
        condition: dict[str, Any],
        results: dict[str, Any],
    ) -> bool:
        """Evaluate a condition to determine if a task should be executed.

        Args:
            condition: The condition specification
            results: Results of previous task executions

        Returns:
            Whether the condition is met
        """
        condition_type = condition["type"]

        if condition_type == "task_result":
            task_id = condition["task_id"]
            if task_id not in results:
                return False

            task_result = results[task_id]
            field = condition.get("field", "success")
            expected_value = condition.get("value", True)

            actual_value = task_result.get(field)

            if condition.get("operator") == "not_equals":
                return actual_value != expected_value
            else:
                return actual_value == expected_value

        elif condition_type == "expression":
            return True

        return False

    def _process_template_vars(
        self,
        arguments: dict[str, Any],
        template_vars: dict[str, Any],
        results: dict[str, Any],
    ) -> dict[str, Any]:
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
                processed_value = value
                for var_name, var_def in template_vars.items():
                    placeholder = f"${{{var_name}}}"
                    if placeholder in processed_value:
                        if var_def.get("type") == "task_result":
                            task_id = var_def["task_id"]
                            if task_id in results:
                                result_value = results[task_id]

                                if "field" in var_def:
                                    field_path = var_def["field"].split(".")
                                    field_value = result_value

                                    for field in field_path:
                                        if (
                                            isinstance(field_value, dict)
                                            and field in field_value
                                        ):
                                            field_value = field_value[field]
                                        else:
                                            field_value = var_def.get("default", "")
                                            break

                                    replacement_value = str(field_value).replace(
                                        "\n",
                                        "",
                                    )
                                else:
                                    if isinstance(result_value, dict):
                                        replacement_value = json.dumps(result_value)
                                    else:
                                        replacement_value = str(result_value)

                                processed_value = processed_value.replace(
                                    placeholder,
                                    replacement_value,
                                )
                            else:
                                default_value = var_def.get("default", "")
                                processed_value = processed_value.replace(
                                    placeholder,
                                    str(default_value),
                                )
                        elif var_def.get("type") == "static":
                            static_value = var_def.get("value", "")
                            processed_value = processed_value.replace(
                                placeholder,
                                str(static_value),
                            )

                processed_args[key] = processed_value
            elif isinstance(value, dict):
                processed_args[key] = self._process_template_vars(
                    value,
                    template_vars,
                    results,
                )
            elif isinstance(value, list):
                processed_list = []
                for item in value:
                    if isinstance(item, str):
                        processed_item = item
                        for var_name, var_def in template_vars.items():
                            placeholder = f"${{{var_name}}}"
                            if placeholder in processed_item:
                                replacement = str(
                                    var_def.get("value", var_def.get("default", "")),
                                )
                                processed_item = processed_item.replace(
                                    placeholder,
                                    replacement,
                                )
                        processed_list.append(processed_item)
                    elif isinstance(item, dict):
                        processed_list.append(
                            self._process_template_vars(item, template_vars, results),
                        )
                    else:
                        processed_list.append(item)
                processed_args[key] = processed_list
            else:
                processed_args[key] = value

        return processed_args

    def _display_plan_summary(self, plan: dict[str, Any]) -> None:
        """Display a summary of the plan to the user.

        Args:
            plan: The task plan to display
        """
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

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

            dependencies = ""
            if "depends_on" in task:
                dependencies = ", ".join(task["depends_on"])

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
                conditional,
            )

        panel_content = []
        panel_content.append(Text("🔄 TASK PLAN: ", style="bold blue"))
        panel_content.append(Text(plan.get("name", "Unnamed Plan"), style="bold white"))
        panel_content.append(Text("\n\n"))

        panel_content.append(Text("Description: ", style="bold"))
        panel_content.append(Text(plan.get("description", "No description provided")))
        panel_content.append(Text("\n"))

        panel_content.append(Text("Number of Tasks: ", style="bold"))
        panel_content.append(Text(str(len(plan.get("tasks", [])))))
        panel_content.append(Text("\n"))

        panel_content.append(Text("Stop on Failure: ", style="bold"))
        panel_content.append(
            Text("Yes" if plan.get("stop_on_failure", False) else "No"),
        )

        panel_text = Text.assemble(*panel_content)

        panel = Panel(panel_text, border_style="blue", expand=False)

        if self.ui:
            self.ui.console.print("\n")
            self.ui.console.print(panel)
            self.ui.console.print(table)
            self.ui.console.print("\n")

            execution_msg = Text.assemble(
                Text("Starting execution", style="bold green"),
                Text("..."),
                Text(
                    " Task plan will be executed in sequence with dependencies.",
                    style="dim",
                ),
            )
            self.ui.console.print(execution_msg)

    def _collect_permission_operations(
        self,
        plan: dict[str, Any],
    ) -> list[tuple[str, Any, str]]:
        """Collect all operations in the plan that require permission.

        Args:
            plan: The task plan to analyze

        Returns:
            List of (tool_name, path, description) tuples for operations requiring permission
        """
        permission_operations = []

        tools_requiring_permission = {}
        for tool_name, tool in self.tool_manager.tools.items():
            if tool.requires_confirmation:
                tools_requiring_permission[tool_name] = tool

        for task in plan.get("tasks", []):
            tool_name = task.get("tool_name")

            if tool_name in tools_requiring_permission:
                arguments = task.get("arguments", {})

                if tool_name == "bash" and "command" in arguments:
                    permission_path = arguments
                    task_desc = task.get(
                        "description",
                        f"Execute command: {arguments.get('command')}",
                    )
                else:
                    permission_path = None
                    for arg_name, arg_value in arguments.items():
                        if isinstance(arg_value, str) and arg_name in (
                            "path",
                            "file_path",
                        ):
                            permission_path = arg_value
                            break

                    task_desc = task.get("description", f"Execute {tool_name}")

                permission_operations.append((tool_name, permission_path, task_desc))

        return permission_operations

    def get_plan_schema(self) -> dict[str, Any]:
        """Get the JSON schema for task plans.

        Returns:
            JSON schema as a dictionary
        """
        return {
            "type": "object",
            "required": ["name", "tasks"],
            "properties": {
                "name": {"type": "string", "description": "Name of the task plan"},
                "description": {
                    "type": "string",
                    "description": "Description of what the plan does",
                },
                "stop_on_failure": {
                    "type": "boolean",
                    "description": "Whether to stop execution if a task fails",
                    "default": False,
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
                                "description": "Unique identifier for the task",
                            },
                            "tool_name": {
                                "type": "string",
                                "description": "Name of the tool to execute",
                            },
                            "description": {
                                "type": "string",
                                "description": "Description of what the task does",
                            },
                            "arguments": {
                                "type": "object",
                                "description": "Arguments to pass to the tool",
                            },
                            "depends_on": {
                                "type": "array",
                                "description": "List of task IDs that must complete before this task",
                                "items": {"type": "string"},
                            },
                            "condition": {
                                "type": "object",
                                "description": "Condition that determines if this task should run",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["task_result", "expression"],
                                        "description": "Type of condition to evaluate",
                                    },
                                    "task_id": {
                                        "type": "string",
                                        "description": "ID of task whose result to check (for task_result type)",
                                    },
                                    "field": {
                                        "type": "string",
                                        "description": "Field in the task result to check (default: 'success')",
                                    },
                                    "operator": {
                                        "type": "string",
                                        "enum": ["equals", "not_equals"],
                                        "default": "equals",
                                        "description": "Comparison operator",
                                    },
                                    "value": {
                                        "description": "Value to compare against",
                                    },
                                },
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
                                            "description": "Source type for the variable",
                                        },
                                        "task_id": {
                                            "type": "string",
                                            "description": "ID of task whose result to use (for task_result type)",
                                        },
                                        "field": {
                                            "type": "string",
                                            "description": "Field path in the task result to use (dot notation)",
                                        },
                                        "value": {
                                            "description": "Static value (for static type)",
                                        },
                                        "default": {
                                            "description": "Default value to use if the source is unavailable",
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
