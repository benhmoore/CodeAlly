"""
Configuration interface for directory tree generation.

This module provides a clean interface between the config system and the directory tree
generator, helping to avoid circular imports.
"""

from typing import Any, Dict, List, Optional

# Default configuration values - must match those in config.py
DEFAULT_DIR_TREE_ENABLED = True
DEFAULT_DIR_TREE_MAX_DEPTH = 3
DEFAULT_DIR_TREE_MAX_FILES = 100


def get_directory_tree_config() -> Dict[str, Any]:
    """
    Get the directory tree configuration from the global config.

    Returns:
        Dictionary with configuration values for the directory tree generator
    """
    try:
        # Import here to avoid circular imports
        from code_ally.config import get_config_value

        return {
            "enabled": get_config_value("dir_tree_enable", DEFAULT_DIR_TREE_ENABLED),
            "max_depth": get_config_value(
                "dir_tree_max_depth", DEFAULT_DIR_TREE_MAX_DEPTH
            ),
            "max_files": get_config_value(
                "dir_tree_max_files", DEFAULT_DIR_TREE_MAX_FILES
            ),
        }
    except ImportError:
        # If import fails (during initial loading), return defaults
        return {
            "enabled": DEFAULT_DIR_TREE_ENABLED,
            "max_depth": DEFAULT_DIR_TREE_MAX_DEPTH,
            "max_files": DEFAULT_DIR_TREE_MAX_FILES,
        }
