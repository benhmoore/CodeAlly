# Task Planning Tutorial

This tutorial demonstrates how to use the task planning system in Code Ally to orchestrate complex multi-step operations.

## Overview

The task planning system allows you to:

1. Define a sequence of tool operations as a structured plan
2. Establish dependencies between tasks
3. Set conditions for task execution
4. Pass results from earlier tasks to later ones
5. Handle errors and control execution flow

## Basic Plan Structure

A task plan is defined as a JSON object with the following structure:

```json
{
  "name": "My Plan Name",
  "description": "What this plan does",
  "stop_on_failure": true,
  "tasks": [
    {
      "id": "task1",
      "tool_name": "tool_to_execute",
      "description": "What this task does",
      "arguments": {
        "arg1": "value1",
        "arg2": "value2"
      }
    },
    {
      "id": "task2",
      "tool_name": "another_tool",
      "arguments": {
        "arg1": "value1"
      },
      "depends_on": ["task1"]
    }
  ]
}
```

## Task Dependencies

Dependencies ensure that tasks run in the correct order:

```json
{
  "id": "process_file",
  "tool_name": "file_edit",
  "depends_on": ["find_file", "backup_file"],
  "arguments": { "path": "example.py", "old_text": "TODO", "new_text": "DONE" }
}
```

In this example, `process_file` will only run after both `find_file` and `backup_file` have successfully completed.

## Conditional Execution

Conditions determine whether a task should run based on the results of previous tasks:

```json
{
  "id": "commit_changes",
  "tool_name": "bash",
  "arguments": { "command": "git commit -m 'Fix TODOs'" },
  "depends_on": ["process_file"],
  "condition": {
    "type": "task_result",
    "task_id": "process_file",
    "field": "success",
    "value": true
  }
}
```

This task will only run if the `process_file` task was successful.

## Template Variables

Template variables allow passing results from previous tasks to later ones:

```json
{
  "id": "show_summary",
  "tool_name": "bash",
  "arguments": {
    "command": "echo 'Processed ${file_count} files with ${change_count} changes'"
  },
  "depends_on": ["process_files"],
  "template_vars": {
    "file_count": {
      "type": "task_result",
      "task_id": "process_files",
      "field": "file_count",
      "default": "0"
    },
    "change_count": {
      "type": "task_result",
      "task_id": "process_files",
      "field": "changes",
      "default": "0"
    }
  }
}
```

Here, the values from the `process_files` task results are used in the command.

## Error Handling

The `stop_on_failure` flag controls whether execution should continue if a task fails:

```json
{
  "name": "Safe File Processing",
  "description": "Process files with error handling",
  "stop_on_failure": false,
  "tasks": [...]
}
```

With `stop_on_failure: false`, the plan will continue executing tasks even if some fail, as long as their dependencies are met.

## Real-World Example: Code Refactoring

Here's a practical example plan for finding and refactoring deprecated function calls:

```json
{
  "name": "Find and Refactor Deprecated Functions",
  "description": "Search for deprecated function calls and update them",
  "stop_on_failure": true,
  "tasks": [
    {
      "id": "find_deprecated",
      "tool_name": "grep",
      "description": "Find deprecated function calls",
      "arguments": {
        "pattern": "oldFunction\\(",
        "path": "src",
        "include": "*.js"
      }
    },
    {
      "id": "backup_files",
      "tool_name": "bash",
      "description": "Backup affected files",
      "arguments": {
        "command": "mkdir -p backups && cp ${file_list} backups/ || echo 'No files to backup'"
      },
      "depends_on": ["find_deprecated"],
      "condition": {
        "type": "task_result",
        "task_id": "find_deprecated",
        "field": "match_count",
        "operator": "not_equals",
        "value": 0
      },
      "template_vars": {
        "file_list": {
          "type": "task_result",
          "task_id": "find_deprecated",
          "field": "matching_files",
          "default": ""
        }
      }
    },
    {
      "id": "refactor_code",
      "tool_name": "batch",
      "description": "Replace deprecated function calls",
      "arguments": {
        "operation": "replace",
        "path": "src",
        "file_pattern": "*.js",
        "find": "oldFunction(",
        "replace": "newFunction("
      },
      "depends_on": ["backup_files"]
    },
    {
      "id": "run_tests",
      "tool_name": "bash",
      "description": "Run tests to verify changes",
      "arguments": {
        "command": "npm test || echo 'Tests failed'"
      },
      "depends_on": ["refactor_code"]
    },
    {
      "id": "report_results",
      "tool_name": "bash",
      "description": "Generate summary report",
      "arguments": {
        "command": "echo 'Refactoring complete. Modified ${file_count} files with ${change_count} replacements.'"
      },
      "depends_on": ["run_tests"],
      "template_vars": {
        "file_count": {
          "type": "task_result",
          "task_id": "refactor_code",
          "field": "files_changed",
          "default": "0"
        },
        "change_count": {
          "type": "task_result",
          "task_id": "refactor_code",
          "field": "total_modifications",
          "default": "0"
        }
      }
    }
  ]
}
```

## Using the Task Plan Tool

To execute a plan, use the `task_plan` tool:

```python
result = tool_manager.execute_tool(
    "task_plan",
    {"plan": my_plan},
    check_context_msg=True
)
```

For validation without execution:

```python
validation_result = tool_manager.execute_tool(
    "task_plan",
    {"plan": my_plan, "validate_only": True},
    check_context_msg=True
)
```

## Best Practices

1. Give each task a descriptive ID and description
2. Use meaningful dependencies to control execution flow
3. Add conditions to skip tasks when appropriate
4. Provide default values for template variables
5. Use `stop_on_failure` appropriately for your use case
6. Start with `validate_only=True` to check your plan before execution
7. Break complex operations into smaller, focused tasks
8. Use the task results for insights into what happened

## Debugging Task Plans

If a task plan fails, examine the results to see what went wrong:

```python
if not result.get("success"):
    print(f"Plan failed: {result.get('error')}")
    for task_id in result.get("failed_tasks", []):
        task_result = result.get("results", {}).get(task_id, {})
        print(f"Task {task_id} failed: {task_result.get('error')}")
```

You can also use `verbose=True` when initializing the Agent to get detailed logging of task execution.