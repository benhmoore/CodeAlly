<<<<<<< Updated upstream
"""Bash execution guidance for contextual help."""
=======
"""Guidance for using the bash tool."""
>>>>>>> Stashed changes

BASH_GUIDANCE = """
**BASH TOOL GUIDANCE**

**CORE USAGE:** Execute shell commands, run scripts, and interact with the file system.

<<<<<<< Updated upstream
1. COMMAND CONSTRUCTION:
   - Use full paths for commands and files when possible
   - Quote variable values and paths with spaces: `echo "Hello $USER"`
   - Chain commands appropriately with && (AND) or || (OR): `mkdir dir && cd dir`
   - For complex operations, prefer creating and running a script over long one-liners
   - Use command substitution for dynamic values: `find $(pwd) -name "*.py"`

2. PROCESS MANAGEMENT:
   - For long-running commands, consider setting appropriate timeouts
   - Avoid starting background processes with &, as they can't be managed properly
   - Route output explicitly: `command > output.txt 2> error.txt`
   - For data processing, use pipes efficiently: `cat file.txt | grep pattern | sort`
   - Always clean up temporary files and processes when done

3. FILE SYSTEM OPERATIONS:
   - Navigate using absolute paths rather than relative paths
   - Use `mkdir -p` to create nested directory structures
   - When copying files, preserve permissions with `cp -p`
   - For file searches, use `find` with appropriate filters: `find . -type f -name "*.py" -mtime -7`
   - For moving files, verify target directory exists first

4. ENVIRONMENT HANDLING:
   - Check environment before operations: `python --version`, `node --version`
   - Set environment variables appropriately for commands: `ENV_VAR=value command`
   - Use `which` to find available tools: `which pip`
   - For path manipulation, use `realpath` or `readlink -f` to resolve symlinks
   - Respect language-specific environment managers (.venv, node_modules, etc.)

5. ERROR HANDLING:
   - Check command exit codes when critical: `command && echo "Success" || echo "Failed"`
   - Provide explanatory output when commands fail
   - When a command fails, try alternate approaches
   - For missing tools, suggest installation commands
   - Handle text encoding issues with explicit UTF-8 options when needed
=======
**CRITICAL RULES:**

1.  **Path Handling (Input to *Other* Tools):**
    * **NEVER** use shell variables (`$(pwd)`, `${HOME}`), placeholders (`[cwd]`), or example paths *within* other tool arguments (like `file_write path=...`).
    * **ALWAYS** get the literal path string first using `bash`:
        * Call `bash command="pwd"` -> Capture the exact output string (e.g., the string `/actual/runtime/path`).
    * Use the **captured literal string** when constructing paths for `file_write`, `file_edit`, etc.

2.  **Script Execution Workflow (MANDATORY):**
    * If you create *any* script file using `file_write`:
        a.  Determine the **literal path** `[script_path]` where the file was written (e.g., `/actual/runtime/path/script.py`, using the actual output from `pwd`).
        b.  **IMMEDIATELY** verify its existence: `bash command="ls -la [script_path]"` (using the literal path).
        c.  **IMMEDIATELY** attempt to execute it using `bash`:
            * Python: `bash command="python [script_path]"` (using the literal path).
        d.  Show the **exact, complete output** (or error) from the execution command.
    * **DO NOT** claim a script runs without actually executing it via `bash`.

3.  **Command Output:**
    * **ONLY** show the actual, literal output returned by the `bash` tool.

4.  **Verification:**
    * After creating files/dirs: Use `bash command="ls -la /actual/literal/path"` to verify.
    * After installs: Use appropriate check commands (`which`, etc.).
    * After git ops: Use `bash command="git status"` etc.
>>>>>>> Stashed changes

5.  **Avoid Workflow Repetition:** Execute a logical sequence **only once** per request unless retrying after an error.

<<<<<<< Updated upstream
DETAILED EXAMPLES:

Example 1: Setting up a Python virtual environment and installing dependencies
```
# Check Python version first
bash command="python --version"

# Create a virtual environment
bash command="python -m venv venv"

# Activate the virtual environment (use the appropriate command for your shell)
bash command="source venv/bin/activate"

# Install dependencies from requirements file
bash command="pip install -r requirements.txt"

# Verify installation
bash command="pip list"

# Run a Python script in the virtual environment
bash command="python src/main.py"
```

Example 2: Processing log files and extracting information
```
# Find log files from the past week
bash command="find /var/log -type f -name '*.log' -mtime -7"

# Count occurrences of ERROR in log files
bash command="grep -c 'ERROR' /var/log/application.log"

# Extract and sort unique error messages
bash command="grep 'ERROR' /var/log/application.log | cut -d ':' -f 4 | sort | uniq -c | sort -nr"

# Save the results to a report file
bash command="grep 'ERROR' /var/log/application.log | cut -d ':' -f 4 | sort | uniq -c | sort -nr > error_report.txt"

# Check the report
bash command="head error_report.txt"
```

Example 3: Deploying a web application
```
# Build the application
bash command="npm run build"

# Make sure destination directory exists
bash command="mkdir -p /var/www/myapp"

# Copy the built files to the deployment directory
bash command="cp -rp dist/* /var/www/myapp/"

# Set proper permissions
bash command="chmod -R 755 /var/www/myapp"

# Restart the web server
bash command="systemctl restart nginx"

# Verify the deployment by checking the service status
bash command="systemctl status nginx"

# Test the website is accessible
bash command="curl -I http://localhost"
```

Use these guidelines to construct effective, safe bash commands that produce reliable results.
=======
**EXAMPLES (Showing Process - Replace Placeholders with ACTUAL `pwd` Output):**

1.  **Creating and Running a Python Script:**
    * *Thought: Need the current directory.*
    * `bash command="pwd"`
    * *Tool Output:* `/actual/path/from/pwd/output`
    * *Thought: Use the literal output '/actual/path/from/pwd/output' to create the file path.*
    * `file_write path="/actual/path/from/pwd/output/hello.py" content="print('Hello!')"`
    * *Thought: Verify using the literal path.*
    * `bash command="ls -la /actual/path/from/pwd/output/hello.py"`
    * *Tool Output:* (File details)
    * *Thought: Run using the literal path.*
    * `bash command="python /actual/path/from/pwd/output/hello.py"`
    * *Tool Output:* `Hello!`

2.  **Creating a Directory:**
    * *Thought: Need the current directory.*
    * `bash command="pwd"`
    * *Tool Output:* `/some/actual/path`
    * *Thought: Use literal output '/some/actual/path' to create dir path.*
    * `bash command="mkdir /some/actual/path/new_dir"`
    * *Thought: Verify directory using the literal path.*
    * `bash command="ls -la /some/actual/path"`
    * *Tool Output:* (shows `new_dir` listed)

**SAFETY:**
* Avoid `sudo`.
* Be cautious with `rm -rf`; use specific literal paths.
* Quote paths/variables with spaces: `bash command="ls -la '/actual path/with spaces/file.txt'"`
>>>>>>> Stashed changes
"""
