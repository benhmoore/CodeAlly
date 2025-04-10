"""Glob tool for finding files by pattern.

Provides file pattern matching functionality to locate files by name patterns.
"""

import glob
import os
from typing import Any

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class GlobTool(BaseTool):
    """Tool for finding files that match specific patterns with glob syntax."""

    name = "glob"
    description = """Find files matching a glob pattern with improved context efficiency.

    <tool_call>
    {"name": "glob", "arguments": {"pattern": "*.py", "path": "/search/directory", "show_content": true, "limit": 20}}
    </tool_call>

    Supports:
    - File searching with glob patterns
    - Directory traversal
    - Content preview for context efficiency
    - File sorting by modification time
    - Limiting results to a specified number
    - Error handling for non-existent directories
    """
    requires_confirmation = False

    # pylint: disable=arguments-differ,too-many-arguments,too-many-locals,too-many-branches
    def execute(
        self,
        **kwargs: dict[str, object],
    ) -> dict[str, Any]:
        """Execute the glob tool with the provided kwargs.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            A dictionary with glob search results
        """
        pattern = str(kwargs.get("pattern", ""))
        path = str(kwargs.get("path", "."))
        
        limit_val = kwargs.get("limit", 20)
        limit = int(limit_val) if isinstance(limit_val, int | str | float) else 20
        
        show_content = bool(kwargs.get("show_content", False))
        
        content_lines_val = kwargs.get("content_lines", 10)
        content_lines = int(content_lines_val) if isinstance(content_lines_val, int | str | float) else 10
        """
        Find files matching a glob pattern with content preview options to save context.

        Args:
            pattern: The glob pattern to match
            path: The directory to search in (defaults to current directory)
            limit: Maximum number of files to return (default: 20)
            show_content: Whether to include file content previews (default: False)
            content_lines: Number of lines to preview for each file (default: 10)
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the search was successful
                files: List of matching files or dict of files with content previews
                total_matches: Total number of matches found
                limited: Whether results were limited
                error: Error message if any
        """
        try:
            # Expand user home directory if present
            search_dir = os.path.expanduser(path)

            # Verify path doesn't contain traversal patterns
            if (
                ".." in search_dir
                or search_dir.startswith("/")
                or search_dir.startswith("~")
            ):
                # Convert to absolute path to verify CWD constraint
                abs_path = os.path.abspath(search_dir)
                cwd = os.path.abspath(os.getcwd())

                # If it's not within the current working directory, reject it
                if not abs_path.startswith(cwd):
                    return {
                        "success": False,
                        "files": [],
                        "total_matches": 0,
                        "limited": False,
                        "error": f"Access denied: Path '{path}' is outside the current working directory. Operations are restricted to '{cwd}' and its subdirectories.",
                    }

            if not os.path.exists(search_dir):
                return {
                    "success": False,
                    "files": [],
                    "total_matches": 0,
                    "limited": False,
                    "error": f"Directory not found: {search_dir}",
                }

            if not os.path.isdir(search_dir):
                return {
                    "success": False,
                    "files": [],
                    "total_matches": 0,
                    "limited": False,
                    "error": f"Path is not a directory: {search_dir}",
                }

            # Check if the pattern contains traversal attempts
            if ".." in pattern or pattern.startswith("/") or pattern.startswith("~"):
                return {
                    "success": False,
                    "files": [],
                    "total_matches": 0,
                    "limited": False,
                    "error": f"Access denied: Pattern '{pattern}' contains path traversal patterns. Operations are restricted to the current working directory and its subdirectories.",
                }

            # Construct the glob pattern by joining the directory and pattern
            glob_pattern = os.path.join(search_dir, pattern)

            # Find all matching files
            files = glob.glob(glob_pattern, recursive=True)

            # Filter out any files outside the current working directory
            cwd = os.path.abspath(os.getcwd())
            files = [f for f in files if os.path.abspath(f).startswith(cwd)]

            # Sort by modification time (newest first)
            files.sort(key=os.path.getmtime, reverse=True)

            # Compute total matches before limiting
            total_matches = len(files)
            limited = total_matches > limit

            # Limit results
            files = files[:limit]

            # If content preview is requested, read the files
            if show_content:
                file_previews = {}
                for file_path in files:
                    try:
                        # Skip directories and binary files
                        if os.path.isdir(file_path):
                            continue

                        # Read first few lines to check if binary
                        try:
                            with open(file_path, encoding="utf-8") as f:
                                preview_lines = []
                                for i, line in enumerate(f):
                                    if i >= content_lines:
                                        break
                                    preview_lines.append(line.rstrip())

                                if len(preview_lines) < content_lines:
                                    content_preview = "\n".join(preview_lines)
                                else:
                                    content_preview = (
                                        "\n".join(preview_lines) + "\n[...] (truncated)"
                                    )

                                file_previews[file_path] = content_preview
                        except UnicodeDecodeError:
                            # Skip binary files
                            file_previews[file_path] = "[Binary file]"

                    except Exception as exc:  # pylint: disable=broad-except
                        file_previews[file_path] = f"[Error reading file: {str(exc)}]"

                return {
                    "success": True,
                    "files": file_previews,
                    "total_matches": total_matches,
                    "limited": limited,
                    "error": "",
                }

            return {
                "success": True,
                "files": files,
                "total_matches": total_matches,
                "limited": limited,
                "error": "",
            }
        except Exception as exc:  # pylint: disable=broad-except
            return {
                "success": False,
                "files": [],
                "total_matches": 0,
                "limited": False,
                "error": str(exc),
            }
