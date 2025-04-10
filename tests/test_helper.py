"""Test helper functions and fixtures for CodeAlly tests."""

import os
import sys
from unittest.mock import MagicMock

# Add the root directory to the path for direct imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def setup_mocks():
    """Set up common mocks to avoid import errors."""
    # Mock prompt_toolkit
    mock_pt = MagicMock()
    mock_pt.key_binding = MagicMock()
    mock_pt.shortcuts = MagicMock()
    mock_pt.styles = MagicMock()
    mock_pt.history = MagicMock()
    mock_pt.completion = MagicMock()
    mock_pt.patch_stdout = MagicMock()
    sys.modules["prompt_toolkit"] = mock_pt
    sys.modules["prompt_toolkit.key_binding"] = mock_pt.key_binding
    sys.modules["prompt_toolkit.shortcuts"] = mock_pt.shortcuts
    sys.modules["prompt_toolkit.styles"] = mock_pt.styles
    sys.modules["prompt_toolkit.history"] = mock_pt.history
    sys.modules["prompt_toolkit.completion"] = mock_pt.completion
    sys.modules["prompt_toolkit.patch_stdout"] = mock_pt.patch_stdout

    # Create a comprehensive set of mocks for rich
    mock_rich = MagicMock()
    rich_modules = [
        "console",
        "live",
        "markdown",
        "syntax",
        "panel",
        "table",
        "box",
        "progress",
        "prompt",
        "theme",
        "spinner",
        "text",
        "style",
        "color",
        "columns",
        "align",
        "rule",
        "status",
        "logging",
        "pretty",
        "measure",
    ]

    # Set attributes in mock_rich and create module mocks
    for module in rich_modules:
        setattr(mock_rich, module, MagicMock())
        sys.modules[f"rich.{module}"] = getattr(mock_rich, module)

    # Set the main rich module
    sys.modules["rich"] = mock_rich
