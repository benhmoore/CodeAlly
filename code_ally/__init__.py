"""Code Ally - Local LLM-powered pair programming assistant.

This package provides a set of tools for using local LLMs to assist with
coding tasks through natural language, while keeping all data on your machine.
"""

__version__ = "0.1.0"
__author__ = "Code Ally Team"
__email__ = "info@example.com"

# Import common configuration functions for easier access
from code_ally.config import load_config, reset_config, save_config

# Note: We don't import Agent directly to avoid circular imports
# Users should use: from code_ally.agent import Agent
