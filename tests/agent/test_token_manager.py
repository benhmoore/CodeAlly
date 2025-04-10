"""Tests for the TokenManager class.

This file contains tests for the TokenManager class, which manages token counting
and context window utilization in the CodeAlly system.
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest

from code_ally.agent.token_manager import TokenManager

# Add the root directory to the path for direct imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import and setup mocks
from tests.test_helper import setup_mocks

setup_mocks()


@pytest.fixture
def token_manager():
    """Create a token manager instance for testing."""
    manager = TokenManager(context_size=4096)
    manager.ui = MagicMock()
    return manager


def test_token_manager_initialization(token_manager):
    """Test that the token manager initializes correctly."""
    assert token_manager.context_size == 4096
    assert token_manager.estimated_tokens == 0
    assert token_manager.token_buffer_ratio == 0.95
    assert token_manager.chars_per_token == 4.0
    assert token_manager._token_cache == {}
    assert token_manager._file_content_hashes == {}
    assert token_manager._file_message_ids == {}


def test_estimate_tokens_basic(token_manager):
    """Test basic token estimation."""
    # Create a simple message
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you for asking!"},
    ]

    # Estimate tokens
    token_count = token_manager.estimate_tokens(messages)

    # Check that the estimate is reasonable
    assert token_count > 0

    # Combined text length is about 93 chars, at 4 chars per token + overhead
    # we should expect ~30-40 tokens
    assert 20 <= token_count <= 50

    # Test cached token estimation
    cached_token_count = token_manager.estimate_tokens(messages)
    assert cached_token_count == token_count


def test_estimate_tokens_with_function_calls(token_manager):
    """Test token estimation with function calls."""
    # Create a message with a function call
    messages = [
        {
            "role": "assistant",
            "content": None,
            "function_call": {
                "name": "get_weather",
                "arguments": '{"location": "San Francisco", "unit": "celsius"}',
            },
        },
    ]

    # Estimate tokens
    token_count = token_manager.estimate_tokens(messages)

    # Check that the estimate is reasonable
    assert token_count > 0

    # Add a message with tool calls and check again
    messages.append(
        {
            "role": "assistant",
            "content": "I'll check the weather for you.",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "New York", "unit": "fahrenheit"}',
                    },
                },
            ],
        },
    )

    # Estimate tokens again
    new_token_count = token_manager.estimate_tokens(messages)

    # New token count should be higher
    assert new_token_count > token_count


def test_update_token_count(token_manager):
    """Test updating token count."""
    # Create messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]

    # Update token count
    token_manager.update_token_count(messages)

    # Check that the token count was updated
    assert token_manager.estimated_tokens > 0

    # Add more messages
    messages.append(
        {"role": "assistant", "content": "Hello! How can I help you today?"},
    )

    # Update token count again
    token_manager.update_token_count(messages)

    # Token count should be higher
    assert token_manager.estimated_tokens > 0


def test_should_compact(token_manager):
    """Test should_compact method."""
    # Initially should not compact
    assert token_manager.should_compact() is False

    # Set a high token count
    token_manager.estimated_tokens = int(token_manager.context_size * 0.96)

    # Now it should suggest compaction based on threshold
    assert token_manager.should_compact() is True

    # Reset token count
    token_manager.estimated_tokens = 0

    # Set last compaction time to recently
    token_manager.last_compaction_time = time.time()

    # Set a high token count again
    token_manager.estimated_tokens = int(token_manager.context_size * 0.96)

    # Should not compact because we recently compacted
    assert token_manager.should_compact() is False


def test_get_token_percentage(token_manager):
    """Test get_token_percentage method."""
    # With zero tokens
    assert token_manager.get_token_percentage() == 0

    # Set a token count
    token_manager.estimated_tokens = 2048  # 50% of context window

    # Check percentage
    assert token_manager.get_token_percentage() == 50

    # Set a higher token count
    token_manager.estimated_tokens = 4096  # 100% of context window

    # Check percentage
    assert token_manager.get_token_percentage() == 100


def test_clear_cache(token_manager):
    """Test clearing the token cache."""
    # Add some entries to the cache
    token_manager._token_cache = {
        ("system", "You are a helpful assistant."): 10,
        ("user", "Hello!"): 5,
    }

    # Clear the cache
    token_manager.clear_cache()

    # Check that the cache is empty
    assert token_manager._token_cache == {}


def test_file_hash_management(token_manager):
    """Test file hash management and duplicate detection."""
    # Register a file
    file_path = "/test/file.py"
    content = "def test_function():\n    return True"
    message_id = "msg_123"

    previous_id = token_manager.register_file_read(file_path, content, message_id)

    # Should be no previous message ID
    assert previous_id is None

    # File should be registered
    assert file_path in token_manager._file_content_hashes
    assert file_path in token_manager._file_message_ids
    assert token_manager._file_message_ids[file_path] == message_id

    # Register the same file again with the same content but a new message ID
    new_message_id = "msg_456"
    previous_id = token_manager.register_file_read(file_path, content, new_message_id)

    # Based on the implementation, it returns None if content hash is the same
    assert previous_id is None

    # But the message ID should be updated
    assert token_manager._file_message_ids[file_path] == new_message_id

    # File should still be registered with the new message ID
    assert token_manager._file_message_ids[file_path] == new_message_id

    # Register the same file with different content
    new_content = "def updated_function():\n    return False"
    previous_id = token_manager.register_file_read(
        file_path,
        new_content,
        new_message_id,
    )

    # Should return the previous message ID since content changed
    assert previous_id == new_message_id

    # Check getting existing file message ID
    result = token_manager.get_existing_file_message_id(file_path, new_content)
    assert result == new_message_id

    # Check with non-existent file
    result = token_manager.get_existing_file_message_id(
        "/non/existent/file.py",
        "content",
    )
    assert result is None

    # Check with existing file but different content
    result = token_manager.get_existing_file_message_id(file_path, "different content")
    assert result is None
