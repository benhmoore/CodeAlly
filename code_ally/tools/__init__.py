"""Tool implementations for the Code Ally agent.

This package provides the tools that the agent can use to interact with
the system, such as file operations, shell commands, and more.
"""

# Base classes and registry
from .base import BaseTool

# Core tools
from .bash import BashTool
from .edit import FileEditTool
from .glob import GlobTool
from .grep import GrepTool
from .ls import LSTool
from .math_tool import MathTool
from .read import FileReadTool
from .registry import ToolRegistry, register_tool
from .write import FileWriteTool

# Public API
__all__ = [
    # Base classes and infrastructure
    "BaseTool",
    "ToolRegistry",
    "register_tool",
    # Core tools
    "BashTool",
    "FileReadTool",
    "FileWriteTool",
    "FileEditTool",
    "GlobTool",
    "GrepTool",
    "LSTool",
    "MathTool",
]

# Create registry instance to ensure all tools are registered
registry = ToolRegistry()
