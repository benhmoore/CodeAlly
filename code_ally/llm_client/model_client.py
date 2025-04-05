"""Base model client interfaces.

This module provides a standardized interface for interacting with different
language model backends through a common API.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)


class ModelClient(ABC):
    """Base class for LLM clients.

    This abstract class defines the interface that all model clients must implement.
    It provides a standard way to interact with different LLM backends.
    """

    @abstractmethod
    def send(
        self,
        messages: List[Dict[str, Any]],
        functions: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[List[Callable]] = None,
        stream: bool = False,
        include_reasoning: bool = False,
    ) -> Dict[str, Any]:
        """Send a request to the LLM with messages and function definitions.

        Args:
            messages: List of message objects with role and content
            functions: List of function definitions in JSON schema format
            tools: List of Python functions to expose as tools
            stream: Whether to stream the response
            include_reasoning: Whether to include reasoning in the response

        Returns:
            The LLM's response as a dictionary with at least 'role' and 'content' keys
        """
        # Abstract method must be implemented by subclasses
        raise NotImplementedError("Subclasses must implement the send method")

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the name of the current model."""
        # Abstract property must be implemented by subclasses
        raise NotImplementedError("Subclasses must implement the model_name property")

    @property
    @abstractmethod
    def endpoint(self) -> str:
        """Get the API endpoint URL."""
        # Abstract property must be implemented by subclasses
        raise NotImplementedError("Subclasses must implement the endpoint property")
