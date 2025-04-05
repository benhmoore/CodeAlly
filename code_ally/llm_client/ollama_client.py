"""Ollama API client for function calling LLMs."""

import inspect
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

import requests

from code_ally.prompts import get_system_message
from .model_client import ModelClient

# Configure logging
logger = logging.getLogger(__name__)


class OllamaClient(ModelClient):
    """Client for interacting with Ollama API with function calling support.

    This client implements the ModelClient interface for the Ollama API,
    providing support for function calling with compatible models.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:11434",
        model_name: str = "llama3",
        temperature: float = 0.7,
        context_size: int = 32000,
        max_tokens: int = 5000,
    ):
        """Initialize the Ollama client.

        Args:
            endpoint: The Ollama API endpoint URL
            model_name: The name of the model to use
            temperature: Temperature for text generation (higher = more creative)
            context_size: Context size in tokens
            max_tokens: Maximum tokens to generate
        """
        self._endpoint = endpoint
        self._model_name = model_name
        self.temperature = temperature
        self.context_size = context_size
        self.max_tokens = max_tokens
        self.api_url = f"{endpoint}/api/chat"

    @property
    def model_name(self) -> str:
        """Get the name of the current model."""
        return self._model_name

    @model_name.setter
    def model_name(self, value: str) -> None:
        """Set the model name."""
        self._model_name = value

    @property
    def endpoint(self) -> str:
        """Get the API endpoint URL."""
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value: str) -> None:
        """Set the API endpoint URL and update the API URL."""
        self._endpoint = value
        self.api_url = f"{value}/api/chat"

    def _determine_param_type(self, annotation: Type) -> str:
        """Determine the JSON schema type from a Python type annotation.

        Args:
            annotation: The type annotation to convert

        Returns:
            The corresponding JSON schema type
        """
        # Basic types
        if annotation == str:
            return "string"
        elif annotation == int:
            return "integer"
        elif annotation == float:
            return "number"
        elif annotation == bool:
            return "boolean"
        elif annotation == list or (
            hasattr(annotation, "__origin__") and annotation.__origin__ == list
        ):
            return "array"

        # Handle Optional types
        if hasattr(annotation, "__origin__") and annotation.__origin__ == Union:
            # Check if this is an Optional (Union with None)
            args = annotation.__args__
            if type(None) in args:
                # Find the non-None type
                for arg in args:
                    if arg != type(None):
                        return self._determine_param_type(arg)

        # Default to string for unknown types
        return "string"

    def _generate_schema_from_function(self, func: Callable) -> Dict[str, Any]:
        """Generate a JSON schema for a function based on its signature and docstring.

        Args:
            func: The function to generate a schema for

        Returns:
            A JSON schema object
        """
        # Get the function signature
        sig = inspect.signature(func)

        # Get function name and docstring
        name = func.__name__
        description = inspect.getdoc(func) or ""

        # Build parameters schema
        parameters = {"type": "object", "properties": {}, "required": []}

        for param_name, param in sig.parameters.items():
            # Skip self for class methods
            if param_name == "self":
                continue

            # Default to string type
            param_type = "string"

            # Get parameter type annotation if available
            if param.annotation != inspect.Parameter.empty:
                param_type = self._determine_param_type(param.annotation)

            # Add parameter to schema
            parameters["properties"][param_name] = {
                "type": param_type,
                "description": f"Parameter {param_name}",
            }

            # Mark required parameters
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(param_name)

        # Return the function schema
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }

    def _convert_tools_to_schemas(self, tools: List[Callable]) -> List[Dict[str, Any]]:
        """Convert a list of tools (functions) to JSON schemas.

        Args:
            tools: List of function objects

        Returns:
            List of JSON schemas for the functions
        """
        return [self._generate_schema_from_function(tool) for tool in tools]

    def send(
        self,
        messages: List[Dict[str, Any]],
        functions: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[List[Callable]] = None,
        stream: bool = False,
        include_reasoning: bool = False,
    ) -> Dict[str, Any]:
        """Send a request to Ollama with messages and function definitions.

        Args:
            messages: List of message objects with role and content
            functions: List of function definitions in JSON schema format
            tools: List of Python functions to expose as tools
            stream: Whether to stream the response
            include_reasoning: Whether to include reasoning in the response

        Returns:
            The LLM's response
        """
        # Create a copy of messages to avoid modifying the original
        messages_copy = messages.copy()

        # Format the request for Ollama's API
        payload = {
            "model": self.model_name,
            "messages": messages_copy,
            "stream": stream,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.context_size,
                "num_predict": self.max_tokens,
            },
        }

        # For verbose mode, ask the model to include its reasoning
        if include_reasoning:
            # Add a system message requesting reasoning
            reasoning_request = {
                "role": "system",
                "content": get_system_message("verbose_thinking"),
            }

            # Insert before the last user message
            for i in range(len(messages_copy) - 1, -1, -1):
                if messages_copy[i]["role"] == "user":
                    messages_copy.insert(i, reasoning_request)
                    break

        # Add tool/function definitions if available
        if functions:
            payload["tools"] = functions
        elif tools:
            # Generate tool schemas from Python functions
            payload["tools"] = self._convert_tools_to_schemas(tools)

        try:
            # Log the request if in debug mode
            logger.debug(f"Sending request to Ollama: {self.api_url}")

            # Send the request
            response = requests.post(self.api_url, json=payload, timeout=240)
            response.raise_for_status()
            result = response.json()

            # Extract the message from the response
            if "message" in result:
                return result["message"]
            return result

        except requests.RequestException as e:
            # Log the error
            logger.error(f"Error communicating with Ollama: {str(e)}")

            # Handle API errors (connection issues, etc.)
            return {
                "role": "assistant",
                "content": f"Error communicating with Ollama: {str(e)}",
            }
        except json.JSONDecodeError as e:
            # Log the error
            logger.error(f"Invalid JSON response from Ollama API: {str(e)}")

            # Handle invalid JSON responses
            return {
                "role": "assistant",
                "content": f"Error: Received invalid response from Ollama API",
            }
