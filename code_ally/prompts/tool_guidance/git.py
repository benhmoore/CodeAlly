"""Git-specific guidance for contextual help."""

GIT_GUIDANCE = """
ENHANCED GIT TOOL GUIDANCE:

When working with Git repositories, follow these specific guidelines:

1. REPOSITORY ANALYSIS:
   - Before any operation, get the current branch and status: `git branch` and `git status`
   - For commit history, use: `git log --oneline -n 10` to see recent commits first
   - For branch comparison: `git diff <branch1>..<branch2> --name-only` to list changed files

2. COMMIT WORKFLOW:
   - Stage specific files with purpose: `git add <specific-files>` (avoid `git add .` unless appropriate)
   - Always check what's being committed with: `git diff --staged` before committing
   - Write meaningful commit messages that explain WHY, not just WHAT
   - Standard format: "type(scope): message" (e.g., "fix(auth): resolve token validation bug")
   - Types: feat, fix, docs, style, refactor, test, chore

3. BRANCH OPERATIONS:
   - Create topic branches from main: `git checkout -b feature/name`
   - Use kebab-case for feature branches: `feature/user-authentication`
   - For merging, prefer: `git merge --no-ff` to preserve feature history
   - For complex merges, analyze with: `git log --graph --oneline --all`

4. UNDOING CHANGES:
   - For uncommitted changes: `git restore <file>` (not `git checkout -- <file>`)
   - For staged changes: `git restore --staged <file>` then `git restore <file>` if needed
   - For committed changes: `git revert <commit>` (creates new commit) over `git reset` (rewrites history)

5. CONFLICT RESOLUTION:
   - When conflicts occur, use `git status` to identify conflicted files
   - Resolve conflicts in each file, then `git add <file>` each resolved file
   - After resolving all conflicts, use `git commit` to complete the merge
   - Use `git merge --abort` if you need to start over

6. BEST PRACTICES:
   - Never force push to shared branches: avoid `git push --force` on main/master
   - Keep commits atomic: each commit should represent one logical change
   - Regularly pull upstream changes: `git pull --rebase origin main`
   - Verify remote operations with `git remote -v` before pushing

DETAILED EXAMPLES:

Example 1: Committing changes to specific files
```
# First check status to identify changed files
bash command="git status"

# View the specific changes that will be committed
bash command="git diff path/to/changed/file.js"

# Stage only specific files for commit
bash command="git add path/to/changed/file.js path/to/another/file.py"

# Verify what's staged before committing
bash command="git diff --staged"

# Create a meaningful commit
bash command="git commit -m 'fix(auth): resolve token validation when session expires'"

# Verify the commit was successful
bash command="git status"
```

Example 2: Branch management workflow
```
# First check current branch
bash command="git branch"

# Create and switch to a new feature branch
bash command="git checkout -b feature/user-profile"

# Make changes and commits to the feature branch
bash command="git add user/profile.js"
bash command="git commit -m 'feat(profile): add user avatar upload functionality'"

# When ready to merge back to main
bash command="git checkout main"
bash command="git pull" # Ensure main is up to date
bash command="git merge --no-ff feature/user-profile"
bash command="git push origin main"
```

Example 3: Resolving a merge conflict
```
# When conflict occurs during merge
bash command="git status" # Identify conflicted files

# Edit the conflicted files to resolve conflicts
file_read file_path="/path/to/conflicted/file.js"
file_edit file_path="/path/to/conflicted/file.js" old_string="<<<<<<< HEAD\ncode from current branch\n=======\ncode from other branch\n>>>>>>> other-branch" new_string="resolved code that combines both changes"

# Mark conflicts as resolved
bash command="git add /path/to/conflicted/file.js"

# Complete the merge
bash command="git commit" # Use default merge commit message

# Verify the merge was successful
bash command="git status"
```

Use these guidelines to perform Git operations expertly and maintain a clean repository history.
"""
