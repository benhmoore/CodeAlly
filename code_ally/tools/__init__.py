"""Tool implementations for the Code Ally agent.

This package provides the tools that the agent can use to interact with
the system, such as file operations, shell commands, and more.
"""

# Base classes and registry
from .base import BaseTool

# Core tools
from .bash import BashTool
from .batch import BatchOperationTool
from .code import CodeStructureAnalyzerTool
from .directory import DirectoryTool
from .edit import FileEditTool
from .glob import GlobTool
from .grep import GrepTool
from .plan import TaskPlanTool
from .read import FileReadTool
from .refactor import RefactorTool
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
    "CodeStructureAnalyzerTool",
    "BatchOperationTool",
    "DirectoryTool",
    "RefactorTool",
    "TaskPlanTool",
]

# Create registry instance to ensure all tools are registered
registry = ToolRegistry()
