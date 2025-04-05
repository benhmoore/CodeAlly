import os
from typing import Any, Dict

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class LSTool(BaseTool):
    name = "ls"
    description = "List directory contents"
    requires_confirmation = False

    def execute(
        self, path: str = ".", file_pattern: str = None, **kwargs
    ) -> Dict[str, Any]:
        """
        List directory contents, optionally filtering by file pattern.

        Args:
            path: The directory to list (defaults to current directory)
            file_pattern: Optional pattern to filter files (e.g., "*.py", "*.txt")
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the listing was successful
                files: List of files in the directory
                directories: List of subdirectories in the directory
                error: Error message if any
                display: A formatted display string (for direct output)
                has_file_type: Dict with file extension counts (e.g., {"py": 2, "txt": 3})
        """
        try:
            # Expand user home directory if present
            dir_path = os.path.expanduser(path)

            if not os.path.exists(dir_path):
                return {
                    "success": False,
                    "files": [],
                    "directories": [],
                    "has_file_type": {},
                    "error": f"Directory not found: {dir_path}",
                    "display": f"Error: Directory not found: {dir_path}",
                }

            if not os.path.isdir(dir_path):
                return {
                    "success": False,
                    "files": [],
                    "directories": [],
                    "has_file_type": {},
                    "error": f"Path is not a directory: {dir_path}",
                    "display": f"Error: Path is not a directory: {dir_path}",
                }

            # Get directory contents
            contents = os.listdir(dir_path)

            # Separate files and directories
            files = []
            directories = []
            file_type_counts = {}

            for item in contents:
                item_path = os.path.join(dir_path, item)
                if os.path.isdir(item_path):
                    directories.append(item)
                else:
                    files.append(item)
                    # Count file extensions
                    _, ext = os.path.splitext(item)
                    if ext:
                        ext = ext[1:]  # Remove the dot
                        file_type_counts[ext] = file_type_counts.get(ext, 0) + 1

            # Apply file pattern filter if provided
            if file_pattern:
                import fnmatch

                files = [f for f in files if fnmatch.fnmatch(f, file_pattern)]

            # Sort the lists
            sorted_files = sorted(files)
            sorted_dirs = sorted(directories)

            # Create a display string for direct output
            display_lines = [f"Contents of directory: {os.path.abspath(dir_path)}"]

            if file_pattern:
                display_lines[0] += f" (filtered by: {file_pattern})"

            if sorted_dirs:
                display_lines.append("\nDirectories:")
                for directory in sorted_dirs:
                    display_lines.append(f"📁 {directory}/")

            if sorted_files:
                display_lines.append("\nFiles:")
                for file in sorted_files:
                    display_lines.append(f"📄 {file}")

            if not sorted_dirs and not sorted_files:
                display_lines.append("\nDirectory is empty.")
                if file_pattern:
                    display_lines.append(f"No files matching pattern: {file_pattern}")

            # Add file type summary if we have files
            if file_type_counts:
                display_lines.append("\nFile types:")
                for ext, count in sorted(file_type_counts.items()):
                    display_lines.append(f"- {ext}: {count} file(s)")

            display_text = "\n".join(display_lines)

            return {
                "success": True,
                "files": sorted_files,
                "directories": sorted_dirs,
                "has_file_type": file_type_counts,
                "error": "",
                "display": display_text,
            }
        except Exception as e:
            return {
                "success": False,
                "files": [],
                "directories": [],
                "error": str(e),
                "display": f"Error listing directory: {str(e)}",
            }
