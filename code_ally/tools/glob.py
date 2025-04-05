import glob
import os
from typing import Any, Dict

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class GlobTool(BaseTool):
    name = "glob"
    description = "Find files matching a glob pattern with improved context efficiency"
    requires_confirmation = False

    # pylint: disable=arguments-differ,too-many-arguments,too-many-locals,too-many-branches
    def execute(
        self,
        pattern: str,
        path: str = ".",
        limit: int = 20,
        show_content: bool = False,
        content_lines: int = 10,
        **kwargs,
    ) -> Dict[str, Any]:
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

            # Construct the glob pattern by joining the directory and pattern
            glob_pattern = os.path.join(search_dir, pattern)

            # Find all matching files
            files = glob.glob(glob_pattern, recursive=True)

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
                            with open(file_path, "r", encoding="utf-8") as f:
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
