"""Test the CLI functionality of CodeAlly."""

import os
import subprocess
import sys
from unittest.mock import patch

import pytest

# Import and setup mocks
from tests.test_helper import setup_mocks
setup_mocks()


def run_command(command, expected_exit_code=0):
    """Run a command and return its output.
    
    Args:
        command: The command to run as a list of strings
        expected_exit_code: The expected exit code
        
    Returns:
        The stdout output from the command
    """
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    
    assert result.returncode == expected_exit_code, (
        f"Command {command} failed with code {result.returncode}.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    
    return result.stdout


def test_help_option():
    """Test that --help works."""
    # Skip actual execution in CI environments
    if os.environ.get("CI") == "true":
        pytest.skip("Skipping CLI test in CI environment")
        
    # Run the command through the installed entry point
    output = run_command(["ally", "--help"])
    
    # Check that the output contains expected help text
    assert "CodeAlly" in output
    assert "--help" in output
    assert "--version" in output


def test_version_option():
    """Test that --version works."""
    # Skip actual execution in CI environments
    if os.environ.get("CI") == "true":
        pytest.skip("Skipping CLI test in CI environment")
        
    # Run the command through the installed entry point
    output = run_command(["ally", "--version"])
    
    # Check that the output contains a version string
    assert "CodeAlly" in output
    assert "version" in output.lower()


def test_main_function_exists():
    """Test that the main module and function exists in code_ally."""
    # This is a simpler test that doesn't attempt to import the module directly
    # but still checks that the entry point is defined correctly in setup.py
    
    # The package should have been properly built with an entry point
    import pkg_resources
    entry_points = list(pkg_resources.iter_entry_points("console_scripts", "ally"))
    
    # There should be at least one entry point for 'ally'
    assert len(entry_points) > 0
    
    # The first entry point should point to code_ally.main:main
    entry_point = entry_points[0]
    assert entry_point.module_name == "code_ally.main"
    assert entry_point.attrs == ["main"]