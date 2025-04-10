"""Prompt templates for Code Ally."""

# Define what's available from this module.
# Only expose necessary functions - import within functions to avoid circular imports
__all__ = [
    "get_system_message",
    "get_main_system_prompt",
    "generate_truncated_tree",
    "get_gitignore_patterns",
    "get_directory_tree_config",
]

# Import directly used functions
from code_ally.prompts.system_messages import get_system_message

# Use lazy loading for other imports
def get_main_system_prompt():
    """Get the main system prompt."""
    from code_ally.prompts.system_messages import get_main_system_prompt as _get_main_system_prompt
    return _get_main_system_prompt()

def generate_truncated_tree(*args, **kwargs):
    """Generate a truncated directory tree."""
    from code_ally.prompts.directory_utils import generate_truncated_tree as _generate_truncated_tree
    return _generate_truncated_tree(*args, **kwargs)

def get_gitignore_patterns(*args, **kwargs):
    """Extract patterns from .gitignore files."""
    from code_ally.prompts.directory_utils import get_gitignore_patterns as _get_gitignore_patterns
    return _get_gitignore_patterns(*args, **kwargs)

def get_directory_tree_config():
    """Get directory tree configuration."""
    from code_ally.prompts.directory_config import get_directory_tree_config as _get_directory_tree_config
    return _get_directory_tree_config()
