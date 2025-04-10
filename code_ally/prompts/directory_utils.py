"""
Utilities for directory tree generation and management.

This module provides functionality for generating truncated directory trees and
other directory-related utilities for use in system prompts and context building.
"""

import os
import fnmatch
from typing import List, Set, Dict, Any, Optional, Tuple


def generate_truncated_tree(
    root_path: str,
    max_depth: int = 3,
    max_files: int = 100,
    exclude_patterns: Optional[List[str]] = None,
    indent_char: str = "  ",
) -> str:
    """
    Generate a truncated directory tree with limited depth and file count.
    
    Args:
        root_path: The root directory to start the tree from
        max_depth: Maximum directory depth to traverse (default: 3)
        max_files: Maximum number of files to include (default: 100)
        exclude_patterns: List of glob patterns to exclude (e.g., ["*.pyc", "__pycache__"])
        indent_char: Character(s) used for indentation (default: two spaces)
        
    Returns:
        A string representation of the directory tree
    """
    # Default patterns to exclude
    default_excludes = [
        "*.pyc", "__pycache__", "*.git", ".git", ".github", ".gitattributes",
        ".DS_Store", "*.egg-info", "*.venv", ".venv", "venv", "env", 
        "node_modules", "build", "dist", ".idea", ".vscode", ".pytest_cache",
        "*.pyo", "*.so", "*.dylib", "*.dll", "*.exe", "*.o", "*.a", "*.lib",
        "*.zip", "*.tar.gz", "*.tgz", "*.rar", "*.jar", "*.war", "*.ear",
        "coverage", ".coverage", "htmlcov", ".nyc_output", "*.log", "logs"
    ]
    
    # Combine default and user-provided patterns
    exclude_patterns = (exclude_patterns or []) + default_excludes
    
    # Initialize counters and output
    file_count = 0
    output_lines = [f"- {os.path.basename(root_path)}/"]
    
    def should_exclude(path: str) -> bool:
        """Check if a path should be excluded based on patterns."""
        basename = os.path.basename(path)
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(basename, pattern):
                return True
        return False
    
    def walk_directory(
        current_path: str, 
        current_depth: int, 
        prefix: str
    ) -> Tuple[int, bool]:
        """
        Walk through directory recursively, adding entries to output_lines.
        
        Args:
            current_path: Current directory path
            current_depth: Current depth in the tree
            prefix: Prefix string for the current level
            
        Returns:
            Tuple of (current file count, whether to continue)
        """
        nonlocal file_count, output_lines
        
        if current_depth > max_depth:
            output_lines.append(f"{prefix}{indent_char}...")
            return file_count, False
            
        if should_exclude(current_path):
            return file_count, True
            
        try:
            # Get all entries in the directory
            entries = sorted(os.listdir(current_path))
            dirs = []
            files = []
            
            # Separate into files and directories
            for entry in entries:
                path = os.path.join(current_path, entry)
                if should_exclude(path):
                    continue
                    
                if os.path.isdir(path):
                    dirs.append(entry)
                else:
                    files.append(entry)
            
            # Process directories first
            for dirname in dirs:
                dir_path = os.path.join(current_path, dirname)
                output_lines.append(f"{prefix}{indent_char}- {dirname}/")
                
                # Recursively process subdirectory
                file_count, should_continue = walk_directory(
                    dir_path, 
                    current_depth + 1, 
                    f"{prefix}{indent_char}"
                )
                
                if not should_continue or file_count >= max_files:
                    return file_count, False
            
            # Then process files
            for filename in files:
                file_count += 1
                output_lines.append(f"{prefix}{indent_char}- {filename}")
                
                if file_count >= max_files:
                    output_lines.append(f"{prefix}{indent_char}...")
                    return file_count, False
                    
            return file_count, True
            
        except (PermissionError, OSError):
            output_lines.append(f"{prefix}{indent_char}[Error accessing directory]")
            return file_count, True
    
    # Start walking from the root
    walk_directory(root_path, 1, "")
    
    if file_count >= max_files:
        output_lines.append("... (truncated due to file limit)")
        
    return "\n".join(output_lines)


def get_gitignore_patterns(root_path: str) -> List[str]:
    """
    Extract patterns from .gitignore files in the given directory.
    
    Args:
        root_path: The root directory to search for .gitignore files
        
    Returns:
        List of gitignore patterns
    """
    patterns = []
    gitignore_path = os.path.join(root_path, ".gitignore")
    
    if os.path.exists(gitignore_path) and os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('#'):
                        # Convert .gitignore pattern to fnmatch pattern
                        if line.startswith('/'):
                            line = line[1:]  # Remove leading slash
                        if line.endswith('/'):
                            line = line[:-1] + '*'  # Convert directory pattern
                        patterns.append(line)
        except (IOError, UnicodeDecodeError):
            pass
            
    return patterns