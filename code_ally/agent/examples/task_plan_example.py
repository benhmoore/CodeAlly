"""
Example task plan for the Code Ally agent.

This file provides a practical example of how to create and use task plans
with the Code Ally agent's task planning system.
"""

# Example task plan for finding Python files and analyzing their imports
FIND_AND_ANALYZE_IMPORTS_PLAN = {
    "name": "Find and Analyze Python Imports",
    "description": "Search for Python files and analyze their import statements",
    "stop_on_failure": True,
    "tasks": [
        {
            "id": "find_python_files",
            "tool_name": "glob",
            "description": "Find all Python files in the project",
            "arguments": {
                "pattern": "**/*.py",
                "path": "."
            }
        },
        {
            "id": "check_files_found",
            "tool_name": "bash",
            "description": "Check if any Python files were found",
            "arguments": {
                "command": "echo 'Found ${file_count} Python files to analyze'",
            },
            "depends_on": ["find_python_files"],
            "template_vars": {
                "file_count": {
                    "type": "task_result",
                    "task_id": "find_python_files",
                    "field": "count",
                    "default": "0"
                }
            }
        },
        {
            "id": "find_imports",
            "tool_name": "grep",
            "description": "Find import statements in Python files",
            "arguments": {
                "pattern": "^import|^from\\s+\\w+\\s+import",
                "path": ".",
                "include": "*.py"
            },
            "depends_on": ["find_python_files"],
            "condition": {
                "type": "task_result",
                "task_id": "find_python_files",
                "field": "count",
                "operator": "not_equals",
                "value": 0
            }
        },
        {
            "id": "analyze_results",
            "tool_name": "bash",
            "description": "Summarize results",
            "arguments": {
                "command": "echo 'Analysis complete. Found ${match_count} import statements across ${file_count} Python files.'",
            },
            "depends_on": ["find_imports"],
            "template_vars": {
                "match_count": {
                    "type": "task_result",
                    "task_id": "find_imports",
                    "field": "match_count",
                    "default": "0"
                },
                "file_count": {
                    "type": "task_result",
                    "task_id": "find_python_files",
                    "field": "count",
                    "default": "0"
                }
            }
        }
    ]
}

# Example of using the task_plan tool via tool_manager
# (For reference, not executable as-is)
"""
# Execute the plan
result = tool_manager.execute_tool(
    "task_plan",
    {"plan": FIND_AND_ANALYZE_IMPORTS_PLAN},
    check_context_msg=True,
    client_type="ollama"
)

if result.get("success"):
    print(f"Plan executed successfully: {result.get('plan_name')}")
    print(f"Completed tasks: {result.get('completed_tasks')}")
    
    # Access individual task results
    for task_id, task_result in result.get("results", {}).items():
        print(f"Task {task_id}: {task_result.get('success')}")
else:
    print(f"Plan execution failed: {result.get('error')}")
    print(f"Failed tasks: {result.get('failed_tasks')}")
"""