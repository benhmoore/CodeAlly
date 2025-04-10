"""Tests for the ToolManager class.

This file contains tests for the ToolManager class, which manages tool registration,
validation, and execution in the CodeAlly system.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# Add the root directory to the path for direct imports
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import and setup mocks
from tests.test_helper import setup_mocks
setup_mocks()

from code_ally.agent.tool_manager import ToolManager
from code_ally.tools.base import BaseTool
from code_ally.trust import PermissionDeniedError


# Create a concrete test tool class
class TestTool(BaseTool):
    """A test tool for testing the ToolManager."""
    
    name = "test_tool"
    description = "A tool for testing"
    requires_confirmation = False
    
    def execute(self, param1=None, param2=None):
        """Execute the test tool."""
        return self._format_success_response(result=f"Executed with {param1} and {param2}")


class TestProtectedTool(BaseTool):
    """A protected test tool that requires confirmation."""
    
    name = "protected_tool"
    description = "A protected tool for testing"
    requires_confirmation = True
    
    def execute(self, path=None):
        """Execute the protected tool."""
        return self._format_success_response(result=f"Protected operation on {path}")


@pytest.fixture
def trust_manager():
    """Create a mock trust manager for testing."""
    mock_trust = MagicMock()
    mock_trust.is_trusted.return_value = False
    mock_trust.prompt_for_permission.return_value = True
    return mock_trust


@pytest.fixture
def permission_manager(trust_manager):
    """Create a mock permission manager for testing."""
    mock_permission = MagicMock()
    return mock_permission


@pytest.fixture
def tools():
    """Create test tools for testing."""
    return [TestTool(), TestProtectedTool()]


@pytest.fixture
def tool_manager(tools, trust_manager, permission_manager):
    """Create a tool manager instance for testing."""
    manager = ToolManager(tools, trust_manager, permission_manager)
    manager.ui = MagicMock()
    return manager


def test_tool_manager_initialization(tool_manager, tools):
    """Test that the tool manager initializes correctly."""
    # Check that the tools were registered
    assert len(tool_manager.tools) == 2
    assert "test_tool" in tool_manager.tools
    assert "protected_tool" in tool_manager.tools
    
    # Check that the tools are instances of the expected classes
    assert isinstance(tool_manager.tools["test_tool"], TestTool)
    assert isinstance(tool_manager.tools["protected_tool"], TestProtectedTool)


def test_get_function_definitions(tool_manager):
    """Test getting function definitions for tools."""
    # Get function definitions
    func_defs = tool_manager.get_function_definitions()
    
    # Validate the structure
    assert len(func_defs) == 2
    
    # Check that each definition has the expected structure
    for func_def in func_defs:
        assert func_def["type"] == "function"
        assert "function" in func_def
        assert "name" in func_def["function"]
        assert "description" in func_def["function"]
        assert "parameters" in func_def["function"]
        
        # Check that the parameters object has the expected fields
        params = func_def["function"]["parameters"]
        assert "type" in params
        assert "properties" in params
        
        # Tools should be found by name
        assert func_def["function"]["name"] in tool_manager.tools


def test_execute_tool_basic(tool_manager):
    """Test basic tool execution."""
    # Execute a tool
    result = tool_manager.execute_tool("test_tool", {"param1": "value1", "param2": "value2"})
    
    # Check the result
    assert result["success"] is True
    assert "Executed with value1 and value2" in result["result"]


def test_execute_tool_with_permission(tool_manager, trust_manager):
    """Test tool execution that requires permission."""
    # Execute a protected tool
    result = tool_manager.execute_tool("protected_tool", {"path": "/test/path"})
    
    # Check that permission was requested
    trust_manager.is_trusted.assert_called_once()
    trust_manager.prompt_for_permission.assert_called_once()
    
    # Check the result
    assert result["success"] is True
    assert "Protected operation on /test/path" in result["result"]


def test_execute_tool_permission_denied(tool_manager, trust_manager):
    """Test tool execution when permission is denied."""
    # Set up the trust manager to deny permission
    trust_manager.prompt_for_permission.side_effect = PermissionDeniedError("Permission denied")
    
    # Execute a protected tool - should raise PermissionDeniedError
    with pytest.raises(PermissionDeniedError):
        tool_manager.execute_tool("protected_tool", {"path": "/test/path"})


def test_execute_tool_invalid_tool(tool_manager):
    """Test executing an invalid tool."""
    # Execute a non-existent tool
    result = tool_manager.execute_tool("non_existent_tool", {})
    
    # Check the result
    assert result["success"] is False
    assert "Unknown tool" in result["error"]


def test_execute_tool_redundant_call(tool_manager):
    """Test executing a redundant tool call."""
    # Execute a tool
    tool_manager.execute_tool("test_tool", {"param1": "value1"})
    
    # Execute the same tool again with the same arguments
    result = tool_manager.execute_tool("test_tool", {"param1": "value1"})
    
    # Check the result - should indicate redundancy
    assert result["success"] is False
    assert "Identical test_tool call was already executed" in result["error"]


def test_execute_tool_error_handling(tool_manager):
    """Test error handling during tool execution."""
    # Make the tool raise an exception
    tool_manager.tools["test_tool"].execute = MagicMock(side_effect=Exception("Test error"))
    
    # Execute the tool
    result = tool_manager.execute_tool("test_tool", {})
    
    # Check the result
    assert result["success"] is False
    assert "Error executing test_tool" in result["error"]
    assert "Test error" in result["error"]