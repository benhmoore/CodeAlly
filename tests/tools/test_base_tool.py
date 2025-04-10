"""Tests for the BaseTool class.

This file contains tests for the BaseTool class, which is the base class for all tools
in the CodeAlly system.
"""

import os
import pytest
from unittest.mock import MagicMock

# Add the root directory to the path for direct imports
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import and setup mocks
from tests.test_helper import setup_mocks
setup_mocks()

from code_ally.tools.base import BaseTool


# Create concrete tool classes for testing
class ValidTool(BaseTool):
    """A valid tool implementation for testing."""
    
    name = "valid_tool"
    description = "A valid tool for testing"
    requires_confirmation = False
    
    def execute(self, param1=None, param2=None):
        """Execute the valid tool."""
        return self._format_success_response(result="Tool executed")


class NoNameTool(BaseTool):
    """A tool without a name."""
    
    description = "A tool without a name"
    requires_confirmation = False
    
    def execute(self):
        """Execute the tool."""
        return self._format_success_response()


class NoDescriptionTool(BaseTool):
    """A tool without a description."""
    
    name = "no_description_tool"
    requires_confirmation = False
    
    def execute(self):
        """Execute the tool."""
        return self._format_success_response()


class NoConfirmationTool(BaseTool):
    """A tool without a requires_confirmation attribute."""
    
    name = "no_confirmation_tool"
    description = "A tool without a requires_confirmation attribute"
    
    def execute(self):
        """Execute the tool."""
        return self._format_success_response()


class NoExecuteTool(BaseTool):
    """A tool without an execute method implementation."""
    
    name = "no_execute_tool"
    description = "A tool without an execute method implementation"
    requires_confirmation = False


def test_valid_tool_initialization():
    """Test that a valid tool can be initialized."""
    tool = ValidTool()
    assert tool.name == "valid_tool"
    assert tool.description == "A valid tool for testing"
    assert tool.requires_confirmation is False


def test_tool_without_name():
    """Test that a tool without a name raises a ValueError."""
    with pytest.raises(ValueError) as excinfo:
        NoNameTool()
    assert "must define a 'name' class variable" in str(excinfo.value)


def test_tool_without_description():
    """Test that a tool without a description raises a ValueError."""
    with pytest.raises(ValueError) as excinfo:
        NoDescriptionTool()
    assert "must define a 'description' class variable" in str(excinfo.value)


def test_tool_without_confirmation_flag():
    """Test that a tool without a requires_confirmation attribute raises a ValueError."""
    with pytest.raises(ValueError) as excinfo:
        NoConfirmationTool()
    assert "must define a 'requires_confirmation' class variable" in str(excinfo.value)


def test_abstract_execute_method():
    """Test that the abstract execute method raises NotImplementedError."""
    tool = ValidTool()
    
    # Check that BaseTool.execute raises NotImplementedError 
    with pytest.raises(NotImplementedError):
        BaseTool.execute(tool)
    
    # Check that NoExecuteTool can't be instantiated because execute is not implemented
    with pytest.raises(TypeError, match="abstract class NoExecuteTool without an implementation for abstract method 'execute'"):
        NoExecuteTool()


def test_format_error_response():
    """Test formatting an error response."""
    tool = ValidTool()
    
    response = tool._format_error_response("Test error message")
    
    assert response["success"] is False
    assert response["error"] == "Test error message"


def test_format_success_response():
    """Test formatting a success response."""
    tool = ValidTool()
    
    # Simple success response
    response = tool._format_success_response()
    assert response["success"] is True
    assert response["error"] == ""
    
    # Success response with additional fields
    response = tool._format_success_response(
        result="Test result",
        data={"key": "value"}
    )
    assert response["success"] is True
    assert response["error"] == ""
    assert response["result"] == "Test result"
    assert response["data"] == {"key": "value"}


def test_execute_implementation():
    """Test that the execute method can be implemented and called correctly."""
    tool = ValidTool()
    
    response = tool.execute(param1="test1", param2="test2")
    
    assert response["success"] is True
    assert response["result"] == "Tool executed"