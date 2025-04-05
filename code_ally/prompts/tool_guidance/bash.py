"""Bash execution guidance for contextual help."""

BASH_GUIDANCE = """
ENHANCED BASH TOOL GUIDANCE:

When executing bash commands, follow these specific guidelines:

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

6. SECURITY BEST PRACTICES:
   - Never execute untrusted code or scripts
   - Avoid piping curl/wget output directly to bash
   - Use checksums when downloading files: `curl -sL example.com/file | sha256sum -c expected.sha256`
   - Avoid commands that run with elevated privileges unless necessary
   - Be cautious with wildcards in destructive commands (rm, chmod, etc.)

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
"""
