"""Guidance for using Git commands via the bash tool."""

GIT_GUIDANCE = """
**GIT TOOL GUIDANCE (via Bash)**

**CRITICAL:** All Git operations MUST use the `bash` tool (e.g., `bash command="git status"`). NEVER fabricate Git output.

**MANDATORY VERIFICATION AFTER *EVERY* GIT COMMAND:**

* **Core Status Check:** Always run `bash command="git status"` immediately after *any* git command that modifies state (add, commit, checkout, merge, pull, push, reset, etc.).
* **Staging Check (after `git add`):** Also run `bash command="git diff --staged --name-status"` to confirm exactly what was staged.
* **Commit Check (after `git commit`):** Also run `bash command="git log -1"` to view the latest commit details.
* **Branch Check (after `checkout`, `branch`):** Also run `bash command="git branch"` to confirm the current branch and existing branches.
* **Remote Check (after `push`, `pull`, `Workspace`):** Also run `bash command="git remote -v"` and potentially `git log origin/main..main` (adjust branch names) to compare local and remote state.

**STANDARD WORKFLOWS (Examples with MANDATORY Verification):**

1.  **Initializing & First Commit:**
    * `bash command="pwd"` -> Get literal path `[cwd]`
    * `bash command="git init"` -> Show exact output.
    * **Verify:** `bash command="git status"` -> Show exact output.
    * `file_write path="[cwd]/README.md" content="..."`
    * **Verify:** `bash command="ls -la [cwd]/README.md"`
    * **Verify:** `bash command="git status"` -> Show untracked file.
    * `bash command="git add README.md"`
    * **Verify:** `bash command="git status"` -> Show staged file.
    * **Verify:** `bash command="git diff --staged --name-status"` -> Show staged changes.
    * `bash command="git commit -m 'Initial commit: Add README'"` -> Show exact output.
    * **Verify:** `bash command="git status"` -> Show working tree clean.
    * **Verify:** `bash command="git log -1"` -> Show commit details.

2.  **Branching & Merging:**
    * `bash command="git checkout -b feature/new-feature"` -> Show exact output.
    * **Verify:** `bash command="git status"` -> Show on new branch.
    * **Verify:** `bash command="git branch"` -> Show new branch selected.
    * *... (make changes, add, commit with verification) ...*
    * `bash command="git checkout main"` -> Show exact output.
    * **Verify:** `bash command="git status"` -> Show on main branch.
    * `bash command="git merge --no-ff feature/new-feature -m 'Merge: Integrate new feature'"` -> Show exact output.
    * **Verify:** `bash command="git status"` -> Show working tree clean (or conflicts).
    * **Verify:** `bash command="git log --oneline -n 5 --graph"` -> Show merge history.

**KEY PRINCIPLES:**

* **Use `bash`:** Every git command runs inside `bash command="..."`.
* **Show Exact Output:** Always display the literal output from the `bash` tool for each git command.
* **Verify Relentlessly:** Perform the specified `git status` and other verification checks immediately after each relevant command.
* **Commit Messages:** Use clear, conventional commit messages (e.g., "feat(auth): Implement password reset").
* **Literal Placeholders:** Replace placeholders like `[cwd]` with the actual string output from `bash command="pwd"`.
"""
