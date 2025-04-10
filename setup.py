#!/usr/bin/env python3
"""
This file is only kept for backward compatibility.
All configuration is now done in pyproject.toml
"""
from setuptools import setup

# This setup.py is only here to ensure compatibility with older tools
# For new tools, pyproject.toml is the source of truth
# However, we need to explicitly set the package name and version to ensure metadata is correct
setup(
    name="code_ally",
    version="0.4.5",
)
