"""File: __init__.py
Code Ally - Local LLM-powered pair programming assistant.

This package provides a set of tools for using local LLMs to assist with
coding tasks through natural language, while keeping all data on your machine.
"""

# Define package metadata
__version__ = "0.3.10"
__author__ = "Ben H Moore"
__email__ = "ben@benhmoore.com"

# Import common configuration functions for easier access
from code_ally.config import load_config, reset_config, save_config
