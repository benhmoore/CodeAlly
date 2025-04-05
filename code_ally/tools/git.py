"""Git tool for interacting with git repositories.

This module provides tools for examining git history, file changes, and status.
"""

import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class GitTool(BaseTool):
    name = "git"
    description = (
        "Interact with git repositories and get information about commits and changes"
    )
    requires_confirmation = False

    # pylint: disable=arguments-differ,too-many-return-statements
    def execute(
        self,
        command: str,
        path: str = ".",
        max_items: int = 50,
        **kwargs,  # Used for passing arguments to specific git commands
    ) -> Dict[str, Any]:
        """
        Execute git commands and return formatted results.

        Args:
            command: Git command (status, log, diff, show, blame, branches, stash)
            path: Repository directory or file path (defaults to current directory)
            max_items: Maximum number of items to return (default: 50)
            **kwargs: Additional arguments for specific commands

        Returns:
            Dict with keys:
                success: Whether the command succeeded
                result: The formatted result of the command
                error: Error message if any
        """
        # Verify the path exists
        full_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(full_path):
            return self._format_error_response(f"Path does not exist: {full_path}")

        # Check that we're in a git repository
        try:
            self._run_git_command(["rev-parse", "--is-inside-work-tree"], full_path)
        except subprocess.CalledProcessError:
            return self._format_error_response(f"Not a git repository: {full_path}")

        # Handle the specified command
        try:
            if command == "status":
                return self._git_status(full_path)
            if command == "log":
                return self._git_log(full_path, max_items, **kwargs)
            if command == "diff":
                return self._git_diff(full_path, **kwargs)
            if command == "show":
                return self._git_show(full_path, **kwargs)
            if command == "blame":
                return self._git_blame(full_path, **kwargs)
            if command == "branches":
                return self._git_branches(full_path)
            if command == "stash":
                return self._git_stash(full_path)

            return self._format_error_response(
                f"Unsupported git command: {command}. "
                "Available commands: status, log, diff, show, blame, branches, stash"
            )
        except subprocess.CalledProcessError as e:
            return self._format_error_response(
                f"Git error: {str(e)}\n"
                f"Output: {e.stderr if hasattr(e, 'stderr') else ''}"
            )
        except Exception as e:  # pylint: disable=broad-except
            return self._format_error_response(f"Error: {str(e)}")

    def _run_git_command(
        self, args: List[str], cwd: str, check: bool = True
    ) -> Tuple[str, str]:
        """Run a git command and return stdout and stderr.

        Args:
            args: Git command arguments (without 'git')
            cwd: Directory to run the command in
            check: Whether to check the return code

        Returns:
            Tuple of (stdout, stderr)

        Raises:
            subprocess.CalledProcessError: If check is True and command returns non-zero
        """
        cmd = ["git"] + args
        process = subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return process.stdout.strip(), process.stderr.strip()

    def _git_status(self, repo_path: str) -> Dict[str, Any]:
        """Get git repository status.

        Args:
            repo_path: Path to the repository

        Returns:
            Formatted status information
        """
        # Get branch info
        branch_output, _ = self._run_git_command(
            ["branch", "--show-current"], repo_path
        )
        current_branch = branch_output.strip()

        # Get status
        status_output, _ = self._run_git_command(["status", "--porcelain"], repo_path)

        # Get status of staged files (useful for debugging)
        _, _ = self._run_git_command(["diff", "--staged", "--name-status"], repo_path)

        # Get remote tracking branch
        remote_branch = ""
        try:
            remote_output, _ = self._run_git_command(
                ["rev-parse", "--abbrev-ref", f"{current_branch}@{{upstream}}"],
                repo_path,
                check=False,
            )
            if remote_output and "fatal:" not in remote_output:
                remote_branch = remote_output
        except subprocess.CalledProcessError:
            # Not tracking a remote branch
            pass

        # Parse modified/added/deleted files
        files = {"staged": [], "unstaged": [], "untracked": []}

        for line in status_output.splitlines():
            if not line.strip():
                continue

            status = line[:2]
            filename = line[3:].strip()

            # Check status codes
            # See: https://git-scm.com/docs/git-status#_short_format
            if status[0] != " " and status[0] != "?":
                # Staged changes
                files["staged"].append(f"{status[0]} {filename}")

            if status[1] != " ":
                if status[1] == "?":
                    # Untracked file
                    files["untracked"].append(filename)
                else:
                    # Unstaged changes
                    files["unstaged"].append(f"{status[1]} {filename}")

        return self._format_success_response(
            branch=current_branch,
            remote_branch=remote_branch,
            files=files,
            raw_status=status_output,
        )

    def _git_log(
        self,
        repo_path: str,
        max_items: int = 50,
        file_path: Optional[str] = None,
        format_str: str = "%h|%an|%ar|%s",
        **kwargs,  # For since, until, author parameters
    ) -> Dict[str, Any]:
        """Get git commit history.

        Args:
            repo_path: Path to the repository
            max_items: Maximum number of log entries to return
            file_path: Optional file path to get history for
            format_str: Format string for git log

        Returns:
            Formatted commit history
        """
        args = ["log", f"--max-count={max_items}", f"--pretty=format:{format_str}"]

        # Add file path if specified
        if file_path:
            full_file_path = os.path.join(repo_path, file_path)
            relative_file_path = os.path.relpath(full_file_path, repo_path)
            args.append("--")
            args.append(relative_file_path)

        # Add any additional arguments
        if "since" in kwargs:
            args.append(f"--since={kwargs['since']}")
        if "until" in kwargs:
            args.append(f"--until={kwargs['until']}")
        if "author" in kwargs:
            args.append(f"--author={kwargs['author']}")

        output, _ = self._run_git_command(args, repo_path)

        commits = []
        for line in output.splitlines():
            if not line.strip():
                continue

            parts = line.split("|", 3)
            if len(parts) >= 4:
                commit = {
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3],
                }
                commits.append(commit)

        return self._format_success_response(
            commits=commits, total_commits=len(commits)
        )

    # pylint: disable=too-many-locals
    def _git_diff(
        self,
        repo_path: str,
        file_path: Optional[str] = None,
        staged: bool = False,
        commit: Optional[str] = None,
        **_,  # Unused kwargs
    ) -> Dict[str, Any]:
        """Get git diff information.

        Args:
            repo_path: Path to the repository
            file_path: Optional file path to get diff for
            staged: Whether to show staged changes
            commit: Optional commit to diff against

        Returns:
            Formatted diff information
        """
        args = ["diff", "--color=never"]

        if staged:
            args.append("--staged")

        if commit:
            if ".." in commit:
                # Range of commits
                args = ["diff", commit, "--color=never"]
            else:
                # Single commit
                args = ["diff", f"{commit}^..{commit}", "--color=never"]

        # Add file path if specified
        if file_path:
            full_file_path = os.path.join(repo_path, file_path)
            relative_file_path = os.path.relpath(full_file_path, repo_path)
            args.append("--")
            args.append(relative_file_path)

        output, _ = self._run_git_command(args, repo_path)

        # Get a summary of changed files
        summary_args = args.copy()
        summary_args.insert(1, "--name-status")
        summary, _ = self._run_git_command(summary_args, repo_path)

        changes = []
        for line in summary.splitlines():
            if not line.strip():
                continue

            parts = line.split("\t", 1)
            if len(parts) >= 2:
                status, filename = parts
                changes.append({"status": status, "file": filename})

        return self._format_success_response(
            diff=output, changes=changes, total_changes=len(changes)
        )

    # pylint: disable=too-many-locals
    def _git_show(
        self,
        repo_path: str,
        commit: str = "HEAD",
        show_diff: bool = False,
        **_,  # Other kwargs
    ) -> Dict[str, Any]:
        """Show git commit information.

        Args:
            repo_path: Path to the repository
            commit: The commit hash to show (default: HEAD)
            show_diff: Whether to include the full diff in the response

        Returns:
            Formatted commit information
        """
        # Get commit details
        format_str = "%h|%an|%ae|%at|%cn|%ce|%ct|%s"
        details_args = ["show", "--no-patch", f"--pretty=format:{format_str}", commit]
        details_output, _ = self._run_git_command(details_args, repo_path)

        commit_details = {}
        if details_output:
            parts = details_output.split("|", 7)
            if len(parts) >= 8:
                commit_details = {
                    "hash": parts[0],
                    "author_name": parts[1],
                    "author_email": parts[2],
                    "author_time": parts[3],
                    "committer_name": parts[4],
                    "committer_email": parts[5],
                    "commit_time": parts[6],
                    "message": parts[7],
                }

        # Get changed files
        files_args = ["show", "--name-status", "--oneline", commit]
        files_output, _ = self._run_git_command(files_args, repo_path)

        # Skip the first line which contains commit info
        files_lines = files_output.splitlines()[1:]

        # Parse file changes
        changes = []
        for line in files_lines:
            if not line.strip():
                continue

            parts = line.split("\t", 1)
            if len(parts) >= 2:
                status, filename = parts
                changes.append({"status": status, "file": filename})

        # Get full diff if requested
        diff = ""
        if show_diff:
            diff_args = ["show", "--color=never", commit]
            diff, _ = self._run_git_command(diff_args, repo_path)

        return self._format_success_response(
            commit=commit_details,
            changes=changes,
            total_changes=len(changes),
            diff=diff,
        )

    # pylint: disable=too-many-locals
    def _git_blame(
        self,
        repo_path: str,
        file_path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
        **_,  # Unused kwargs
    ) -> Dict[str, Any]:
        """Get git blame information for a file.

        Args:
            repo_path: Path to the repository
            file_path: File path to get blame for
            start_line: First line to blame (1-based index)
            end_line: Last line to blame (inclusive)

        Returns:
            Formatted blame information
        """
        if not file_path:
            return self._format_error_response(
                "file_path is required for blame command"
            )

        full_file_path = os.path.join(repo_path, file_path)
        if not os.path.isfile(full_file_path):
            return self._format_error_response(f"File not found: {full_file_path}")

        relative_file_path = os.path.relpath(full_file_path, repo_path)

        # Build arguments for git blame
        args = ["blame", "--line-porcelain"]

        # Add line range if specified
        if end_line:
            args.append(f"-L {start_line},{end_line}")
        elif start_line > 1:
            # Count lines in file to determine end
            with open(full_file_path, "r", encoding="utf-8", errors="replace") as f:
                line_count = sum(1 for _ in f)
            args.append(f"-L {start_line},{line_count}")

        args.append("--")
        args.append(relative_file_path)

        output, _ = self._run_git_command(args, repo_path)

        # Parse blame output
        blame_lines = []
        current_line = None
        current_commit = {}

        for line in output.splitlines():
            if not line.strip():
                continue

            # New blame line starts with commit hash, line number, etc.
            if line.startswith("^") or not line.startswith("\t"):
                if current_line is not None and current_commit:
                    blame_lines.append(
                        {
                            "line_number": current_line,
                            "commit": current_commit.copy(),
                            "content": content if "content" in locals() else "",
                        }
                    )

                parts = line.split(" ", 3)
                if len(parts) >= 3:
                    hash_val = parts[0].lstrip("^")
                    current_line = int(parts[2])
                    current_commit = {"hash": hash_val}
            elif line.startswith("\t"):
                # Line content
                content = line[1:]
            elif ":" in line:
                # Commit metadata
                key, value = line.split(" ", 1) if " " in line else (line, "")
                current_commit[key] = value

        # Add the last blame line
        if current_line is not None and current_commit:
            blame_lines.append(
                {
                    "line_number": current_line,
                    "commit": current_commit.copy(),
                    "content": content if "content" in locals() else "",
                }
            )

        return self._format_success_response(
            blame=blame_lines, file=file_path, total_lines=len(blame_lines)
        )

    def _git_branches(self, repo_path: str) -> Dict[str, Any]:
        """Get git branch information.

        Args:
            repo_path: Path to the repository

        Returns:
            Formatted branch information
        """
        # Get all branches
        output, _ = self._run_git_command(["branch", "-a"], repo_path)

        # Parse branches
        branches = {"local": [], "remote": [], "current": None}

        for line in output.splitlines():
            if not line.strip():
                continue

            is_current = line.startswith("*")
            branch_name = line[2:].strip()

            if is_current:
                branches["current"] = branch_name
                branches["local"].append(branch_name)
            elif "remotes/" in branch_name:
                # Remote branch
                remote_name = branch_name.replace("remotes/", "", 1)
                branches["remote"].append(remote_name)
            else:
                # Local branch
                branches["local"].append(branch_name)

        return self._format_success_response(
            branches=branches,
            total_local=len(branches["local"]),
            total_remote=len(branches["remote"]),
        )

    def _git_stash(self, repo_path: str) -> Dict[str, Any]:
        """Get git stash information.

        Args:
            repo_path: Path to the repository

        Returns:
            Formatted stash information
        """
        output, _ = self._run_git_command(["stash", "list"], repo_path)

        stashes = []
        for line in output.splitlines():
            if not line.strip():
                continue

            # Parse stash entry (format: stash@{N}: ...)
            parts = line.split(":", 1)
            if len(parts) >= 2:
                stash_id = parts[0].strip()
                message = parts[1].strip()
                stashes.append({"id": stash_id, "message": message})

        return self._format_success_response(
            stashes=stashes, total_stashes=len(stashes)
        )
