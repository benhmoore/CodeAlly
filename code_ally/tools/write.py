import os
import shutil
import time
import re
import json
from typing import Any, Dict, Optional

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class FileWriteTool(BaseTool):
    name = "file_write"
    description = """Write content to a file with enhanced options.
    
    Supports:
    - Standard overwrite mode
    - Append/prepend modes
    - Template-based content creation
    - Line insertion at specific positions
    - Automatic backup creation
    - Various file formats (auto-detected or specified)
    """
    requires_confirmation = True

    def execute(
        self,
        path: str,
        content: str = "",
        mode: str = "w",
        template: str = "",
        variables: Optional[Dict[str, Any]] = None,
        line_insert: int = -1,
        create_backup: bool = False,
        format: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Write content to a file with enhanced options.

        Args:
            path: The path to the file to write
            content: The content to write to the file
            mode: Write mode ('w' = overwrite, 'a' = append, 'p' = prepend)
            template: Template string with $variable placeholders
            variables: Dictionary of variables to substitute in template
            line_insert: Line number to insert at (1-based, negative counts from end)
            create_backup: Whether to create a backup of the existing file
            format: Force specific format for pretty-printing ('json', 'yaml', etc.)
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the file was written successfully
                error: Error message if any
                backup_path: Path to the backup file (if created)
                bytes_written: Number of bytes written
                file_path: The absolute path of the written file
        """
        try:
            # Expand user home directory if present
            file_path = os.path.expanduser(path)
            absolute_path = os.path.abspath(file_path)

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(absolute_path), exist_ok=True)

            # Generate content from template if provided
            final_content = content
            if template and not content:
                if variables is None:
                    variables = {}
                final_content = self._process_template(template, variables)

            # Format content if requested
            if format and final_content:
                final_content = self._format_content(final_content, format)

            # Create backup if requested and file exists
            backup_path = None
            if create_backup and os.path.exists(absolute_path):
                backup_path = f"{absolute_path}.bak.{int(time.time())}"
                shutil.copy2(absolute_path, backup_path)

            # Determine write mode and perform the operation
            if mode == "a" and os.path.exists(absolute_path):
                # Append mode
                with open(absolute_path, "r", encoding="utf-8") as f:
                    existing_content = f.read()

                # Only add newline if the existing content doesn't end with one
                if existing_content and not existing_content.endswith("\n"):
                    final_content = "\n" + final_content

                with open(absolute_path, "a", encoding="utf-8") as f:
                    f.write(final_content)
                    bytes_written = len(final_content.encode("utf-8"))

            elif mode == "p" and os.path.exists(absolute_path):
                # Prepend mode
                with open(absolute_path, "r", encoding="utf-8") as f:
                    existing_content = f.read()

                # Only add newline if the content doesn't already have one
                if final_content and not final_content.endswith("\n"):
                    final_content += "\n"

                with open(absolute_path, "w", encoding="utf-8") as f:
                    f.write(final_content + existing_content)
                    bytes_written = len(
                        (final_content + existing_content).encode("utf-8")
                    )

            elif line_insert != -1 and os.path.exists(absolute_path):
                # Line insertion mode
                with open(absolute_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                # Ensure content ends with newline
                if final_content and not final_content.endswith("\n"):
                    final_content += "\n"

                # Convert 1-based indexing to 0-based, handle negative indices
                insert_pos = (
                    line_insert - 1 if line_insert > 0 else len(lines) + line_insert
                )
                insert_pos = max(0, min(insert_pos, len(lines)))

                # Insert content
                lines.insert(insert_pos, final_content)

                with open(absolute_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                    bytes_written = sum(len(line.encode("utf-8")) for line in lines)

            else:
                # Standard write mode (overwrite)
                with open(absolute_path, "w", encoding="utf-8") as f:
                    f.write(final_content)
                    bytes_written = len(final_content.encode("utf-8"))

            return {
                "success": True,
                "error": "",
                "backup_path": backup_path,
                "bytes_written": bytes_written,
                "file_path": absolute_path,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "backup_path": None,
                "bytes_written": 0,
                "file_path": file_path if "file_path" in locals() else path,
            }

    def _process_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Process a template string by substituting variables.

        Args:
            template: Template string with $variable placeholders
            variables: Dictionary of variables to substitute

        Returns:
            Processed template with variables substituted
        """
        result = template

        # Simple variable substitution
        for var_name, var_value in variables.items():
            # Handle different value types
            if isinstance(var_value, (dict, list)):
                # Convert to JSON string for complex types
                val_str = json.dumps(var_value, indent=2)
            else:
                # Convert to string for simple types
                val_str = str(var_value)

            # Replace both ${var} and $var patterns
            result = result.replace(f"${{{var_name}}}", val_str)
            result = result.replace(f"${var_name}", val_str)

        return result

    def _format_content(self, content: str, format_type: str) -> str:
        """Format content according to specified format.

        Args:
            content: Content to format
            format_type: Format type ('json', 'yaml', etc.)

        Returns:
            Formatted content
        """
        format_type = format_type.lower()

        if format_type == "json":
            try:
                # Try to parse as JSON and then pretty-print
                data = json.loads(content)
                return json.dumps(data, indent=2, sort_keys=True)
            except json.JSONDecodeError:
                # If it's not valid JSON, return as is
                return content

        elif format_type == "yaml" or format_type == "yml":
            try:
                import yaml

                # Try to parse as YAML and then pretty-print
                data = yaml.safe_load(content)
                return yaml.dump(data, default_flow_style=False)
            except (ImportError, yaml.YAMLError):
                # If yaml is not available or content is not valid YAML
                return content

        # For unsupported formats, return content as is
        return content
