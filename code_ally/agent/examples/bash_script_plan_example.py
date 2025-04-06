"""
Example of using task planning to create and execute a bash script.

This example demonstrates how to use the task planning system to:
1. Determine the current working directory
2. Create a new bash script
3. Make the script executable
4. Execute the script
5. Display the results
"""

# Example plan for creating and running a bash script
BASH_SCRIPT_PLAN = {
    "name": "Create and Run Bash Script",
    "description": "Create a new bash script, make it executable, and run it",
    "stop_on_failure": True,
    "tasks": [
        {
            "id": "check_directory",
            "tool_name": "bash",
            "description": "Get current working directory",
            "arguments": {
                "command": "pwd"
            }
        },
        {
            "id": "create_script",
            "tool_name": "file_write",
            "description": "Create the bash script file",
            "depends_on": ["check_directory"],
            "arguments": {
                "path": "${working_dir}/hello.sh",
                "content": "#!/bin/bash\n\necho 'Hello from task planner!'\necho 'Current date:' $(date)\necho 'Directory:' $(pwd)\n"
            },
            "template_vars": {
                "working_dir": {
                    "type": "task_result",
                    "task_id": "check_directory",
                    "field": "output",
                    "default": "/tmp"
                }
            }
        },
        {
            "id": "make_executable",
            "tool_name": "bash",
            "description": "Make the script executable",
            "depends_on": ["create_script"],
            "arguments": {
                "command": "chmod +x ${script_path}"
            },
            "template_vars": {
                "script_path": {
                    "type": "static",
                    "value": "${working_dir}/hello.sh"
                },
                "working_dir": {
                    "type": "task_result",
                    "task_id": "check_directory",
                    "field": "output",
                    "default": "/tmp"
                }
            }
        },
        {
            "id": "run_script",
            "tool_name": "bash",
            "description": "Execute the script",
            "depends_on": ["make_executable"],
            "arguments": {
                "command": "${script_path}"
            },
            "template_vars": {
                "script_path": {
                    "type": "static",
                    "value": "${working_dir}/hello.sh"
                },
                "working_dir": {
                    "type": "task_result",
                    "task_id": "check_directory",
                    "field": "output",
                    "default": "/tmp"
                }
            }
        },
        {
            "id": "report_results",
            "tool_name": "bash",
            "description": "Report successful execution",
            "depends_on": ["run_script"],
            "arguments": {
                "command": "echo 'Script execution completed successfully!'"
            }
        }
    ]
}

"""
Example usage:

result = tool_manager.execute_tool(
    "task_plan",
    {"plan": BASH_SCRIPT_PLAN},
    check_context_msg=True
)

if result.get("success"):
    print("Successfully created and executed the bash script!")
    
    # Access specific task results
    script_output = result.get("results", {}).get("run_script", {}).get("output", "")
    print(f"Script output: {script_output}")
else:
    print(f"Failed to execute the plan: {result.get('error')}")
"""