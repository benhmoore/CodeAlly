"""Guidance for using the bash tool."""

BASH_GUIDANCE = """
**BASH TOOL GUIDANCE**

**CORE USAGE:** Execute shell commands, run scripts, and interact with the file system.

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

5.  **Avoid Workflow Repetition:** Execute a logical sequence **only once** per request unless retrying after an error.

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
"""
