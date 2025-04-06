import os
import re
from typing import Any, Dict

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class FileEditTool(BaseTool):
    name = "file_edit"
    description = """Edit an existing file with multiple editing modes.
    
    Supports:
    - String replacement (old_text, new_text)
    - Line range editing (line_range)
    - Regex-based replacement (regex_pattern, regex_replacement)
    - Appending/prepending content (append, prepend)
    """
    requires_confirmation = True

    def execute(
        self,
        path: str,
        old_text: str = "",
        new_text: str = "",
        line_range: str = "",
        regex_pattern: str = "",
        regex_replacement: str = "",
        append: bool = False,
        prepend: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Edit an existing file using various editing modes.

        Args:
            path: The path to the file to edit
            old_text: The text to replace (string replacement mode)
            new_text: The text to replace it with or to insert
            line_range: Range of lines to edit (e.g., "5-10" or "5")
            regex_pattern: Regex pattern to match (regex replacement mode)
            regex_replacement: Replacement text for regex matches
            append: Whether to append content to the end of the file
            prepend: Whether to prepend content at the beginning of the file
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the file was edited successfully
                error: Error message if any
                lines_changed: Number of lines changed
                matches: Number of matches (for regex mode)
        """
        try:
            # Expand user home directory if present
            file_path = os.path.expanduser(path)

            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "lines_changed": 0,
                    "matches": 0,
                }

            if not os.path.isfile(file_path):
                return {
                    "success": False,
                    "error": f"Path is not a file: {file_path}",
                    "lines_changed": 0,
                    "matches": 0,
                }

            # Read the original file content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                original_lines = content.splitlines()

            lines_changed = 0
            matches = 0
            new_content = content

            # 1. Append mode
            if append and new_text:
                if not new_content.endswith("\n") and new_content:
                    new_content += "\n"
                new_content += new_text
                lines_changed = len(new_text.splitlines())

            # 2. Prepend mode
            elif prepend and new_text:
                if not new_content.startswith("\n") and new_content:
                    new_text += "\n"
                new_content = new_text + new_content
                lines_changed = len(new_text.splitlines())

            # 3. Line range editing
            elif line_range:
                lines = original_lines.copy()

                try:
                    # Parse line range (1-based in the interface, 0-based in code)
                    if "-" in line_range:
                        start, end = map(int, line_range.split("-"))
                        start = max(1, start) - 1  # Convert to 0-based
                        end = min(len(lines), end) - 1  # Convert to 0-based
                    else:
                        # Single line
                        start = int(line_range) - 1  # Convert to 0-based
                        end = start

                    # Replace the specified lines
                    new_lines = new_text.splitlines()
                    original_segment = lines[start : end + 1]
                    lines_changed = len(original_segment)

                    # Replace the segment with the new lines
                    lines[start : end + 1] = new_lines
                    new_content = "\n".join(lines)

                except ValueError:
                    return {
                        "success": False,
                        "error": f"Invalid line range: {line_range}",
                        "lines_changed": 0,
                        "matches": 0,
                    }

            # 4. Regex replacement
            elif regex_pattern:
                try:
                    regex = re.compile(regex_pattern, re.MULTILINE)
                    new_content, count = regex.subn(regex_replacement, content)
                    matches = count

                    # Calculate lines changed
                    new_lines = new_content.splitlines()
                    lines_changed = abs(len(new_lines) - len(original_lines))

                except re.error as e:
                    return {
                        "success": False,
                        "error": f"Invalid regex pattern: {str(e)}",
                        "lines_changed": 0,
                        "matches": 0,
                    }

            # 5. String replacement (original behavior)
            elif old_text and new_text:
                if old_text not in content:
                    return {
                        "success": False,
                        "error": f"Text to replace not found in the file: {file_path}",
                        "lines_changed": 0,
                        "matches": 0,
                    }

                # Count occurrences
                matches = content.count(old_text)

                # Replace the text
                new_content = content.replace(old_text, new_text)

                # Calculate lines changed
                old_lines = len(old_text.splitlines()) or 1
                new_lines = len(new_text.splitlines()) or 1
                lines_changed = (
                    abs(len(new_content.splitlines()) - len(original_lines))
                    or (old_lines != new_lines) * matches
                )

            else:
                # No edit operation specified
                return {
                    "success": False,
                    "error": "No edit operation specified. Please specify one of: old_text/new_text, line_range, regex_pattern/regex_replacement, append, or prepend.",
                    "lines_changed": 0,
                    "matches": 0,
                }

            # Write the changes back to the file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return {
                "success": True,
                "error": "",
                "lines_changed": lines_changed,
                "matches": matches,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "lines_changed": 0, "matches": 0}
