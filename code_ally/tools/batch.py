"""File: batch.py.

Execute operations on multiple files with filtering and pattern matching.
"""

import fnmatch
import glob as glob_mod
import os
import re
from typing import Any

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class BatchOperationTool(BaseTool):
    """Tool for performing batch operations on multiple files."""

    name = "batch"
    description = """Execute operations on multiple files with filtering and pattern matching.

    <tool_call>
    {"name": "batch", "arguments": {"operation": "replace", "path": "/path/to/dir", "file_pattern": "*.py", "find": "old_text", "replace": "new_text"}}
    </tool_call>
    
    Supports:
    - Search and replace across multiple files
    - Apply transformations with templates
    - Execute operations with file filtering
    - Preview changes before applying
    """
    requires_confirmation = True

    def execute(
        self,
        operation: str,
        path: str = ".",
        file_pattern: str = "*",
        exclude_pattern: str = "",
        find: str = "",
        replace: str = "",
        template: str = "",
        template_vars: dict[str, str] | None = None,
        recursive: bool = False,
        preview: bool = True,
        max_files: int = 100,
        create_backup: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Execute a batch operation on multiple files.

        Args:
            operation: Operation type ('replace', 'template', 'prepend', 'append')
            path: Directory path to operate on
            file_pattern: Pattern to match files (e.g., "*.py")
            exclude_pattern: Pattern to exclude files
            find: Text or regex pattern to find
            replace: Text to replace with
            template: Template text to apply
            template_vars: Variables to substitute in the template
            recursive: Whether to search directories recursively
            preview: Whether to preview changes without applying
            max_files: Maximum number of files to process
            create_backup: Whether to create backups
            **kwargs: Additional arguments

        Returns:
            Dict with keys:
                success: Whether the operation was successful
                error: Error message if any
                files: List of files processed with changes
                summary: Summary of operations performed
        """
        try:
            # Validate operation type
            valid_operations = ["replace", "template", "prepend", "append"]
            if operation not in valid_operations:
                return {
                    "success": False,
                    "error": f"Invalid operation: {operation}. Valid operations: {', '.join(valid_operations)}",
                    "files": [],
                    "summary": "",
                }

            # Expand path
            base_path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(base_path):
                return {
                    "success": False,
                    "error": f"Path does not exist: {base_path}",
                    "files": [],
                    "summary": "",
                }

            # Find matching files
            matching_files = self._find_matching_files(
                base_path,
                file_pattern,
                exclude_pattern,
                recursive,
                max_files,
            )

            if not matching_files:
                return {
                    "success": False,
                    "error": f"No files matching '{file_pattern}' found in {base_path}",
                    "files": [],
                    "summary": "",
                }

            # Process each file based on the operation type
            processed_files = []
            total_modifications = 0

            for file_path in matching_files:
                result = self._process_file(
                    file_path,
                    operation,
                    find,
                    replace,
                    template,
                    template_vars or {},
                    preview,
                    create_backup,
                )

                if result["modifications"] > 0:
                    processed_files.append(result)
                    total_modifications += result["modifications"]

            # Create summary
            if not processed_files:
                summary = f"No changes made to any of the {len(matching_files)} matching files."
            else:
                files_changed = len(processed_files)
                op_description = {
                    "replace": "Replaced text",
                    "template": "Applied template",
                    "prepend": "Prepended content",
                    "append": "Appended content",
                }[operation]

                summary = f"{op_description} in {files_changed} of {len(matching_files)} matching files, with {total_modifications} total modifications."

                if preview:
                    summary = f"Preview: {summary}"

            return {
                "success": True,
                "error": "",
                "files": processed_files,
                "summary": summary,
                "total_files": len(matching_files),
                "files_changed": len(processed_files),
                "total_modifications": total_modifications,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing batch operation: {str(e)}",
                "files": [],
                "summary": "",
            }

    def _find_matching_files(
        self,
        base_path: str,
        file_pattern: str,
        exclude_pattern: str,
        recursive: bool,
        max_files: int,
    ) -> list[str]:
        """
        Find files matching the given patterns.

        Args:
            base_path: Base directory
            file_pattern: Pattern to match files
            exclude_pattern: Pattern to exclude files
            recursive: Whether to search recursively
            max_files: Maximum number of files to return

        Returns:
            List of matching file paths
        """
        matching_files = []

        if recursive:
            # For recursive search, we need to walk the directory tree
            for root, _, files in os.walk(base_path):
                for filename in files:
                    if len(matching_files) >= max_files:
                        break

                    filepath = os.path.join(root, filename)

                    # Skip directories and binary files
                    if os.path.isdir(filepath) or self._is_binary_file(filepath):
                        continue

                    # Check if the file matches the pattern
                    if fnmatch.fnmatch(filename, file_pattern):
                        # Check if it should be excluded
                        if exclude_pattern and fnmatch.fnmatch(
                            filename,
                            exclude_pattern,
                        ):
                            continue

                        matching_files.append(filepath)

                if len(matching_files) >= max_files:
                    break
        else:
            # Non-recursive search, just look in the base directory
            search_pattern = os.path.join(base_path, file_pattern)
            for filepath in glob_mod.glob(search_pattern):
                if len(matching_files) >= max_files:
                    break

                # Skip directories and binary files
                if os.path.isdir(filepath) or self._is_binary_file(filepath):
                    continue

                # Check if it should be excluded
                filename = os.path.basename(filepath)
                if exclude_pattern and fnmatch.fnmatch(filename, exclude_pattern):
                    continue

                matching_files.append(filepath)

        return matching_files

    def _is_binary_file(self, file_path: str) -> bool:
        """Check if a file appears to be binary.

        Args:
            file_path: Path to the file

        Returns:
            True if the file appears to be binary, False otherwise
        """
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\0" in chunk  # Simple heuristic: contains null bytes
        except Exception:
            return True

    def _process_file(
        self,
        file_path: str,
        operation: str,
        find: str,
        replace: str,
        template: str,
        template_vars: dict[str, str],
        preview: bool,
        create_backup: bool,
    ) -> dict[str, Any]:
        """
        Process a single file based on the operation type.

        Args:
            file_path: Path to the file
            operation: Operation type
            find: Text or pattern to find
            replace: Text to replace with
            template: Template text
            template_vars: Template variables
            preview: Whether to preview changes
            create_backup: Whether to create backup

        Returns:
            Dict with processing results
        """
        try:
            # Read the file
            with open(file_path, encoding="utf-8") as f:
                original_content = f.read()

            # Process based on operation type
            new_content = original_content
            modifications = 0

            if operation == "replace":
                # Check if we have both find and replace parameters
                if not find:
                    return {
                        "file": file_path,
                        "error": "Missing 'find' parameter for replace operation",
                        "modifications": 0,
                        "preview": "",
                    }

                # Determine if it's a regex pattern
                is_regex = find.startswith("r'") or find.startswith('r"')
                if is_regex:
                    # Remove the 'r' prefix and quotes
                    pattern = (
                        find[2:-1]
                        if find.endswith("'") or find.endswith('"')
                        else find[1:]
                    )
                    try:
                        # Apply regex replacement
                        new_content, count = re.subn(pattern, replace, original_content)
                        modifications = count
                    except re.error as e:
                        return {
                            "file": file_path,
                            "error": f"Invalid regex pattern: {str(e)}",
                            "modifications": 0,
                            "preview": "",
                        }
                else:
                    # Simple string replacement
                    new_content = original_content.replace(find, replace)
                    modifications = original_content.count(find)

            elif operation == "template":
                if not template:
                    return {
                        "file": file_path,
                        "error": "Missing 'template' parameter for template operation",
                        "modifications": 0,
                        "preview": "",
                    }

                # Apply template by substituting variables
                new_content = template
                for var_name, var_value in template_vars.items():
                    new_content = new_content.replace(f"${{{var_name}}}", var_value)
                    new_content = new_content.replace(f"${var_name}", var_value)

                if new_content != template:
                    modifications = 1

            elif operation == "prepend":
                content_to_add = replace if replace else template
                if not content_to_add:
                    return {
                        "file": file_path,
                        "error": "Missing content for prepend operation",
                        "modifications": 0,
                        "preview": "",
                    }

                # Add newline if needed
                if not content_to_add.endswith("\n"):
                    content_to_add += "\n"

                new_content = content_to_add + original_content
                modifications = 1

            elif operation == "append":
                content_to_add = replace if replace else template
                if not content_to_add:
                    return {
                        "file": file_path,
                        "error": "Missing content for append operation",
                        "modifications": 0,
                        "preview": "",
                    }

                # Add newline if needed
                if original_content and not original_content.endswith("\n"):
                    new_content = original_content + "\n" + content_to_add
                else:
                    new_content = original_content + content_to_add

                modifications = 1

            # Check if there were any changes
            if new_content == original_content:
                return {
                    "file": file_path,
                    "modifications": 0,
                    "preview": "",
                }

            # Get a preview of changes
            preview_content = self._generate_preview(original_content, new_content)

            # Apply changes if not just previewing
            if not preview:
                if create_backup:
                    # Create backup
                    backup_path = f"{file_path}.bak"
                    with open(backup_path, "w", encoding="utf-8") as f:
                        f.write(original_content)

                # Write new content
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

            return {
                "file": file_path,
                "modifications": modifications,
                "preview": preview_content if preview else "",
            }

        except Exception as e:
            return {
                "file": file_path,
                "error": str(e),
                "modifications": 0,
                "preview": "",
            }

    def _generate_preview(
        self,
        original: str,
        modified: str,
        context_lines: int = 3,
    ) -> str:
        """
        Generate a preview of changes between original and modified content.

        Args:
            original: Original content
            modified: Modified content
            context_lines: Number of context lines to include

        Returns:
            String with a preview of changes
        """
        import difflib

        if original == modified:
            return "No changes"

        # Generate unified diff
        original_lines = original.splitlines()
        modified_lines = modified.splitlines()

        diff_lines = list(
            difflib.unified_diff(
                original_lines,
                modified_lines,
                lineterm="",
                n=context_lines,
            ),
        )

        # Skip the first two lines (--- and +++ headers)
        if len(diff_lines) > 2:
            diff_lines = diff_lines[2:]

        return "\n".join(diff_lines)
