# Contributing to Code Ally

Thank you for your interest in contributing to Code Ally! This document provides guidelines and instructions for contributing.

## Setting Up Development Environment

1. Fork the repository and clone your fork:

    ```bash
    git clone https://github.com/YOUR_USERNAME/code-ally.git
    cd code-ally
    ```

2. Set up a virtual environment and install development dependencies:

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -e ".[dev]"   # Install the package in development mode with dev dependencies
    pip install -r requirements-dev.txt
    ```

3. Set up pre-commit hooks:
    ```bash
    pre-commit install
    ```

## Development Workflow

1. Create a new branch for your feature or bug fix:

    ```bash
    git checkout -b feature/your-feature-name
    ```

2. Make your changes, following the code style guidelines below.

3. Commit your changes:

    ```bash
    git commit -m "Your descriptive commit message"
    ```

4. Push to your fork:

    ```bash
    git push origin feature/your-feature-name
    ```

5. Open a pull request against the main repository.

## Code Style Guidelines

-   **Imports**: Standard Python modules first, then third-party, then project imports
-   **Type Annotations**: Strict typing with mypy (disallow_untyped_defs=true)
-   **Documentation**: Google-style docstrings with Args and Returns sections
-   **Naming**: snake_case (variables/functions), PascalCase (classes), ALL_CAPS (constants)
-   **Error Handling**: Structured responses with `{success: bool, error: str}` format
-   **Formatting**: Black (88-char line limit), isort with black profile
-   **Tools**: Each tool should inherit from BaseTool and implement execute() method

We use the following tools to enforce code style:

-   [Black](https://black.readthedocs.io/en/stable/) for code formatting
-   [isort](https://pycqa.github.io/isort/) for import sorting
-   [mypy](https://mypy.readthedocs.io/en/stable/) for static type checking
-   [pylint](https://pylint.pycqa.org/en/latest/) for code quality

You can run all code style checks with the following commands:

```bash
# Format code
black . && isort .

# Check code
pylint code_ally tests
mypy code_ally tests
```

## Testing

We use pytest for testing. Please include tests for any new functionality or bug fixes:

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=code_ally tests/

# Run specific test files
pytest tests/test_specific_module.py
```

Our CI workflow will automatically run tests on your PR to ensure everything passes.

## Pull Request Process

1. Ensure your code follows the style guidelines
2. Add tests for any new functionality or bug fixes
3. Update the README.md with details of changes if needed
4. Create a pull request with a clear title and description
5. Verify that all CI checks pass
6. Address any review comments and update your PR as needed

## Versioning and Release Process

We follow [Semantic Versioning](https://semver.org/) for this project.

1. Update the CHANGELOG.md file with a summary of the changes.
2. Use bump2version to increment the version number:

   ```bash
   # For a new patch release (bug fixes)
   bump2version patch
   
   # For a new minor release (new features, backwards compatible)
   bump2version minor
   
   # For a new major release (breaking changes)
   bump2version major
   ```

3. Push the new commit and tag to GitHub:

   ```bash
   git push origin main --tags
   ```

4. The GitHub Actions workflow will automatically build and publish the new version to PyPI.

## Adding New Tools

To add a new tool to Code Ally:

1. Create a new file in `code_ally/tools/` named after your tool
2. Implement a tool class that inherits from `BaseTool`
3. Add the tool to `code_ally/tools/__init__.py`

Example tool implementation:

```python
from typing import Dict, Any
from code_ally.tools.base import BaseTool

class MyNewTool(BaseTool):
    name = "my_tool"
    description = "Description of what my tool does"
    requires_confirmation = True  # Set to True if the tool could modify files or execute commands

    def execute(self, param1: str, param2: int = 0, **kwargs) -> Dict[str, Any]:
        """Execute the tool functionality.

        Args:
            param1: Description of parameter 1
            param2: Description of parameter 2 (optional)
            **kwargs: Additional arguments

        Returns:
            Dict with keys:
                success: Whether the tool executed successfully
                result: The result of the tool execution
                error: Error message if any
        """
        try:
            # Implement your tool logic here
            result = f"Processed {param1} with value {param2}"

            return {
                "success": True,
                "result": result,
                "error": ""
            }
        except Exception as e:
            return {
                "success": False,
                "result": "",
                "error": str(e)
            }
```

## License

By contributing to this project, you agree that your contributions will be licensed under the project's MIT License.
