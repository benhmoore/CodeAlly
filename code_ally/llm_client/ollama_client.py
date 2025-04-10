"""Ollama API client for function calling LLMs."""

import json
import logging
import re
import signal
import time
from collections.abc import Callable
from types import FrameType  # Import FrameType from the correct module
from typing import Any, NoReturn, Union

import requests

from code_ally.config import ConfigManager
from code_ally.prompts import get_system_message

from .model_client import ModelClient

# Configure logging
logger = logging.getLogger(__name__)


class OllamaClient(ModelClient):
    """Client for interacting with Ollama API with function calling support."""

    def __init__(
        self,
        endpoint: str = "http://localhost:11434",
        model_name: str = "llama3",
        temperature: float = 0.3,
        context_size: int = 16000,
        max_tokens: int = 5000,
        keep_alive: int | None = None,
    ) -> None:
        """Initialize the Ollama client."""
        self._endpoint = endpoint
        self._model_name = model_name
        self.temperature = temperature
        self.context_size = context_size
        self.max_tokens = max_tokens
        self.keep_alive = keep_alive
        self.api_url = f"{endpoint}/api/chat"
        self.is_qwen_model = "qwen" in model_name.lower()

        # Load configuration for model-specific settings
        self.config = ConfigManager.get_instance().get_config()

        # State for interruption handling
        self.current_session = None
        self.interrupted = False

    @property
    def model_name(self) -> str:
        """Get the name of the current model."""
        return self._model_name

    @model_name.setter
    def model_name(self, value: str) -> None:
        """Set the model name."""
        self._model_name = value
        self.is_qwen_model = "qwen" in value.lower()

    @property
    def endpoint(self) -> str:
        """Get the API endpoint URL."""
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value: str) -> None:
        """Set the API endpoint URL and update the API URL."""
        self._endpoint = value
        self.api_url = f"{value}/api/chat"

    def _determine_param_type(self, annotation: type) -> str:
        """Determine the JSON schema type from a Python type annotation."""
        # Basic types
        if annotation is str:
            return "string"
        elif annotation is int:
            return "integer"
        elif annotation is float:
            return "number"
        elif annotation is bool:
            return "boolean"
        elif annotation is list or (
            hasattr(annotation, "__origin__") and annotation.__origin__ is list
        ):
            return "array"

        # Handle Optional types
        if hasattr(annotation, "__origin__") and annotation.__origin__ == Union:
            # Check if this is an Optional (Union with None)
            args = annotation.__args__
            if type(None) in args:
                # Find the non-None type
                for arg in args:
                    if arg is not type(None):
                        return self._determine_param_type(arg)

        # Default to string for unknown types
        return "string"

    def _generate_schema_from_function(self, func: Callable) -> dict[str, Any]:
        """Generate a JSON schema for a function based on its signature and docstring."""
        # [Function body remains unchanged]

    def _convert_tools_to_schemas(self, tools: list[Callable]) -> list[dict[str, Any]]:
        """Convert a list of tools (functions) to JSON schemas."""
        return [self._generate_schema_from_function(tool) for tool in tools]

    def _get_qwen_template_options(
        self,
        messages: list[dict[str, Any]],
        tools: list[Callable] | None = None,
    ) -> dict[str, Any]:
        """Generate Qwen-specific template options for function calling.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tool functions

        Returns:
            Dictionary with template options for Qwen models
        """
        if not self.is_qwen_model:
            return {}

        # Get configurable settings with defaults
        qwen_template = self.config.get("qwen_template", "qwen2.5_function_calling")
        enable_parallel = self.config.get("qwen_parallel_calls", True)
        use_chinese = self.config.get("qwen_chinese", False)

        # Only check messages for parallel keyword if not explicitly configured
        if not self.config.get("qwen_parallel_calls_explicit", False):
            for msg in messages:
                if (
                    msg.get("role") == "system"
                    and "parallel" in msg.get("content", "").lower()
                ):
                    enable_parallel = True
                    break

        # Only try to detect language if not explicitly configured
        if not self.config.get("qwen_chinese_explicit", False):
            for msg in messages:
                if (
                    msg.get("role") in ["system", "user"]
                    and msg.get("content")
                    and any(
                        "\u4e00" <= char <= "\u9fff" for char in msg.get("content", "")
                    )
                ):
                    use_chinese = True
                    break

        logger.debug(
            f"Using Qwen template options: {qwen_template}, parallel={enable_parallel}, chinese={use_chinese}",
        )

        return {
            "template": qwen_template,
            "template_params": {
                "parallel_calls": enable_parallel,
                "chinese": use_chinese,
            },
        }

    def _normalize_tool_calls_in_message(self, message: dict[str, Any]) -> None:
        """Normalize tool calls in a message to ensure consistent format."""
        # First, check if tool_calls is already properly formatted
        if "tool_calls" in message and message["tool_calls"]:
            try:
                self._standardize_existing_tool_calls(message)
                return
            except Exception as e:
                logger.warning(f"Error standardizing existing tool calls: {e}")
                # Continue with extraction as fallback

        # Check for function_call (legacy format)
        if (
            "function_call" in message
            and message["function_call"]
            and not message.get("tool_calls")
        ):
            try:
                self._convert_function_call_to_tool_calls(message)
                return
            except Exception as e:
                logger.warning(f"Error converting function_call to tool_calls: {e}")

        # Only attempt regex extraction if no existing tool calls were found
        if (
            not message.get("tool_calls")
            and "content" in message
            and message["content"]
        ):
            self._extract_tool_calls_from_text(message)

    def _standardize_existing_tool_calls(self, message: dict[str, Any]) -> None:
        """Standardize tool_calls that already exist in the message."""
        normalized_calls = []
        for call in message["tool_calls"]:
            if "function" not in call and "name" in call:
                # Convert simplified format to standard format
                normalized_calls.append(
                    {
                        "id": call.get(
                            "id",
                            f"normalized-{int(time.time())}-{len(normalized_calls)}",
                        ),
                        "type": "function",
                        "function": {
                            "name": call.get("name"),
                            "arguments": call.get("arguments", {}),
                        },
                    },
                )
            else:
                normalized_calls.append(call)
        message["tool_calls"] = normalized_calls

    def _convert_function_call_to_tool_calls(self, message: dict[str, Any]) -> None:
        """Convert legacy function_call format to tool_calls format."""
        message["tool_calls"] = [
            {
                "id": f"function-{int(time.time())}",
                "type": "function",
                "function": message["function_call"],
            },
        ]

    def _extract_tool_calls_from_text(self, message: dict[str, Any]) -> None:
        """Extract tool calls from text content as a fallback."""
        content = message["content"]
        tool_calls = []

        # Common tool call patterns in text
        tool_call_patterns = [
            r"<tool_call>\s*({.*?})\s*</tool_call>",  # Hermes format
            r"✿FUNCTION✿:\s*(.*?)\s*\n✿ARGS✿:\s*(.*?)(?:\n✿|$)",  # Qwen format
            r"Action:\s*(.*?)\nAction Input:\s*(.*?)(?:\n|$)",  # ReAct format
        ]

        for pattern in tool_call_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                logger.warning(
                    f"Using regex fallback to extract tool calls with pattern: {pattern}",
                )
                for match in matches:
                    try:
                        if isinstance(match, tuple):
                            # ReAct or Qwen format
                            function_name = match[0].strip()
                            arguments = match[1].strip()
                            try:
                                # Try parsing as JSON
                                arg_obj = json.loads(arguments)
                            except json.JSONDecodeError:
                                # Use as string if not valid JSON
                                arg_obj = arguments

                            tool_calls.append(
                                {
                                    "id": f"extracted-{int(time.time())}-{len(tool_calls)}",
                                    "type": "function",
                                    "function": {
                                        "name": function_name,
                                        "arguments": (
                                            arg_obj
                                            if isinstance(arg_obj, dict)
                                            else arguments
                                        ),
                                    },
                                },
                            )
                        else:
                            # Hermes format - single JSON string
                            tool_json = json.loads(match)
                            tool_calls.append(
                                {
                                    "id": f"extracted-{int(time.time())}-{len(tool_calls)}",
                                    "type": "function",
                                    "function": {
                                        "name": tool_json.get("name", ""),
                                        "arguments": tool_json.get("arguments", {}),
                                    },
                                },
                            )
                    except Exception as e:
                        logger.warning(f"Error parsing tool call from text: {e}")

        # If we found tool calls in text but none are in the message structure
        if tool_calls and not message.get("tool_calls"):
            message["tool_calls"] = tool_calls
            # Clean up the content if we extracted tool calls
            for pattern in tool_call_patterns:
                content = re.sub(pattern, "", content, flags=re.DOTALL)
            message["content"] = content.strip()

    def _extract_tool_response(self, content: str) -> str:
        """Extract the actual tool response from content with tags."""
        # First try to extract from tool_response tags
        tool_response_pattern = r"<tool_response>(.*?)</tool_response>"
        tool_matches = re.findall(tool_response_pattern, content, re.DOTALL)

        if tool_matches:
            # Use the first match as the tool response
            response_content = tool_matches[0].strip()

            # Try to parse as JSON
            try:
                response_json = json.loads(response_content)
                return response_json
            except json.JSONDecodeError:
                # Return as is if not valid JSON
                return response_content

        # Remove any tags that might be present
        cleaned_content = content
        patterns_to_remove = [
            r"<tool_response>.*?</tool_response>",
            r"<search_reminders>.*?</search_reminders>",
            r"<automated_reminder_from_anthropic>.*?</automated_reminder_from_anthropic>",
        ]

        for pattern in patterns_to_remove:
            cleaned_content = re.sub(pattern, "", cleaned_content, flags=re.DOTALL)

        return cleaned_content.strip()

    def send(
        self,
        messages: list[dict[str, Any]],
        functions: list[dict[str, Any]] | None = None,
        tools: list[Callable] | None = None,
        stream: bool = False,
        include_reasoning: bool = False,
    ) -> dict[str, Any] | requests.Response:
        """Send a request to Ollama with messages and function definitions."""
        messages_copy = messages.copy()
        payload = self._prepare_payload(
            messages_copy,
            functions,
            tools,
            stream,
            include_reasoning,
        )

        # Reset interruption flag before starting new request
        self.interrupted = False

        try:
            # Set up keyboard interrupt handler for this request
            original_sigint_handler = signal.getsignal(signal.SIGINT)

            def sigint_handler(
                sig: int, frame: FrameType,
            ) -> NoReturn:  # Use FrameType from types
                logger.warning(
                    "SIGINT received during request. Interrupting Ollama request.",
                )
                self.interrupted = True

                # Close current session if it exists
                if self.current_session:
                    try:
                        logger.debug("Attempting to close session")
                        self.current_session.close()
                    except Exception as e:
                        logger.error(f"Error closing session: {e}")

                # Restore original handler for future handling
                signal.signal(signal.SIGINT, original_sigint_handler)

                # Raise KeyboardInterrupt to propagate upward
                raise KeyboardInterrupt("Request interrupted by user")

            # Set our custom handler for SIGINT
            signal.signal(signal.SIGINT, sigint_handler)

            try:
                result = self._execute_request(payload, stream)

                # Restore the original SIGINT handler
                signal.signal(signal.SIGINT, original_sigint_handler)

                # If we got here and interruption flag is set, something went wrong with interruption
                if self.interrupted:
                    logger.warning(
                        "Request was interrupted but still returned a result",
                    )
                    # Return a special response indicating interruption
                    return {
                        "role": "assistant",
                        "content": "[Request interrupted by user]",
                        "interrupted": True,
                    }

                return result
            except KeyboardInterrupt:
                # This will be caught immediately after our handler raises KeyboardInterrupt
                logger.warning("Request interrupted by user")

                # Restore the original SIGINT handler
                signal.signal(signal.SIGINT, original_sigint_handler)

                # Return a special response indicating interruption
                return {
                    "role": "assistant",
                    "content": "[Request interrupted by user]",
                    "interrupted": True,
                }
            finally:
                # Make sure the original SIGINT handler is restored
                signal.signal(signal.SIGINT, original_sigint_handler)

        except requests.RequestException as e:
            return self._handle_request_error(e)
        except json.JSONDecodeError as e:
            return self._handle_json_error(e)

    def _prepare_payload(
        self,
        messages: list[dict[str, Any]],
        functions: list[dict[str, Any]] | None,
        tools: list[Callable] | None,
        stream: bool,
        include_reasoning: bool,
    ) -> dict[str, Any]:
        """Prepare the request payload."""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.context_size,
                "num_predict": self.max_tokens,
                **(
                    {"keep_alive": self.keep_alive}
                    if self.keep_alive is not None
                    else {}
                ),
                **self._get_qwen_template_options(messages, tools),
            },
        }

        payload["options"]["tool_choice"] = "auto"

        if include_reasoning:
            reasoning_request = {
                "role": "system",
                "content": get_system_message("verbose_thinking"),
            }

            for i in range(len(messages) - 1, -1, -1):
                if messages[i]["role"] == "user":
                    messages.insert(i, reasoning_request)
                    break

        if functions or tools:
            if functions:
                payload["tools"] = functions
            elif tools:
                payload["tools"] = self._convert_tools_to_schemas(tools)

            if self.is_qwen_model:
                payload["options"]["parallel_function_calls"] = self.config.get(
                    "qwen_parallel_calls",
                    True,
                )

        return payload

    def _execute_request(self, payload: dict[str, Any], stream: bool) -> dict[str, Any]:
        """Execute the request to the Ollama API."""
        logger.debug(f"Sending request to Ollama: {self.api_url}")

        # Create a new session for this request
        self.current_session = requests.Session()

        try:
            response = self.current_session.post(
                self.api_url,
                json=payload,
                timeout=240,
                stream=True,
            )
            response.raise_for_status()

            if not stream:
                # For non-streaming requests, we need to check for interruption while collecting the response
                full_content = ""
                for chunk in response.iter_content(chunk_size=1024):
                    if self.interrupted:
                        logger.warning("Request interrupted while reading response")
                        response.close()
                        # Close the session
                        self.current_session.close()
                        self.current_session = None
                        raise KeyboardInterrupt("Request interrupted by user")

                    if chunk:
                        full_content += chunk.decode("utf-8")

                # Parse the full response
                try:
                    result = json.loads(full_content)
                except json.JSONDecodeError:
                    logger.error(
                        f"Invalid JSON response from Ollama API: {full_content[:100]}...",
                    )
                    raise

                message = result.get("message", {})

                # Normalize tool calls - try structured first, fallback to regex
                self._normalize_tool_calls_in_message(message)

                if "message" in result:
                    # Close the session
                    self.current_session.close()
                    self.current_session = None
                    return message

                # Close the session
                self.current_session.close()
                self.current_session = None
                return result

            # For streaming, just return the response object
            return response
        except KeyboardInterrupt:
            # This will be raised by our signal handler
            raise
        except Exception:
            # Close the session on error
            if self.current_session:
                self.current_session.close()
                self.current_session = None
            raise

    def _handle_request_error(self, e: Exception) -> dict[str, Any]:
        """Handle request exceptions.

        Args:
            e: The exception that occurred

        Returns:
            A formatted error response for the user
        """
        logger.error(f"Error communicating with Ollama: {str(e)}")
        return {
            "role": "assistant",
            "content": f"Error communicating with Ollama: {str(e)}",
        }

    def _handle_json_error(self, e: Exception) -> dict[str, Any]:
        """Handle JSON decoding errors.

        Args:
            e: The JSON decoding exception

        Returns:
            A formatted error response for the user
        """
        logger.error(f"Invalid JSON response from Ollama API: {str(e)}")
        return {
            "role": "assistant",
            "content": "Error: Received invalid response from Ollama API",
        }
