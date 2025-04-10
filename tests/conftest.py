"""Pytest configuration file for Code Ally tests."""

import os
import shutil
import tempfile

import pytest


@pytest.fixture
def temp_directory():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_directory_structure(temp_directory):
    """
    Create a sample directory structure for testing.

    Structure:
    - root/
      - dir1/
        - file1.txt
        - file2.py
        - subdir1/
          - file3.md
      - dir2/
        - file4.json
      - .git/
        - config
      - .gitignore
      - file5.py
      - file6.pyc
    """
    # Create the directory structure
    os.makedirs(os.path.join(temp_directory, "dir1", "subdir1"), exist_ok=True)
    os.makedirs(os.path.join(temp_directory, "dir2"), exist_ok=True)
    os.makedirs(os.path.join(temp_directory, ".git"), exist_ok=True)

    # Create sample files
    with open(os.path.join(temp_directory, "dir1", "file1.txt"), "w") as f:
        f.write("Sample content 1")

    with open(os.path.join(temp_directory, "dir1", "file2.py"), "w") as f:
        f.write("print('Hello, world!')")

    with open(os.path.join(temp_directory, "dir1", "subdir1", "file3.md"), "w") as f:
        f.write("# Sample Markdown")

    with open(os.path.join(temp_directory, "dir2", "file4.json"), "w") as f:
        f.write('{"sample": "data"}')

    with open(os.path.join(temp_directory, ".git", "config"), "w") as f:
        f.write("[core]\n    repositoryformatversion = 0")

    with open(os.path.join(temp_directory, ".gitignore"), "w") as f:
        f.write("*.pyc\n.DS_Store\n__pycache__/\n")

    with open(os.path.join(temp_directory, "file5.py"), "w") as f:
        f.write("def sample_function():\n    return True")

    with open(os.path.join(temp_directory, "file6.pyc"), "w") as f:
        f.write("Compiled Python file")

    # Ensure this directory exists for testing
    os.makedirs(os.path.join(temp_directory, "does_not_exist"), exist_ok=True)

    return temp_directory
