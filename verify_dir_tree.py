#!/usr/bin/env python3
"""
Simple script to verify the directory tree functionality.
"""

import os

from code_ally.prompts.directory_config import get_directory_tree_config
from code_ally.prompts.directory_utils import (
    generate_truncated_tree,
    get_gitignore_patterns,
)


def main():
    """Verify directory tree generation."""
    print("Directory Tree Test Script")
    print("-" * 50)

    # Get current directory
    current_dir = os.getcwd()
    print(f"Current directory: {current_dir}")

    # Get .gitignore patterns
    gitignore_patterns = get_gitignore_patterns(current_dir)
    print(f"Found {len(gitignore_patterns)} .gitignore patterns")

    # Get configuration
    config = get_directory_tree_config()
    print(f"Configuration: {config}")

    # Generate tree
    tree = generate_truncated_tree(
        current_dir,
        max_depth=config["max_depth"],
        max_files=config["max_files"],
        exclude_patterns=gitignore_patterns,
    )

    # Print tree
    print("\nDirectory Tree:")
    print(tree)

    return 0


if __name__ == "__main__":
    main()
