"""Tests for the Agent class.

This file contains tests for the Agent class, which is the core component
of the CodeAlly system that manages conversations and handles tool execution.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Setup mocks FIRST before importing Agent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from tests.test_helper import setup_mocks

setup_mocks()

# Now import after mocks are set up
from code_ally.agent.agent import Agent
from code_ally.service_registry import ServiceRegistry


@pytest.fixture
def mock_model_client():
    """Create a mock model client for testing."""
    mock_client = MagicMock()
    mock_client.context_size = 4096
    mock_client.send.return_value = {
        "role": "assistant",
        "content": "Hello, I'm your assistant.",
    }
    return mock_client


@pytest.fixture
def mock_tools():
    """Create mock tools for testing."""
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "A test tool"
    mock_tool.requires_confirmation = False
    mock_tool.execute.return_value = {"success": True, "result": "Tool executed"}
    return [mock_tool]


@pytest.fixture
def agent(mock_model_client, mock_tools):
    """Create an agent instance for testing."""
    # Create a new service registry for each test
    service_registry = ServiceRegistry()

    # Mock the UIManager class before creating an agent
    with patch("code_ally.agent.agent.UIManager") as MockUIManager:
        # Configure the UI manager mock
        mock_ui = MagicMock()
        MockUIManager.return_value = mock_ui

        # Create the agent
        agent = Agent(
            model_client=mock_model_client,
            tools=mock_tools,
            system_prompt="You are a test assistant.",
            service_registry=service_registry,
        )

        # Mock the tool manager - we need to replace the entire attribute, not just the execute_tool method
        agent.tool_manager = MagicMock()
        agent.tool_manager.execute_tool.return_value = {
            "success": True,
            "result": "Tool executed",
        }
        agent.tool_manager.format_tool_result.return_value = {
            "success": True,
            "result": "Tool executed",
        }
        agent.tool_manager.get_function_definitions.return_value = []

        return agent


def test_agent_initialization(agent, mock_model_client, mock_tools):
    """Test that the agent initializes correctly."""
    # Check that the agent was initialized with the correct components
    assert agent.model_client == mock_model_client
    assert len(agent.messages) == 1  # System message
    assert agent.messages[0]["role"] == "system"
    assert agent.messages[0]["content"] == "You are a test assistant."

    # Check that components were registered
    assert agent.service_registry.get("ui_manager") is not None
    assert agent.service_registry.get("trust_manager") is not None
    assert agent.service_registry.get("permission_manager") is not None
    assert agent.service_registry.get("token_manager") is not None
    assert agent.service_registry.get("tool_manager") is not None
    assert agent.service_registry.get("task_planner") is not None
    assert agent.service_registry.get("command_handler") is not None


def test_process_llm_response_text(agent):
    """Test processing a simple text response from the LLM."""
    # Create a response with just text
    response = {
        "role": "assistant",
        "content": "This is a test response.",
    }

    # Process the response
    agent.process_llm_response(response)

    # Check that the message was added to history
    assert len(agent.messages) == 2  # System message + new message
    assert agent.messages[1] == response

    # Check that the UI was used to print the response
    agent.ui.print_assistant_response.assert_called_once_with(
        "This is a test response.",
    )


def test_process_llm_response_with_tool_calls(agent, mock_tools):
    """Test processing a response with tool calls."""
    # Create a tool call
    tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"param1": "value1"}',
        },
    }

    # Create a response with a tool call
    response = {
        "role": "assistant",
        "content": "I'll call a tool for you.",
        "tool_calls": [tool_call],
    }

    # Set up the model client to return a follow-up response
    follow_up_response = {
        "role": "assistant",
        "content": "The tool was executed successfully.",
    }
    agent.model_client.send.return_value = follow_up_response

    # Tool manager is already set up in the fixture

    # Process the response
    agent.process_llm_response(response)

    # Check that the tool was called
    agent.tool_manager.execute_tool.assert_called_once()

    # Check that the follow-up response was processed
    agent.ui.print_assistant_response.assert_called_with(
        "The tool was executed successfully.",
    )

    # Check that the messages include the tool call and its result
    assert (
        len(agent.messages) > 3
    )  # System message + assistant message + tool result + follow-up


def test_normalize_tool_call(agent):
    """Test normalizing different tool call formats."""
    # Standard format
    standard_tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"param1": "value1"}',
        },
    }

    call_id, tool_name, arguments = agent._normalize_tool_call(standard_tool_call)
    assert call_id == "call_123"
    assert tool_name == "test_tool"
    assert arguments == {"param1": "value1"}

    # Older format
    older_format = {
        "id": "call_123",
        "name": "test_tool",
        "arguments": '{"param1": "value1"}',
    }

    call_id, tool_name, arguments = agent._normalize_tool_call(older_format)
    assert call_id == "call_123"
    assert tool_name == "test_tool"
    assert arguments == {"param1": "value1"}

    # Format with already parsed arguments
    parsed_args_format = {
        "id": "call_123",
        "function": {
            "name": "test_tool",
            "arguments": {"param1": "value1"},
        },
    }

    call_id, tool_name, arguments = agent._normalize_tool_call(parsed_args_format)
    assert call_id == "call_123"
    assert tool_name == "test_tool"
    assert arguments == {"param1": "value1"}


@patch("code_ally.agent.agent.time")
def test_process_sequential_tool_calls(mock_time, agent):
    """Test processing multiple tool calls sequentially."""
    mock_time.time.return_value = 12345

    # Create multiple tool calls
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{"param1": "value1"}',
            },
        },
        {
            "id": "call_2",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{"param2": "value2"}',
            },
        },
    ]

    # Tool manager is already set up in the fixture

    # Process the tool calls
    agent._process_sequential_tool_calls(tool_calls)

    # Check that both tools were called
    assert agent.tool_manager.execute_tool.call_count == 2

    # Check that tool messages were added
    tool_messages = [m for m in agent.messages if m.get("role") == "tool"]
    assert len(tool_messages) == 2
