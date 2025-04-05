import os
import re
from typing import Any, Dict

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class GrepTool(BaseTool):
    name = "grep"
    description = "Search for a pattern in files"
    requires_confirmation = False

    def execute(
        self, pattern: str, path: str = ".", include: str = "*", **kwargs
    ) -> Dict[str, Any]:
        """
        Search for a pattern in files.

        Args:
            pattern: The regex pattern to search for
            path: The directory to search in (defaults to current directory)
            include: File pattern to include in the search (e.g. "*.py")
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the search was successful
                matches: List of matches (file path, line number, line content)
                error: Error message if any
        """
        try:
            # Expand user home directory if present
            search_dir = os.path.expanduser(path)

            if not os.path.exists(search_dir):
                return {
                    "success": False,
                    "matches": [],
                    "error": f"Directory not found: {search_dir}",
                }

            if not os.path.isdir(search_dir):
                return {
                    "success": False,
                    "matches": [],
                    "error": f"Path is not a directory: {search_dir}",
                }

            # Compile the regex pattern
            try:
                regex = re.compile(pattern)
            except re.error as e:
                return {
                    "success": False,
                    "matches": [],
                    "error": f"Invalid regex pattern: {e}",
                }

            matches = []
            matched_files = set()

            # Walk through the directory tree
            for root, _, files in os.walk(search_dir):
                for file in files:
                    # Check if the file matches the include pattern
                    if not self._matches_pattern(file, include):
                        continue

                    file_path = os.path.join(root, file)

                    # Skip binary files
                    if self._is_binary_file(file_path):
                        continue

                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            for i, line in enumerate(f, 1):
                                if regex.search(line):
                                    matches.append(
                                        {
                                            "file": file_path,
                                            "line": i,
                                            "content": line.strip(),
                                        }
                                    )
                                    matched_files.add(file_path)
                    except Exception:
                        # Skip files that can't be read
                        continue

            # Sort matches by file modification time (newest first)
            sorted_matches = sorted(
                matches, key=lambda m: os.path.getmtime(m["file"]), reverse=True
            )

            return {"success": True, "matches": sorted_matches, "error": ""}
        except Exception as e:
            return {"success": False, "matches": [], "error": str(e)}

    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if a filename matches a glob pattern."""
        import fnmatch

        return fnmatch.fnmatch(filename, pattern)

    def _is_binary_file(self, file_path: str) -> bool:
        """Check if a file is binary."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                f.read(1024)
                return False
        except UnicodeDecodeError:
            return True
