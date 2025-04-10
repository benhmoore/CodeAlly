"""File: directory.py

Operations for managing directories and project structure.
"""

import fnmatch
import os
import shutil
from typing import Any

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class DirectoryTool(BaseTool):
    """Tool for directory-level operations and project organization."""

    name = "directory"
    description = """Perform directory-level operations for project organization.

    <tool_call>
    {"name": "directory", "arguments": {"operation": "create", "path": "/target/path", "structure": {"src": {}, "tests": {}, "docs": {}}}}
    </tool_call>
    
    Supports:
    - Reorganizing project directories
    - Creating directory structures from templates
    - Moving/copying files with pattern matching
    - Analyzing and reporting on code organization
    """
    requires_confirmation = True

    def execute(
        self,
        operation: str,
        path: str = ".",
        dest_path: str = "",
        pattern: str = "*",
        exclude: str = "",
        recursive: bool = False,
        create_parents: bool = True,
        structure: dict[str, Any] | None = None,
        dry_run: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Execute a directory operation.

        Args:
            operation: Operation type ('create', 'move', 'copy', 'analyze', 'reorganize')
            path: Source directory path
            dest_path: Destination directory path (for move/copy)
            pattern: File/directory pattern to include
            exclude: Pattern to exclude
            recursive: Whether to operate recursively
            create_parents: Whether to create parent directories
            structure: Directory structure spec (for create/reorganize)
            dry_run: Whether to simulate the operation without making changes
            **kwargs: Additional operation-specific arguments

        Returns:
            Dict with keys:
                success: Whether the operation was successful
                error: Error message if any
                changes: List of changes made or that would be made
                analysis: Analysis results (for 'analyze' operation)
        """
        try:
            # Validate the operation type
            valid_operations = ["create", "move", "copy", "analyze", "reorganize"]
            if operation not in valid_operations:
                return {
                    "success": False,
                    "error": f"Invalid operation: {operation}. Valid operations: {', '.join(valid_operations)}",
                    "changes": [],
                    "analysis": {},
                }

            # Expand paths
            source_path = os.path.abspath(os.path.expanduser(path))
            # Check if source path is within current working directory
            cwd = os.path.abspath(os.getcwd())
            if not source_path.startswith(cwd):
                return {
                    "success": False,
                    "error": f"Access denied: The path '{path}' is outside the current working directory. "
                    f"Operations are restricted to '{cwd}' and its subdirectories.",
                    "changes": [],
                    "analysis": {},
                }

            # For operations that require a destination path
            if operation in ["move", "copy", "reorganize"]:
                if not dest_path:
                    return {
                        "success": False,
                        "error": f"Destination path is required for '{operation}' operation",
                        "changes": [],
                        "analysis": {},
                    }
                destination_path = os.path.abspath(os.path.expanduser(dest_path))
                # Check if destination path is within current working directory
                if not destination_path.startswith(cwd):
                    return {
                        "success": False,
                        "error": f"Access denied: The destination path '{dest_path}' is outside the current working directory. "
                        f"Operations are restricted to '{cwd}' and its subdirectories.",
                        "changes": [],
                        "analysis": {},
                    }
            else:
                destination_path = source_path

            # Verify source path exists for operations that require it
            if operation in ["move", "copy", "analyze"] and not os.path.exists(
                source_path,
            ):
                return {
                    "success": False,
                    "error": f"Source path does not exist: {source_path}",
                    "changes": [],
                    "analysis": {},
                }

            # Execute the appropriate operation
            if operation == "create":
                return self._create_directory_structure(
                    source_path,
                    structure,
                    create_parents,
                    dry_run,
                )
            elif operation == "move":
                return self._move_files(
                    source_path,
                    destination_path,
                    pattern,
                    exclude,
                    recursive,
                    create_parents,
                    dry_run,
                )
            elif operation == "copy":
                return self._copy_files(
                    source_path,
                    destination_path,
                    pattern,
                    exclude,
                    recursive,
                    create_parents,
                    dry_run,
                )
            elif operation == "analyze":
                return self._analyze_directory(source_path, recursive, pattern, exclude)
            elif operation == "reorganize":
                return self._reorganize_project(
                    source_path,
                    destination_path,
                    structure,
                    pattern,
                    exclude,
                    recursive,
                    dry_run,
                )
            else:
                # This should never happen due to validation above
                return {
                    "success": False,
                    "error": f"Invalid operation: {operation}",
                    "changes": [],
                    "analysis": {},
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing directory operation: {str(e)}",
                "changes": [],
                "analysis": {},
            }

    def _create_directory_structure(
        self,
        base_path: str,
        structure: dict[str, Any] | None,
        create_parents: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        """
        Create a directory structure from a specification.

        Args:
            base_path: Base directory path
            structure: Directory structure specification
            create_parents: Whether to create parent directories
            dry_run: Whether to simulate the operation

        Returns:
            Dict with operation results
        """
        changes = []

        # Check if structure is provided
        if not structure:
            return {
                "success": False,
                "error": "No directory structure specified",
                "changes": [],
                "analysis": {},
            }

        # Create base directory if it doesn't exist
        if not os.path.exists(base_path):
            if create_parents:
                changes.append(
                    {
                        "action": "create_directory",
                        "path": base_path,
                        "applied": not dry_run,
                    },
                )

                if not dry_run:
                    os.makedirs(base_path, exist_ok=True)
            else:
                return {
                    "success": False,
                    "error": f"Base path does not exist: {base_path}",
                    "changes": [],
                    "analysis": {},
                }

        # Process the structure recursively
        self._process_directory_structure(base_path, structure, changes, dry_run)

        return {
            "success": True,
            "error": "",
            "changes": changes,
            "analysis": {
                "directories_created": sum(
                    1 for c in changes if c["action"] == "create_directory"
                ),
                "files_created": sum(
                    1 for c in changes if c["action"] == "create_file"
                ),
            },
        }

    def _process_directory_structure(
        self,
        current_path: str,
        structure: dict[str, Any],
        changes: list[dict[str, Any]],
        dry_run: bool,
    ) -> None:
        """
        Process a directory structure specification recursively.

        Args:
            current_path: Current directory path
            structure: Structure specification for this level
            changes: List to collect changes
            dry_run: Whether to simulate the operation
        """
        for name, value in structure.items():
            item_path = os.path.join(current_path, name)

            # Handle special file content notation
            if isinstance(value, str) and name.endswith(":content"):
                # Extract the real file name without the ":content" suffix
                real_name = name[:-8]
                file_path = os.path.join(current_path, real_name)

                changes.append(
                    {
                        "action": "create_file",
                        "path": file_path,
                        "content_size": len(value),
                        "applied": not dry_run,
                    },
                )

                if not dry_run:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(value)

            # Handle directory
            elif isinstance(value, dict):
                changes.append(
                    {
                        "action": "create_directory",
                        "path": item_path,
                        "applied": not dry_run,
                    },
                )

                if not dry_run:
                    os.makedirs(item_path, exist_ok=True)

                # Process subdirectory
                self._process_directory_structure(item_path, value, changes, dry_run)

            # Handle file (empty or with simple content)
            elif isinstance(value, str) or value is None:
                content = value or ""

                changes.append(
                    {
                        "action": "create_file",
                        "path": item_path,
                        "content_size": len(content),
                        "applied": not dry_run,
                    },
                )

                if not dry_run:
                    with open(item_path, "w", encoding="utf-8") as f:
                        f.write(content)

            # Handle list of files/directories
            elif isinstance(value, list):
                # Create directory first
                changes.append(
                    {
                        "action": "create_directory",
                        "path": item_path,
                        "applied": not dry_run,
                    },
                )

                if not dry_run:
                    os.makedirs(item_path, exist_ok=True)

                # Process each item in the list
                for item in value:
                    if isinstance(item, str):
                        # Simple file
                        file_path = os.path.join(item_path, item)
                        changes.append(
                            {
                                "action": "create_file",
                                "path": file_path,
                                "content_size": 0,
                                "applied": not dry_run,
                            },
                        )

                        if not dry_run:
                            with open(file_path, "w", encoding="utf-8") as f:
                                pass
                    elif isinstance(item, dict):
                        # Dictionary with a single key for filename and value for content
                        for file_name, file_content in item.items():
                            file_path = os.path.join(item_path, file_name)
                            content = file_content or ""

                            changes.append(
                                {
                                    "action": "create_file",
                                    "path": file_path,
                                    "content_size": len(content),
                                    "applied": not dry_run,
                                },
                            )

                            if not dry_run:
                                with open(file_path, "w", encoding="utf-8") as f:
                                    f.write(content)

    def _move_files(
        self,
        source_path: str,
        dest_path: str,
        pattern: str,
        exclude: str,
        recursive: bool,
        create_parents: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        """
        Move files from source to destination with pattern matching.

        Args:
            source_path: Source directory path
            dest_path: Destination directory path
            pattern: File pattern to include
            exclude: Pattern to exclude
            recursive: Whether to operate recursively
            create_parents: Whether to create parent directories
            dry_run: Whether to simulate the operation

        Returns:
            Dict with operation results
        """
        changes = []
        error = ""

        try:
            # Check if source exists
            if not os.path.exists(source_path):
                return {
                    "success": False,
                    "error": f"Source path does not exist: {source_path}",
                    "changes": [],
                    "analysis": {},
                }

            # Create destination if it doesn't exist and create_parents is True
            if not os.path.exists(dest_path):
                if create_parents:
                    changes.append(
                        {
                            "action": "create_directory",
                            "path": dest_path,
                            "applied": not dry_run,
                        },
                    )

                    if not dry_run:
                        os.makedirs(dest_path, exist_ok=True)
                else:
                    return {
                        "success": False,
                        "error": f"Destination path does not exist: {dest_path}",
                        "changes": [],
                        "analysis": {},
                    }

            # Find matching files
            matches = self._find_matching_items(
                source_path,
                pattern,
                exclude,
                recursive,
            )

            for item_path in matches:
                # Calculate relative path
                rel_path = os.path.relpath(item_path, source_path)
                target_path = os.path.join(dest_path, rel_path)

                # Create parent directories if needed
                parent_dir = os.path.dirname(target_path)
                if not os.path.exists(parent_dir):
                    changes.append(
                        {
                            "action": "create_directory",
                            "path": parent_dir,
                            "applied": not dry_run,
                        },
                    )

                    if not dry_run:
                        os.makedirs(parent_dir, exist_ok=True)

                # Record the move operation
                changes.append(
                    {
                        "action": "move",
                        "source": item_path,
                        "destination": target_path,
                        "is_directory": os.path.isdir(item_path),
                        "applied": not dry_run,
                    },
                )

                # Execute the move if not a dry run
                if not dry_run:
                    if os.path.exists(target_path):
                        if os.path.isdir(target_path) and os.path.isdir(item_path):
                            # If both source and target are directories, we'll merge them
                            # by moving the contents instead of the directory itself
                            for item in os.listdir(item_path):
                                item_source = os.path.join(item_path, item)
                                item_dest = os.path.join(target_path, item)
                                shutil.move(item_source, item_dest)
                            # Remove the source directory if now empty
                            if not os.listdir(item_path):
                                os.rmdir(item_path)
                        else:
                            # Otherwise just replace the target
                            shutil.move(item_path, target_path)
                    else:
                        shutil.move(item_path, target_path)

            return {
                "success": True,
                "error": "",
                "changes": changes,
                "analysis": {
                    "items_moved": len(changes)
                    - sum(1 for c in changes if c["action"] == "create_directory"),
                    "directories_created": sum(
                        1 for c in changes if c["action"] == "create_directory"
                    ),
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error moving files: {str(e)}",
                "changes": changes,
                "analysis": {},
            }

    def _copy_files(
        self,
        source_path: str,
        dest_path: str,
        pattern: str,
        exclude: str,
        recursive: bool,
        create_parents: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        """
        Copy files from source to destination with pattern matching.

        Args:
            source_path: Source directory path
            dest_path: Destination directory path
            pattern: File pattern to include
            exclude: Pattern to exclude
            recursive: Whether to operate recursively
            create_parents: Whether to create parent directories
            dry_run: Whether to simulate the operation

        Returns:
            Dict with operation results
        """
        changes = []
        error = ""

        try:
            # Check if source exists
            if not os.path.exists(source_path):
                return {
                    "success": False,
                    "error": f"Source path does not exist: {source_path}",
                    "changes": [],
                    "analysis": {},
                }

            # Create destination if it doesn't exist and create_parents is True
            if not os.path.exists(dest_path):
                if create_parents:
                    changes.append(
                        {
                            "action": "create_directory",
                            "path": dest_path,
                            "applied": not dry_run,
                        },
                    )

                    if not dry_run:
                        os.makedirs(dest_path, exist_ok=True)
                else:
                    return {
                        "success": False,
                        "error": f"Destination path does not exist: {dest_path}",
                        "changes": [],
                        "analysis": {},
                    }

            # Find matching files
            matches = self._find_matching_items(
                source_path,
                pattern,
                exclude,
                recursive,
            )

            for item_path in matches:
                # Calculate relative path
                rel_path = os.path.relpath(item_path, source_path)
                target_path = os.path.join(dest_path, rel_path)

                # Create parent directories if needed
                parent_dir = os.path.dirname(target_path)
                if not os.path.exists(parent_dir):
                    changes.append(
                        {
                            "action": "create_directory",
                            "path": parent_dir,
                            "applied": not dry_run,
                        },
                    )

                    if not dry_run:
                        os.makedirs(parent_dir, exist_ok=True)

                # Record the copy operation
                changes.append(
                    {
                        "action": "copy",
                        "source": item_path,
                        "destination": target_path,
                        "is_directory": os.path.isdir(item_path),
                        "applied": not dry_run,
                    },
                )

                # Execute the copy if not a dry run
                if not dry_run:
                    if os.path.isdir(item_path):
                        if os.path.exists(target_path):
                            # If target exists, copy contents
                            for item in os.listdir(item_path):
                                item_source = os.path.join(item_path, item)
                                item_dest = os.path.join(target_path, item)
                                if os.path.isdir(item_source):
                                    shutil.copytree(
                                        item_source,
                                        item_dest,
                                        dirs_exist_ok=True,
                                    )
                                else:
                                    shutil.copy2(item_source, item_dest)
                        else:
                            # Copy entire directory
                            shutil.copytree(item_path, target_path)
                    else:
                        # Copy file
                        shutil.copy2(item_path, target_path)

            return {
                "success": True,
                "error": "",
                "changes": changes,
                "analysis": {
                    "items_copied": len(changes)
                    - sum(1 for c in changes if c["action"] == "create_directory"),
                    "directories_created": sum(
                        1 for c in changes if c["action"] == "create_directory"
                    ),
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error copying files: {str(e)}",
                "changes": changes,
                "analysis": {},
            }

    def _analyze_directory(
        self,
        path: str,
        recursive: bool,
        pattern: str,
        exclude: str,
    ) -> dict[str, Any]:
        """
        Analyze a directory structure.

        Args:
            path: Directory path to analyze
            recursive: Whether to analyze recursively
            pattern: Pattern to include in analysis
            exclude: Pattern to exclude from analysis

        Returns:
            Dict with analysis results
        """
        try:
            # Check if path exists
            if not os.path.exists(path):
                return {
                    "success": False,
                    "error": f"Path does not exist: {path}",
                    "changes": [],
                    "analysis": {},
                }

            # Initialize analysis data
            analysis = {
                "path": path,
                "directories": [],
                "files": [],
                "file_types": {},
                "total_files": 0,
                "total_directories": 0,
                "total_size": 0,
                "language_stats": {},
                "file_extensions": {},
            }

            # File extension to language mapping
            extension_to_language = {
                ".py": "Python",
                ".js": "JavaScript",
                ".jsx": "JavaScript (React)",
                ".ts": "TypeScript",
                ".tsx": "TypeScript (React)",
                ".html": "HTML",
                ".css": "CSS",
                ".scss": "SCSS",
                ".sass": "SASS",
                ".less": "LESS",
                ".json": "JSON",
                ".xml": "XML",
                ".md": "Markdown",
                ".sql": "SQL",
                ".java": "Java",
                ".c": "C",
                ".cpp": "C++",
                ".h": "C/C++ Header",
                ".hpp": "C++ Header",
                ".go": "Go",
                ".rb": "Ruby",
                ".php": "PHP",
                ".rs": "Rust",
                ".swift": "Swift",
                ".kt": "Kotlin",
                ".cs": "C#",
                ".fs": "F#",
                ".sh": "Shell",
                ".bat": "Batch",
                ".ps1": "PowerShell",
            }

            # Walk the directory
            for root, dirs, files in os.walk(path):
                # Skip excluded directories
                dirs[:] = [
                    d for d in dirs if not (exclude and fnmatch.fnmatch(d, exclude))
                ]

                # Process this directory
                rel_root = os.path.relpath(root, path)
                if rel_root == ".":
                    rel_root = ""

                dir_info = {
                    "name": os.path.basename(root),
                    "path": rel_root,
                    "file_count": 0,
                    "subdir_count": len(dirs),
                    "size": 0,
                }

                # Process files in this directory
                for filename in files:
                    # Skip excluded files
                    if exclude and fnmatch.fnmatch(filename, exclude):
                        continue

                    # Skip files that don't match pattern
                    if pattern != "*" and not fnmatch.fnmatch(filename, pattern):
                        continue

                    file_path = os.path.join(root, filename)
                    rel_path = (
                        os.path.join(rel_root, filename) if rel_root else filename
                    )

                    # Get file size
                    file_size = os.path.getsize(file_path)

                    # Get file extension
                    _, ext = os.path.splitext(filename)
                    ext = ext.lower()

                    # Update stats
                    analysis["total_files"] += 1
                    analysis["total_size"] += file_size
                    dir_info["file_count"] += 1
                    dir_info["size"] += file_size

                    # Update file extension stats
                    if ext in analysis["file_extensions"]:
                        analysis["file_extensions"][ext]["count"] += 1
                        analysis["file_extensions"][ext]["size"] += file_size
                    else:
                        analysis["file_extensions"][ext] = {
                            "count": 1,
                            "size": file_size,
                        }

                    # Update language stats
                    language = extension_to_language.get(ext, "Other")
                    if language in analysis["language_stats"]:
                        analysis["language_stats"][language]["count"] += 1
                        analysis["language_stats"][language]["size"] += file_size
                    else:
                        analysis["language_stats"][language] = {
                            "count": 1,
                            "size": file_size,
                        }

                    # Add file info
                    analysis["files"].append(
                        {
                            "name": filename,
                            "path": rel_path,
                            "size": file_size,
                            "extension": ext,
                            "language": language,
                        },
                    )

                # Add directory info
                analysis["directories"].append(dir_info)
                analysis["total_directories"] += 1

                # Stop after processing the first level if not recursive
                if not recursive and root == path:
                    break

            # Process file types by grouping extensions
            for ext, stats in analysis["file_extensions"].items():
                file_type = extension_to_language.get(ext, "Other")
                if file_type in analysis["file_types"]:
                    analysis["file_types"][file_type]["count"] += stats["count"]
                    analysis["file_types"][file_type]["size"] += stats["size"]
                    analysis["file_types"][file_type]["extensions"].add(ext)
                else:
                    analysis["file_types"][file_type] = {
                        "count": stats["count"],
                        "size": stats["size"],
                        "extensions": {ext},
                    }

            # Convert sets to lists for JSON serialization
            for file_type, stats in analysis["file_types"].items():
                stats["extensions"] = list(stats["extensions"])

            return {
                "success": True,
                "error": "",
                "changes": [],
                "analysis": analysis,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error analyzing directory: {str(e)}",
                "changes": [],
                "analysis": {},
            }

    def _reorganize_project(
        self,
        source_path: str,
        dest_path: str,
        structure: dict[str, Any] | None,
        pattern: str,
        exclude: str,
        recursive: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        """
        Reorganize a project according to a new structure.

        Args:
            source_path: Source directory path
            dest_path: Destination directory path
            structure: New directory structure specification
            pattern: Pattern to include
            exclude: Pattern to exclude
            recursive: Whether to operate recursively
            dry_run: Whether to simulate the operation

        Returns:
            Dict with operation results
        """
        changes = []
        error = ""

        try:
            # Check if source exists
            if not os.path.exists(source_path):
                return {
                    "success": False,
                    "error": f"Source path does not exist: {source_path}",
                    "changes": [],
                    "analysis": {},
                }

            # Create destination if it doesn't exist
            if not os.path.exists(dest_path):
                changes.append(
                    {
                        "action": "create_directory",
                        "path": dest_path,
                        "applied": not dry_run,
                    },
                )

                if not dry_run:
                    os.makedirs(dest_path, exist_ok=True)

            # First analyze the source directory to understand its structure
            analysis_result = self._analyze_directory(
                source_path,
                recursive,
                pattern,
                exclude,
            )
            if not analysis_result["success"]:
                return analysis_result

            # Now apply the reorganization based on the structure spec
            if structure:
                # Create the target structure
                structure_result = self._create_directory_structure(
                    dest_path,
                    structure,
                    True,
                    dry_run,
                )
                if not structure_result["success"]:
                    return structure_result

                # Add structure changes to our changes list
                changes.extend(structure_result["changes"])

                # Map files from old structure to new structure
                for file_info in analysis_result["analysis"]["files"]:
                    source_file = os.path.join(source_path, file_info["path"])

                    # Determine target based on file extension or pattern
                    target_file = self._map_file_to_new_structure(
                        file_info,
                        dest_path,
                        structure,
                    )

                    if target_file:
                        changes.append(
                            {
                                "action": "copy",
                                "source": source_file,
                                "destination": target_file,
                                "is_directory": False,
                                "applied": not dry_run,
                            },
                        )

                        # Actually copy the file if not a dry run
                        if not dry_run:
                            # Ensure parent directory exists
                            parent_dir = os.path.dirname(target_file)
                            os.makedirs(parent_dir, exist_ok=True)

                            # Copy the file
                            shutil.copy2(source_file, target_file)
            else:
                # Without a structure spec, just copy everything maintaining the original structure
                for file_info in analysis_result["analysis"]["files"]:
                    source_file = os.path.join(source_path, file_info["path"])
                    target_file = os.path.join(dest_path, file_info["path"])

                    # Ensure parent directory exists
                    parent_dir = os.path.dirname(target_file)
                    if not os.path.exists(parent_dir):
                        changes.append(
                            {
                                "action": "create_directory",
                                "path": parent_dir,
                                "applied": not dry_run,
                            },
                        )

                        if not dry_run:
                            os.makedirs(parent_dir, exist_ok=True)

                    changes.append(
                        {
                            "action": "copy",
                            "source": source_file,
                            "destination": target_file,
                            "is_directory": False,
                            "applied": not dry_run,
                        },
                    )

                    # Actually copy the file if not a dry run
                    if not dry_run:
                        shutil.copy2(source_file, target_file)

            return {
                "success": True,
                "error": "",
                "changes": changes,
                "analysis": {
                    "items_reorganized": len(changes)
                    - sum(1 for c in changes if c["action"] == "create_directory"),
                    "directories_created": sum(
                        1 for c in changes if c["action"] == "create_directory"
                    ),
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error reorganizing project: {str(e)}",
                "changes": changes,
                "analysis": {},
            }

    def _find_matching_items(
        self,
        directory: str,
        pattern: str,
        exclude: str,
        recursive: bool,
    ) -> list[str]:
        """
        Find items (files and directories) matching the given patterns.

        Args:
            directory: Directory to search in
            pattern: Pattern to match
            exclude: Pattern to exclude
            recursive: Whether to search recursively

        Returns:
            List of matching item paths
        """
        matching_items = []

        if recursive:
            # For recursive search, we need to walk the directory tree
            for root, dirs, files in os.walk(directory):
                # Process directories
                for dirname in dirs:
                    if exclude and fnmatch.fnmatch(dirname, exclude):
                        continue

                    if fnmatch.fnmatch(dirname, pattern):
                        matching_items.append(os.path.join(root, dirname))

                # Process files
                for filename in files:
                    if exclude and fnmatch.fnmatch(filename, exclude):
                        continue

                    if fnmatch.fnmatch(filename, pattern):
                        matching_items.append(os.path.join(root, filename))
        else:
            # Non-recursive search, just look in the base directory
            for item in os.listdir(directory):
                if exclude and fnmatch.fnmatch(item, exclude):
                    continue

                if fnmatch.fnmatch(item, pattern):
                    matching_items.append(os.path.join(directory, item))

        return matching_items

    def _map_file_to_new_structure(
        self,
        file_info: dict[str, Any],
        base_path: str,
        structure: dict[str, Any],
    ) -> str | None:
        """
        Map a file from the old structure to the new structure.

        Args:
            file_info: Information about the file
            base_path: Base path of the new structure
            structure: New structure specification

        Returns:
            Path in the new structure, or None if unmapped
        """
        # Simple strategies for mapping files:

        # 1. By extension to conventional directories
        ext = file_info["extension"]
        filename = os.path.basename(file_info["path"])

        # Common mappings by extension
        if ext == ".py":
            # Python files go to src or lib
            if "src" in structure:
                return os.path.join(base_path, "src", filename)
            elif "lib" in structure:
                return os.path.join(base_path, "lib", filename)

        elif ext in [".js", ".jsx", ".ts", ".tsx"]:
            # JavaScript/TypeScript files go to src or assets/js
            if "src" in structure:
                if ext.endswith("x"):  # JSX/TSX files
                    if "components" in structure["src"]:
                        return os.path.join(base_path, "src", "components", filename)
                    else:
                        return os.path.join(base_path, "src", filename)
                else:
                    return os.path.join(base_path, "src", filename)
            elif "assets" in structure and "js" in structure["assets"]:
                return os.path.join(base_path, "assets", "js", filename)

        elif ext in [".html", ".htm"]:
            # HTML files go to templates or public
            if "templates" in structure:
                return os.path.join(base_path, "templates", filename)
            elif "public" in structure:
                return os.path.join(base_path, "public", filename)

        elif ext in [".css", ".scss", ".sass", ".less"]:
            # CSS files go to styles or assets/css
            if "styles" in structure:
                return os.path.join(base_path, "styles", filename)
            elif "assets" in structure and "css" in structure["assets"]:
                return os.path.join(base_path, "assets", "css", filename)

        elif ext in [".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico"]:
            # Image files go to images or assets/images
            if "images" in structure:
                return os.path.join(base_path, "images", filename)
            elif "assets" in structure and "images" in structure["assets"]:
                return os.path.join(base_path, "assets", "images", filename)

        elif ext in [".json", ".yaml", ".yml", ".toml", ".ini", ".xml"]:
            # Config files go to config
            if "config" in structure:
                return os.path.join(base_path, "config", filename)

        elif ext in [".md", ".txt", ".rst"]:
            # Documentation files go to docs
            if "docs" in structure:
                return os.path.join(base_path, "docs", filename)

        elif ext in [".test.js", ".spec.js", ".test.py", ".spec.py"]:
            # Test files go to tests
            if "tests" in structure:
                return os.path.join(base_path, "tests", filename)
            elif "test" in structure:
                return os.path.join(base_path, "test", filename)

        # 2. Check if there's a direct path match
        for struct_path, struct_value in self._flatten_structure(structure).items():
            if file_info["path"] == struct_path or filename == struct_path:
                # Direct match
                return os.path.join(base_path, struct_path)

        # 3. Default to keeping the file at the same relative path
        relative_path = file_info["path"]
        return os.path.join(base_path, relative_path)

    def _flatten_structure(
        self,
        structure: dict[str, Any],
        prefix: str = "",
    ) -> dict[str, Any]:
        """
        Flatten a nested directory structure into paths.

        Args:
            structure: Directory structure
            prefix: Path prefix for recursion

        Returns:
            Dict mapping paths to values
        """
        result = {}

        for key, value in structure.items():
            path = os.path.join(prefix, key) if prefix else key

            if isinstance(value, dict):
                # Recursively flatten nested dictionaries
                nested = self._flatten_structure(value, path)
                result.update(nested)
            else:
                # Add leaf nodes
                result[path] = value

        return result
