"""Tool registry for Code Ally.

This module provides a centralized registry for all tools available in the system.
It ensures that tools are automatically registered and can be easily accessed.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, cast

from code_ally.tools.base import BaseTool

# Configure logging
logger = logging.getLogger(__name__)

# Type variable for decorator type checking
T = TypeVar("T", bound=Type[BaseTool])


class ToolRegistry:
    """Registry for all available tools in the system.

    This class is implemented as a singleton to ensure that all tools
    are registered in a single registry regardless of where they are imported.

    Attributes:
        _instance: The singleton instance
        _tools: Dictionary of registered tool classes keyed by tool name
    """

    _instance = None
    _tools: Dict[str, Type[BaseTool]] = {}

    def __new__(cls) -> "ToolRegistry":
        """Create a singleton instance.

        Returns:
            The singleton ToolRegistry instance
        """
        if cls._instance is None:
            logger.debug("Creating new ToolRegistry singleton instance")
            cls._instance = super(ToolRegistry, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, tool_class: T) -> T:
        """Register a tool class.

        Args:
            tool_class: The tool class to register

        Returns:
            The registered tool class (for decorator use)

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        if not hasattr(tool_class, "name") or not tool_class.name:
            raise ValueError(f"Tool class {tool_class.__name__} has no name")

        tool_name = tool_class.name

        # Check if this name is already registered
        if tool_name in cls._tools:
            # If it's the same class, just return it
            if cls._tools[tool_name] == tool_class:
                logger.debug(f"Tool {tool_name} already registered")
                return tool_class

            # Otherwise, this is a conflict
            raise ValueError(
                f"Tool name '{tool_name}' is already registered for {cls._tools[tool_name].__name__}"
            )

        logger.debug(f"Registering tool: {tool_name} ({tool_class.__name__})")
        cls._tools[tool_name] = tool_class
        return tool_class

    @classmethod
    def get_tool_classes(cls) -> Dict[str, Type[BaseTool]]:
        """Get all registered tool classes.

        Returns:
            Dictionary of tool classes by name
        """
        return cls._tools.copy()

    @classmethod
    def get_tool_instances(cls) -> List[BaseTool]:
        """Create instances of all registered tools.

        Returns:
            List of tool instances
        """
        instances = []

        for name, tool_class in cls._tools.items():
            try:
                instances.append(tool_class())
                logger.debug(f"Created instance of tool: {name}")
            except Exception as e:
                logger.error(f"Error creating instance of tool {name}: {str(e)}")
                # Continue with other tools instead of failing completely

        return instances

    @classmethod
    def get_tool_by_name(cls, name: str) -> Optional[Type[BaseTool]]:
        """Get a specific tool class by name.

        Args:
            name: The name of the tool to get

        Returns:
            The tool class, or None if no tool with that name is registered
        """
        return cls._tools.get(name)

    @classmethod
    def get_tools_for_prompt(cls) -> str:
        """Get formatted tool list for the system prompt.

        Returns:
            Formatted string listing all tools
        """
        if not cls._tools:
            logger.warning("No tools registered when generating prompt")
            return "No tools available"

        tools_text = []
        for i, (name, tool_class) in enumerate(sorted(cls._tools.items()), 1):
            # Extract the tool's display name
            display_name = tool_class.name.lower()

            # Get the description from the class attribute
            description = tool_class.description or "No description available"

            # Format the tool entry
            tools_text.append(f"{i}. {display_name} - {description}")

        return "\n".join(tools_text)


def register_tool(cls: T) -> T:
    """Decorator to register a tool class.

    Example:
        @register_tool
        class MyTool(BaseTool):
            name = "my_tool"
            description = "My tool description"
            requires_confirmation = False

            def execute(self, **kwargs):
                # Implementation...

    Args:
        cls: The tool class to register

    Returns:
        The registered tool class
    """
    return ToolRegistry.register(cls)
