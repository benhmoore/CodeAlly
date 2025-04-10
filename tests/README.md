# Code Ally Tests

This directory contains tests for the Code Ally application.

## Running Tests

To run all tests:

```bash
pytest
```

To run specific test files:

```bash
pytest tests/prompts/test_directory_utils.py
```

To run with coverage:

```bash
pytest --cov=code_ally
```

## Test Structure

- `conftest.py` - Contains shared fixtures for tests
- `prompts/` - Tests for the prompt generation modules
  - `test_directory_utils.py` - Tests for directory tree generation
  - `test_directory_config.py` - Tests for directory tree configuration
  - `test_system_messages_integration.py` - Integration tests for system messages

## Test Coverage

The current test suite focuses on:

1. Directory tree generation
2. Configuration interface for directory tree settings
3. Integration with system messages

Additional tests can be added for more comprehensive coverage.