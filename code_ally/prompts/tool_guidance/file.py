"""File operations guidance for contextual help."""

FILE_GUIDANCE = """
FILE OPERATIONS GUIDANCE:

When working with files and filesystem operations, follow these best practices:

1. FILE READING STRATEGY:
   - Before reading a file, verify its existence with: glob pattern="path/to/file*"
   - For large files, read in chunks using the offset and limit parameters
   - When examining code files, look for key patterns with grep after reading
   - For structured files (JSON, YAML, etc.) parse appropriately after reading

2. FILE WRITING WORKFLOW:
   - Before writing a file, check if parent directory exists: ls path="/path/to/dir"
   - Create parent directories if needed: bash command="mkdir -p /path/to/dir"
   - Use appropriate file extensions and naming conventions for the file type
   - For code files, follow language conventions and formatting standards
   - Always verify file creation with ls or glob after writing

3. FILE EDITING TECHNIQUE:
   - Read the entire file first to understand its structure and content
   - Identify unique context around the edit point (3-5 lines before and after)
   - Make minimal necessary changes that maintain code style consistency
   - After editing, verify the file is still valid (e.g., run linters, syntax checks)
   - Test functionality affected by the edit

4. DIRECTORY OPERATIONS:
   - Use ls to list directory contents before operating in unknown directories
   - Create directories with bash mkdir -p for nested paths
   - Use absolute paths when target locations are ambiguous
   - Remove directories carefully with explicit paths: bash command="rm -rf /specific/path"
   - Verify directory operations with ls afterward

5. FILE TYPE SPECIFIC HANDLING:
   - Python (.py): Check imports, respect indentation, follow PEP 8
   - JavaScript/TypeScript (.js/.ts): Respect module system, follow project style guide
   - Configuration files (.json, .yaml, .toml): Maintain exact formatting and structure
   - Markdown (.md): Preserve headings, links, and formatting
   - Executables and scripts: Set appropriate permissions after creation

6. SECURITY AND SAFETY:
   - Never create files with sensitive information (passwords, tokens, keys)
   - Never edit system files without explicit user permission
   - Use temporary files for intermediate processing when appropriate
   - Respect .gitignore patterns when creating files in git repositories
   - Always validate user-provided paths to prevent path traversal issues

DETAILED EXAMPLES:

Example 1: Reading and parsing a config file
```
# First check if the file exists
glob pattern="/app/config*.json"

# Read the file contents
file_read file_path="/app/config.json"

# If it's a large file, read specific parts
file_read file_path="/app/config.json" offset=100 limit=50

# To find specific settings in the file
grep pattern="API_KEY" path="/app/config.json"

# After reading, you might need to apply changes based on content
# (For example, if the file contains invalid JSON that needs fixing)
file_edit file_path="/app/config.json" old_string="{\n  \"api_key\": \"\"\n  \"host\": \"example.com\"\n}" new_string="{\n  \"api_key\": \"\",\n  \"host\": \"example.com\"\n}"
```

Example 2: Creating a new Python script
```
# First check if the directory exists
ls path="/app/scripts"

# Create directory if it doesn't exist
bash command="mkdir -p /app/scripts"

# Create the Python script
file_write file_path="/app/scripts/data_processor.py" content="#!/usr/bin/env python3\n\nimport json\nimport sys\n\ndef process_data(filename):\n    with open(filename, 'r') as f:\n        data = json.load(f)\n    \n    # Process the data\n    result = data['values']\n    return result\n\nif __name__ == '__main__':\n    if len(sys.argv) < 2:\n        print('Usage: data_processor.py <filename>')\n        sys.exit(1)\n    \n    result = process_data(sys.argv[1])\n    print(json.dumps(result, indent=2))"

# Make it executable
bash command="chmod +x /app/scripts/data_processor.py"

# Verify the file was created
ls path="/app/scripts"

# Test the script with an example input
bash command="python /app/scripts/data_processor.py /app/data/sample.json"
```

Example 3: Editing a specific function in a large codebase
```
# First locate the file containing the function
grep pattern="def calculate_tax" include="*.py"

# Read the file to understand the context
file_read file_path="/app/finance/tax_calculator.py"

# Make a precise edit with enough context to ensure uniqueness
file_edit file_path="/app/finance/tax_calculator.py" old_string="def calculate_tax(amount, rate):\n    \"\"\"Calculate tax amount.\"\"\"\n    return amount * rate" new_string="def calculate_tax(amount, rate):\n    \"\"\"Calculate tax amount with validation.\"\"\"\n    if amount < 0 or rate < 0:\n        raise ValueError(\"Amount and rate must be positive\")\n    return amount * rate"

# Test the changes
bash command="python -m pytest /app/tests/test_tax_calculator.py"
```

Use these guidelines to perform safe, effective file operations that maintain system integrity.
"""
