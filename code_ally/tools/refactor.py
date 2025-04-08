"""File: refactor.py

Advanced refactoring operations across multiple files with preview capabilities.
"""

import os
import re
import json
import fnmatch
import difflib
from typing import Any, Dict, List, Tuple, Optional, Set, Pattern

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class RefactorTool(BaseTool):
    """Tool for performing code refactoring operations across multiple files."""

    name = "refactor"
    description = """Perform code refactoring operations across multiple files.

    <tool_call>
    {"name": "refactor", "arguments": {"operation": "rename", "target": "old_symbol", "new_value": "new_symbol", "scope": "/code/directory", "preview": true}}
    </tool_call>
    
    Supports:
    - Rename symbol (variables, functions, classes) across files
    - Extract code to new files
    - Move code between files
    - Apply code transformations with regex patterns
    - Preview changes before applying
    """
    requires_confirmation = True

    # Refactoring operation types
    REFACTOR_TYPES = {
        "rename": "Rename a symbol across files",
        "extract": "Extract code to a new file",
        "move": "Move code between files",
        "transform": "Apply regex transformation across files",
    }

    def execute(
        self,
        operation: str,
        target: str,
        new_value: str = "",
        scope: str = ".",
        include_pattern: str = "*",
        exclude_pattern: str = "",
        preview: bool = True,
        apply: bool = False,
        create_backup: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute a refactoring operation across multiple files.

        Args:
            operation: Type of refactoring ('rename', 'extract', 'move', 'transform')
            target: Symbol or pattern to refactor
            new_value: New value or destination
            scope: Directory scope for the operation (default: current directory)
            include_pattern: Pattern of files to include (e.g., "*.py")
            exclude_pattern: Pattern of files to exclude (e.g., "test_*.py")
            preview: Whether to preview changes without applying them
            apply: Whether to apply the changes (requires confirmation)
            create_backup: Whether to create backups of modified files
            **kwargs: Additional operation-specific arguments

        Returns:
            Dict with keys:
                success: Whether the operation was successful
                error: Error message if any
                changes: List of files changed with diff information
                summary: Summary of the operations performed
        """
        try:
            # Expand user home directory if present
            scope_dir = os.path.expanduser(scope)

            if not os.path.exists(scope_dir):
                return {
                    "success": False,
                    "error": f"Directory not found: {scope_dir}",
                    "changes": [],
                    "summary": "",
                }

            if not os.path.isdir(scope_dir):
                return {
                    "success": False,
                    "error": f"Path is not a directory: {scope_dir}",
                    "changes": [],
                    "summary": "",
                }

            # Validate the operation type
            if operation not in self.REFACTOR_TYPES:
                valid_ops = ", ".join(self.REFACTOR_TYPES.keys())
                return {
                    "success": False,
                    "error": f"Invalid operation type: {operation}. Valid operations: {valid_ops}",
                    "changes": [],
                    "summary": "",
                }

            # Collect files that match the include/exclude patterns
            matching_files = self._collect_files(
                scope_dir, include_pattern, exclude_pattern
            )

            if not matching_files:
                return {
                    "success": False,
                    "error": f"No matching files found in {scope_dir} with pattern {include_pattern}",
                    "changes": [],
                    "summary": "",
                }

            # Execute the appropriate refactoring operation
            if operation == "rename":
                result = self._rename_symbol(
                    matching_files, target, new_value, preview, apply, create_backup
                )
            elif operation == "extract":
                result = self._extract_code(
                    matching_files,
                    target,
                    new_value,
                    preview,
                    apply,
                    create_backup,
                    **kwargs,
                )
            elif operation == "move":
                result = self._move_code(
                    matching_files,
                    target,
                    new_value,
                    preview,
                    apply,
                    create_backup,
                    **kwargs,
                )
            elif operation == "transform":
                result = self._transform_code(
                    matching_files,
                    target,
                    new_value,
                    preview,
                    apply,
                    create_backup,
                    **kwargs,
                )
            else:
                # This should never happen due to the validation above
                return {
                    "success": False,
                    "error": f"Invalid operation type: {operation}",
                    "changes": [],
                    "summary": "",
                }

            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing refactoring operation: {str(e)}",
                "changes": [],
                "summary": "",
            }

    def _collect_files(
        self, directory: str, include_pattern: str, exclude_pattern: str
    ) -> List[str]:
        """
        Collect files matching the include/exclude patterns recursively.

        Args:
            directory: Root directory to search in
            include_pattern: Pattern to include (e.g., "*.py")
            exclude_pattern: Pattern to exclude (e.g., "test_*.py")

        Returns:
            List of matching file paths
        """
        matching_files = []

        for root, _, files in os.walk(directory):
            for filename in files:
                filepath = os.path.join(root, filename)

                # Skip binary files
                if self._is_binary_file(filepath):
                    continue

                # Check include pattern
                if not fnmatch.fnmatch(filename, include_pattern):
                    continue

                # Check exclude pattern if provided
                if exclude_pattern and fnmatch.fnmatch(filename, exclude_pattern):
                    continue

                matching_files.append(filepath)

        return matching_files

    def _is_binary_file(self, file_path: str) -> bool:
        """
        Check if a file is binary.

        Args:
            file_path: Path to the file

        Returns:
            True if the file is binary, False otherwise
        """
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\0" in chunk  # Simple heuristic: contains null bytes
        except Exception:
            return True

    def _rename_symbol(
        self,
        files: List[str],
        old_symbol: str,
        new_symbol: str,
        preview: bool,
        apply: bool,
        create_backup: bool,
    ) -> Dict[str, Any]:
        """
        Rename a symbol across multiple files.

        Args:
            files: List of files to process
            old_symbol: Symbol to rename
            new_symbol: New symbol name
            preview: Whether to preview changes
            apply: Whether to apply changes
            create_backup: Whether to create backups

        Returns:
            Result dictionary with changes
        """
        changes = []
        total_occurrences = 0
        total_files_changed = 0

        # Prepare regex for matching whole word
        # This is a simplistic approach and might need refinement for complex cases
        symbol_pattern = re.compile(r"\b" + re.escape(old_symbol) + r"\b")

        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Count occurrences and prepare new content
                occurrences = len(symbol_pattern.findall(content))
                if occurrences == 0:
                    continue

                new_content = symbol_pattern.sub(new_symbol, content)

                # Generate diff for preview
                diff = self._generate_diff(file_path, content, new_content)

                # Apply changes if requested and not just preview
                if apply and not preview:
                    if create_backup:
                        backup_path = f"{file_path}.bak"
                        with open(backup_path, "w", encoding="utf-8") as f:
                            f.write(content)

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)

                changes.append(
                    {
                        "file": file_path,
                        "occurrences": occurrences,
                        "diff": diff if preview else "",
                    }
                )

                total_occurrences += occurrences
                total_files_changed += 1

            except Exception as e:
                changes.append(
                    {
                        "file": file_path,
                        "error": str(e),
                        "occurrences": 0,
                        "diff": "",
                    }
                )

        # Generate summary
        operation_mode = "Preview of " if preview and not apply else ""
        summary = f"{operation_mode}Rename '{old_symbol}' to '{new_symbol}': {total_occurrences} occurrences in {total_files_changed} files"

        return {
            "success": True,
            "error": "",
            "changes": changes,
            "summary": summary,
            "total_occurrences": total_occurrences,
            "total_files_changed": total_files_changed,
        }

    def _extract_code(
        self,
        files: List[str],
        extraction_pattern: str,
        new_file_path: str,
        preview: bool,
        apply: bool,
        create_backup: bool,
        include_imports: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Extract code matching a pattern to a new file.

        Args:
            files: List of files to process
            extraction_pattern: Regex pattern to match code for extraction
            new_file_path: Path for the new file
            preview: Whether to preview changes
            apply: Whether to apply changes
            create_backup: Whether to create backups
            include_imports: Whether to include related imports
            **kwargs: Additional arguments

        Returns:
            Result dictionary with changes
        """
        changes = []
        extracted_content = []
        imports = set()
        total_extractions = 0
        total_files_changed = 0

        # Prepare regex for extraction
        try:
            extract_regex = re.compile(extraction_pattern, re.MULTILINE | re.DOTALL)
        except re.error as e:
            return {
                "success": False,
                "error": f"Invalid regex pattern: {str(e)}",
                "changes": [],
                "summary": "",
            }

        # Extract code from files
        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Find all matches
                matches = list(extract_regex.finditer(content))
                if not matches:
                    continue

                # Extract the code
                extracted_segments = []
                new_content = content

                # Process matches in reverse to avoid index shifting when removing them
                for match in reversed(matches):
                    matched_text = match.group(0)
                    extracted_segments.append(matched_text)

                    # Remove the extracted code from original file
                    start, end = match.span()
                    new_content = new_content[:start] + new_content[end:]

                # If we're including imports, detect and collect them
                if include_imports:
                    # Simple import detection for Python
                    # This should be extended for other languages
                    if file_path.endswith(".py"):
                        import_pattern = re.compile(
                            r"^import\s+[\w\.]+|^from\s+[\w\.]+\s+import", re.MULTILINE
                        )
                        for match in import_pattern.finditer(content):
                            imports.add(match.group(0))

                # Generate diff for preview
                diff = self._generate_diff(file_path, content, new_content)

                # Add to extracted content
                extracted_content.extend(reversed(extracted_segments))

                # Apply changes if requested and not just preview
                if apply and not preview:
                    if create_backup:
                        backup_path = f"{file_path}.bak"
                        with open(backup_path, "w", encoding="utf-8") as f:
                            f.write(content)

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)

                changes.append(
                    {
                        "file": file_path,
                        "extractions": len(matches),
                        "diff": diff if preview else "",
                    }
                )

                total_extractions += len(matches)
                total_files_changed += 1

            except Exception as e:
                changes.append(
                    {
                        "file": file_path,
                        "error": str(e),
                        "extractions": 0,
                        "diff": "",
                    }
                )

        # Create new file with extracted content
        if extracted_content:
            new_file_content = ""

            # Add imports first if we have any
            if imports:
                new_file_content += "\n".join(sorted(imports)) + "\n\n"

            # Add extracted content
            new_file_content += "\n\n".join(extracted_content)

            # Preview or create the new file
            if apply and not preview:
                # Ensure directory exists
                os.makedirs(
                    os.path.dirname(os.path.abspath(new_file_path)), exist_ok=True
                )

                with open(new_file_path, "w", encoding="utf-8") as f:
                    f.write(new_file_content)

            # Add new file to changes
            changes.append(
                {
                    "file": new_file_path,
                    "new_file_content": new_file_content if preview else "",
                    "is_new_file": True,
                }
            )

        # Generate summary
        operation_mode = "Preview of " if preview and not apply else ""
        summary = f"{operation_mode}Extracted {total_extractions} code segments from {total_files_changed} files to {new_file_path}"

        return {
            "success": True,
            "error": "",
            "changes": changes,
            "summary": summary,
            "total_extractions": total_extractions,
            "total_files_changed": total_files_changed,
            "new_file": new_file_path,
        }

    def _move_code(
        self,
        files: List[str],
        source_file: str,
        target_file: str,
        preview: bool,
        apply: bool,
        create_backup: bool,
        start_pattern: str = "",
        end_pattern: str = "",
        line_range: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Move code from one file to another.

        Args:
            files: List of files to process
            source_file: Source file path
            target_file: Target file path
            preview: Whether to preview changes
            apply: Whether to apply changes
            create_backup: Whether to create backups
            start_pattern: Start pattern for code block
            end_pattern: End pattern for code block
            line_range: Range of lines to move (e.g., "10-20")
            **kwargs: Additional arguments

        Returns:
            Result dictionary with changes
        """
        changes = []
        source_content = ""
        target_content = ""
        moved_content = ""

        # Expand paths
        source_path = os.path.abspath(os.path.expanduser(source_file))
        target_path = os.path.abspath(os.path.expanduser(target_file))

        # Check if source file exists
        if not os.path.exists(source_path):
            return {
                "success": False,
                "error": f"Source file does not exist: {source_path}",
                "changes": [],
                "summary": "",
            }

        # Read source file
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                source_content = f.read()
                source_lines = source_content.splitlines()
        except Exception as e:
            return {
                "success": False,
                "error": f"Error reading source file: {str(e)}",
                "changes": [],
                "summary": "",
            }

        # Read target file if it exists
        target_exists = os.path.exists(target_path)
        if target_exists:
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    target_content = f.read()
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error reading target file: {str(e)}",
                    "changes": [],
                    "summary": "",
                }

        # Extract the code to move
        new_source_content = source_content

        # Method 1: Use line range
        if line_range:
            try:
                if "-" in line_range:
                    start_line, end_line = map(int, line_range.split("-"))
                else:
                    start_line = end_line = int(line_range)

                # Convert to 0-based indexing
                start_line = max(0, start_line - 1)
                end_line = min(len(source_lines) - 1, end_line - 1)

                # Extract the lines
                moved_lines = source_lines[start_line : end_line + 1]
                moved_content = "\n".join(moved_lines)

                # Remove the lines from source
                new_source_lines = (
                    source_lines[:start_line] + source_lines[end_line + 1 :]
                )
                new_source_content = "\n".join(new_source_lines)
            except ValueError:
                return {
                    "success": False,
                    "error": f"Invalid line range: {line_range}",
                    "changes": [],
                    "summary": "",
                }

        # Method 2: Use start/end patterns
        elif start_pattern and end_pattern:
            try:
                start_regex = re.compile(start_pattern, re.MULTILINE)
                end_regex = re.compile(end_pattern, re.MULTILINE)

                start_match = start_regex.search(source_content)
                if not start_match:
                    return {
                        "success": False,
                        "error": f"Start pattern not found: {start_pattern}",
                        "changes": [],
                        "summary": "",
                    }

                # Find the end pattern after the start match
                end_match = end_regex.search(source_content, start_match.end())
                if not end_match:
                    return {
                        "success": False,
                        "error": f"End pattern not found: {end_pattern}",
                        "changes": [],
                        "summary": "",
                    }

                # Extract the content between start and end (including patterns)
                start_pos = start_match.start()
                end_pos = end_match.end()
                moved_content = source_content[start_pos:end_pos]

                # Remove the content from source
                new_source_content = (
                    source_content[:start_pos] + source_content[end_pos:]
                )
            except re.error as e:
                return {
                    "success": False,
                    "error": f"Invalid regex pattern: {str(e)}",
                    "changes": [],
                    "summary": "",
                }
        else:
            return {
                "success": False,
                "error": "Must specify either line_range or both start_pattern and end_pattern",
                "changes": [],
                "summary": "",
            }

        # Generate new target content
        new_target_content = target_content
        if target_exists:
            # Append a newline if needed
            if new_target_content and not new_target_content.endswith("\n"):
                new_target_content += "\n\n"
            else:
                new_target_content += "\n"

        new_target_content += moved_content

        # Generate diffs for preview
        source_diff = self._generate_diff(
            source_path, source_content, new_source_content
        )
        target_diff = self._generate_diff(
            target_path, target_content, new_target_content
        )

        # Apply changes if requested and not just preview
        if apply and not preview:
            # Source file
            if create_backup:
                backup_path = f"{source_path}.bak"
                with open(backup_path, "w", encoding="utf-8") as f:
                    f.write(source_content)

            with open(source_path, "w", encoding="utf-8") as f:
                f.write(new_source_content)

            # Target file - ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_target_content)

        # Add changes
        changes.append(
            {
                "file": source_path,
                "diff": source_diff if preview else "",
                "is_source": True,
            }
        )

        changes.append(
            {
                "file": target_path,
                "diff": target_diff if preview else "",
                "is_target": True,
                "is_new_file": not target_exists,
            }
        )

        # Generate summary
        operation_mode = "Preview of " if preview and not apply else ""
        summary = f"{operation_mode}Moved code from {source_path} to {target_path}"

        return {
            "success": True,
            "error": "",
            "changes": changes,
            "summary": summary,
            "moved_content_size": len(moved_content),
        }

    def _transform_code(
        self,
        files: List[str],
        pattern: str,
        replacement: str,
        preview: bool,
        apply: bool,
        create_backup: bool,
        max_replacements: int = 0,
        whole_words: bool = False,
        case_sensitive: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Apply a regex transformation across multiple files.

        Args:
            files: List of files to process
            pattern: Regex pattern to match
            replacement: Replacement text (can use regex group references)
            preview: Whether to preview changes
            apply: Whether to apply changes
            create_backup: Whether to create backups
            max_replacements: Maximum replacements per file (0 for unlimited)
            whole_words: Whether to match whole words only
            case_sensitive: Whether the match is case sensitive
            **kwargs: Additional arguments

        Returns:
            Result dictionary with changes
        """
        changes = []
        total_replacements = 0
        total_files_changed = 0

        # Prepare regex pattern with options
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            if whole_words:
                pattern = r"\b" + pattern + r"\b"

            transform_regex = re.compile(pattern, flags)
        except re.error as e:
            return {
                "success": False,
                "error": f"Invalid regex pattern: {str(e)}",
                "changes": [],
                "summary": "",
            }

        # Process each file
        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Apply the transformation
                if max_replacements > 0:
                    new_content, replacements = transform_regex.subn(
                        replacement, content, max_replacements
                    )
                else:
                    new_content, replacements = transform_regex.subn(
                        replacement, content
                    )

                if replacements == 0:
                    continue

                # Generate diff for preview
                diff = self._generate_diff(file_path, content, new_content)

                # Apply changes if requested and not just preview
                if apply and not preview:
                    if create_backup:
                        backup_path = f"{file_path}.bak"
                        with open(backup_path, "w", encoding="utf-8") as f:
                            f.write(content)

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)

                changes.append(
                    {
                        "file": file_path,
                        "replacements": replacements,
                        "diff": diff if preview else "",
                    }
                )

                total_replacements += replacements
                total_files_changed += 1

            except Exception as e:
                changes.append(
                    {
                        "file": file_path,
                        "error": str(e),
                        "replacements": 0,
                        "diff": "",
                    }
                )

        # Generate summary
        pattern_display = pattern[:30] + "..." if len(pattern) > 30 else pattern
        replacement_display = (
            replacement[:30] + "..." if len(replacement) > 30 else replacement
        )
        operation_mode = "Preview of " if preview and not apply else ""
        summary = f"{operation_mode}Transform '{pattern_display}' to '{replacement_display}': {total_replacements} replacements in {total_files_changed} files"

        return {
            "success": True,
            "error": "",
            "changes": changes,
            "summary": summary,
            "total_replacements": total_replacements,
            "total_files_changed": total_files_changed,
        }

    def _generate_diff(
        self, file_path: str, old_content: str, new_content: str
    ) -> List[Dict[str, Any]]:
        """
        Generate a human-readable diff between old and new content.

        Args:
            file_path: Path to the file (for reference)
            old_content: Original content
            new_content: Modified content

        Returns:
            List of diff hunks with line numbers and changes
        """
        if old_content == new_content:
            return []

        # Split into lines
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        # Generate unified diff
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            lineterm="",
            n=3,  # Context lines
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )

        # Parse the diff into a more structured format
        structured_diff = []
        current_hunk = None

        for line in diff:
            # Skip file headers
            if line.startswith("---") or line.startswith("+++"):
                continue

            # New hunk header
            if line.startswith("@@"):
                # Add previous hunk if it exists
                if current_hunk and current_hunk["changes"]:
                    structured_diff.append(current_hunk)

                # Parse the hunk header for line numbers
                # Format: @@ -old_start,old_count +new_start,new_count @@
                header_parts = line.split("@@")[1].strip().split(" ")
                old_info = header_parts[0].strip()
                new_info = header_parts[1].strip() if len(header_parts) > 1 else ""

                current_hunk = {
                    "header": line,
                    "old_range": old_info,
                    "new_range": new_info,
                    "changes": [],
                }
            # Line from the diff
            elif current_hunk is not None:
                line_type = None
                if line.startswith("+"):
                    line_type = "add"
                elif line.startswith("-"):
                    line_type = "remove"
                elif line.startswith(" "):
                    line_type = "context"

                if line_type:
                    current_hunk["changes"].append(
                        {
                            "type": line_type,
                            "content": line[1:],  # Remove the prefix character
                        }
                    )

        # Add the last hunk
        if current_hunk and current_hunk["changes"]:
            structured_diff.append(current_hunk)

        return structured_diff
