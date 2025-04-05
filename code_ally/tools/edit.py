import os
from typing import Any, Dict

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class FileEditTool(BaseTool):
    name = "file_edit"
    description = "Edit an existing file by replacing a specific portion"
    requires_confirmation = True

    def execute(
        self, path: str, old_text: str, new_text: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Edit an existing file by replacing a specific portion.

        Args:
            path: The path to the file to edit
            old_text: The text to replace
            new_text: The text to replace it with
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the file was edited successfully
                error: Error message if any
        """
        try:
            # Expand user home directory if present
            file_path = os.path.expanduser(path)

            if not os.path.exists(file_path):
                return {"success": False, "error": f"File not found: {file_path}"}

            if not os.path.isfile(file_path):
                return {"success": False, "error": f"Path is not a file: {file_path}"}

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if old_text not in content:
                return {
                    "success": False,
                    "error": f"Text to replace not found in the file: {file_path}",
                }

            new_content = content.replace(old_text, new_text)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return {"success": True, "error": ""}
        except Exception as e:
            return {"success": False, "error": str(e)}
