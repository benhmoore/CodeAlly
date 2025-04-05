import os
from typing import Any, Dict

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class FileWriteTool(BaseTool):
    name = "file_write"
    description = "Write content to a file (creates or overwrites)"
    requires_confirmation = True

    def execute(self, path: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        Write content to a file (creates or overwrites).

        Args:
            path: The path to the file to write
            content: The content to write to the file
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the file was written successfully
                error: Error message if any
        """
        try:
            # Expand user home directory if present
            file_path = os.path.expanduser(path)

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return {"success": True, "error": ""}
        except Exception as e:
            return {"success": False, "error": str(e)}
