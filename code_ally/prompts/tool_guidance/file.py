"""Guidance for using file operation tools (file_read, file_write, file_edit)."""

FILE_GUIDANCE = """
**FILE OPERATIONS GUIDANCE (file_read, file_write, file_edit)**

**CRITICAL: Path Handling - Follow This Exact Procedure:**
1.  **Step 1: Get Base Path String:**
    * Call `bash command="pwd"` (or `echo $HOME`).
    * **Capture the EXACT string output** (e.g., the string `/actual/path/output/from/pwd`). Let's call this `[base_path_string]`.

2.  **Step 2: Construct Full Literal Path:**
    * Combine `[base_path_string]` with the filename/subdirs.
    * Example: `[full_literal_path] = [base_path_string] + "/subdir/myfile.txt"` resulting in the literal string `/actual/path/output/from/pwd/subdir/myfile.txt`.

3.  **Step 3: Use Full Literal Path in Tool:**
    * Provide the `[full_literal_path]` string directly in the `path` argument.
    * **Correct:** `file_write path="/actual/path/output/from/pwd/subdir/myfile.txt" ...`
    * **ABSOLUTELY FORBIDDEN:** Using placeholders (`[cwd]`), variables (`$(pwd)`), example paths, or unresolved paths in the `path` argument.

**WORKFLOWS & VERIFICATION:**

1.  **`file_write` (Creating/Overwriting Files):**
    * Determine the literal target path `[target_path]` using the 3 steps above.
    * Ensure parent dir exists (`bash command="mkdir -p /literal/path/to/parent"` if needed).
    * Execute `file_write path="[target_path]" content="..."`.
    * **MANDATORY Verification:** Immediately run `bash command="ls -la [target_path]"` (using the literal path) to confirm.
    * **If writing a script:** Proceed immediately to the Script Execution Workflow (Bash guidance) using the literal `[target_path]`.

2.  **`file_read` (Reading Files):**
    * Determine the literal path `[source_path]` using the 3 steps above.
    * Execute `file_read path="[source_path]"`.

3.  **`file_edit` (Modifying Files):**
    * Determine the literal path `[target_path]` using the 3 steps above.
    * **RECOMMENDED:** Use `file_read path="[target_path]"` first.
    * Execute `file_edit path="[target_path]" old_text="..." new_text="..."`.
    * **MANDATORY Verification:** Immediately run `file_read path="[target_path]"` or `grep` (using the literal path) to confirm.

**EXAMPLES (Showing Process - Replace Placeholders with ACTUAL `pwd` Output):**

1.  **Write and Verify:**
    * `bash command="pwd"` -> *Output:* `/real/working/dir`
    * *Thought: Base path is /real/working/dir. Target file is config.txt.*
    * `file_write path="/real/working/dir/config.txt" content="key=value"`
    * *Thought: Verify using literal path.*
    * `bash command="ls -la /real/working/dir/config.txt"` -> *Output:* (shows file details)

2.  **Edit and Verify:**
    * `bash command="pwd"` -> *Output:* `/path/from/pwd`
    * *Thought: File path is /path/from/pwd/settings.json.*
    * `file_read path="/path/from/pwd/settings.json"` -> *Output:* `{"enabled": false}`
    * *Thought: Edit using literal path.*
    * `file_edit path="/path/from/pwd/settings.json" old_text='"enabled": false' new_text='"enabled": true'`
    * *Thought: Verify edit using literal path.*
    * `file_read path="/path/from/pwd/settings.json"` -> *Output:* `{"enabled": true}`

**SAFETY:**
* Be cautious overwriting files.
* Avoid creating/editing outside the intended workspace.
* Do not write sensitive data unless managed securely.
"""
