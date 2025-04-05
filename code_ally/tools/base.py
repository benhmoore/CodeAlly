"""Base classes for tool implementations.

This module provides the base class for all tools in the Code Ally system.
Tools are the primary way for the agent to interact with the environment.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, Optional


class BaseTool(ABC):
    """Base class for all tools.

    Each tool must define:
    - name: The unique name of the tool (used in function calling)
    - description: A clear description of what the tool does
    - requires_confirmation: Whether user confirmation is required before execution
    - execute(): Method to perform the tool's action

    Tool implementations should inherit from this class and implement
    the execute method with appropriate typing.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    requires_confirmation: ClassVar[bool]

    def __init__(self) -> None:
        """Initialize the tool.

        Validates that required class variables are defined.
        """
        # Validate that required class variables are defined
        if not hasattr(self.__class__, "name") or not self.__class__.name:
            raise ValueError(
                f"{self.__class__.__name__} must define a 'name' class variable"
            )

        if not hasattr(self.__class__, "description") or not self.__class__.description:
            raise ValueError(
                f"{self.__class__.__name__} must define a 'description' class variable"
            )

        if not hasattr(self.__class__, "requires_confirmation"):
            raise ValueError(
                f"{self.__class__.__name__} must define a 'requires_confirmation' class variable"
            )

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with the given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            A dictionary containing at least:
            - success: Whether the tool execution succeeded
            - error: Error message if execution failed, empty string otherwise

            Additional key-value pairs depend on the specific tool.
        """
        # Abstract method must be implemented by subclasses
        raise NotImplementedError("Subclasses must implement the execute method")

    def _format_error_response(self, error_message: str) -> Dict[str, Any]:
        """Format a standard error response.

        Args:
            error_message: The error message

        Returns:
            A formatted error response dictionary
        """
        return {"success": False, "error": error_message}

    def _format_success_response(self, **kwargs) -> Dict[str, Any]:
        """Format a standard success response.

        Args:
            **kwargs: Additional key-value pairs for the response

        Returns:
            A formatted success response dictionary
        """
        response = {"success": True, "error": ""}
        response.update(kwargs)
        return response
