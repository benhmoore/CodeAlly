"""Tests for the ModelClient class.

This file contains tests for the ModelClient class, which provides a standardized
interface for interacting with different language model backends.
"""

import os

# Add the root directory to the path for direct imports
import sys
from unittest.mock import MagicMock

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import and setup mocks
from tests.test_helper import setup_mocks

setup_mocks()

from code_ally.llm_client.model_client import ModelClient


# Create a concrete ModelClient implementation for testing
# PyTest will not collect this class as a test class because it doesn't have a test_ prefix
class SampleModelClient(ModelClient):
    """A test implementation of the ModelClient."""

    def __init__(self, mock_response=None):
        """Initialize the test model client.

        Args:
            mock_response: The response to return when send is called
        """
        super().__init__()
        self._mock_response = mock_response or {
            "role": "assistant",
            "content": "This is a test response.",
        }

    def send(
        self,
        messages,
        functions=None,
        tools=None,
        stream=False,
        include_reasoning=False,
    ):
        """Mock implementation of send."""
        return self._mock_response

    @property
    def model_name(self):
        """Mock implementation of model_name."""
        return "test-model"

    @property
    def endpoint(self):
        """Mock implementation of endpoint."""
        return "https://api.test.com"


def test_abstract_model_client():
    """Test that abstract methods must be implemented."""
    # Test that ModelClient can't be instantiated directly
    with pytest.raises(TypeError):
        ModelClient()

    # Test that send method must be implemented
    class IncompleteClient(ModelClient):
        @property
        def model_name(self):
            return "incomplete-model"

        @property
        def endpoint(self):
            return "https://api.incomplete.com"

    with pytest.raises(TypeError):
        IncompleteClient()

    # Test that model_name property must be implemented
    class NoModelNameClient(ModelClient):
        def send(
            self,
            messages,
            functions=None,
            tools=None,
            stream=False,
            include_reasoning=False,
        ):
            return {}

        @property
        def endpoint(self):
            return "https://api.noname.com"

    with pytest.raises(TypeError):
        NoModelNameClient()

    # Test that endpoint property must be implemented
    class NoEndpointClient(ModelClient):
        def send(
            self,
            messages,
            functions=None,
            tools=None,
            stream=False,
            include_reasoning=False,
        ):
            return {}

        @property
        def model_name(self):
            return "no-endpoint-model"

    with pytest.raises(TypeError):
        NoEndpointClient()


def test_concrete_model_client():
    """Test a concrete implementation of ModelClient."""
    # Create a test client with a custom response
    custom_response = {
        "role": "assistant",
        "content": "Custom response",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "test_function",
                    "arguments": '{"param": "value"}',
                },
            }
        ],
    }
    client = SampleModelClient(custom_response)

    # Test the send method
    messages = [
        {"role": "system", "content": "You are a test assistant."},
        {"role": "user", "content": "Hello!"},
    ]

    response = client.send(messages)

    # Check that the response matches our mock
    assert response == custom_response
    assert response["content"] == "Custom response"
    assert "tool_calls" in response

    # Test the properties
    assert client.model_name == "test-model"
    assert client.endpoint == "https://api.test.com"
