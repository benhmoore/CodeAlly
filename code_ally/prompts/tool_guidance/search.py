"""Guidance for using search tools (glob, grep)."""

SEARCH_GUIDANCE = """
**SEARCH TOOLS GUIDANCE (glob, grep)**

**CORE STRATEGY:** Use `glob` to find files by name/pattern, and `grep` to find content within files. Often used together.

**WORKFLOWS & VERIFICATION:**

1.  **Finding Files (`glob`):**
    * Use patterns like `*.py`, `**/*.js` (recursive), `**/test_*.py`.
    * Use `ignore` for directories like `node_modules`, `__pycache__`, `.git`.
    * Example: `glob pattern="src/**/*.ts" ignore="**/node_modules/**"`
    * **Verification:** The results *are* the found paths. Use these paths in subsequent `file_read`, `grep`, or `bash` commands. Don't assume content based on filename alone.

2.  **Finding Content (`grep`):**
    * Provide a clear `pattern` (regex recommended for precision).
    * Specify `path` (e.g., a specific file from `glob`) or `include`/`exclude` patterns (like `glob`).
    * Example: `grep pattern="class\\s+UserService" include="**/*.py"`
    * **Verification:** The results show matching lines and files. **ALWAYS** follow up by using `file_read` on the reported files (or using `grep` with context `-C 5`) to understand the full context of the match. Don't act based only on the single matched line.

3.  **Combined Search (Common Pattern):**
    * Step 1: Find relevant files (`glob`).
        * `glob pattern="**/config*.json"` -> Returns `['path/to/config.json', 'path/to/db_config.json']`
    * Step 2: Search within those specific files (`grep`).
        * `grep pattern='"port":\\s*\\d+' path="path/to/config.json"`
        * `grep pattern='"port":\\s*\\d+' path="path/to/db_config.json"`
    * Step 3: Analyze context (`file_read`).
        * `file_read path="path/to/config.json"` (if grep found a match and more context is needed).

**EFFECTIVE PATTERNS:**

* **Grep:**
    * Function definitions: `def\\s+\\w+\\(`, `function\\s+\\w+\\(`
    * Class definitions: `class\\s+\\w+`
    * Imports: `^import\\s+`, `^from\\s+`
    * API endpoints: `app\\.(get|post|put|delete)\\(['"]`
    * Specific errors: `"NullPointerException"`, `IndexError`
* **Glob:**
    * All Python files recursively: `**/*.py`
    * Configs in any subdir: `**/*config*.{yaml,json,toml}`
    * Tests excluding fixtures: `**/test_*.py` ignore `**/fixtures/**`

**ANALYSIS:**
* Use search results to understand project structure, locate definitions, find error sources, or identify areas for refactoring.
* Always verify findings by examining the actual file content in context.
"""
