# Code Ally

![Code Ally Demo - Terminal interface showing interactive interface](https://github.com/benhmoore/code-ally/blob/main/assets/code-ally-demo.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Work in progress/proof of concept!

A local LLM-powered pair programming assistant using function calling capabilities with Ollama. Code Ally helps you with coding tasks through natural language, providing tools for file operations, code searching, and executing shell commands - all while keeping your code and data local.

## 🚀 Features

-   **Interactive Conversation:** Engage with an LLM (named "Ally") to solve coding tasks collaboratively
-   **Comprehensive Tool Suite:**
    -   Read, write, and edit files with precise control
    -   Find files using glob patterns (similar to `find`)
    -   Search file contents with regex (similar to `grep`)
    -   List directory contents with filtering
    -   Execute shell commands safely with security checks
-   **Safety-First Design:**
    -   User confirmation prompts for potentially destructive operations
    -   Session-based or path-specific permissions
    -   Command filtering to prevent dangerous operations
-   **Excellent Developer Experience:**
    -   Rich terminal UI with color-coded feedback and clear formatting
    -   Multi-step tool usage for complex tasks
    -   Function-calling interface with Ollama LLMs
    -   Flexible configuration via command line, slash commands, or config file

## 📋 Prerequisites

-   **Python 3.8+** (Tested with 3.13)
-   **[Ollama](https://ollama.com)** running locally with function-calling capable models:
    -   **Recommended models:** qwen2.5-coder:latest or newer models that support function calling
    -   Make sure Ollama is running before starting Code Ally
    -   Code Ally will automatically check if Ollama is configured properly and provide instructions if needed

## 🔧 Installation

### From PyPI (Recommended)

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install from PyPI
pip install code-ally

# Install the required Ollama model
ollama pull qwen2.5-coder:latest
```

### Development Installation

```bash
# Clone the repository
git clone https://github.com/example/code-ally.git
cd code-ally

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with development dependencies
pip install -e ".[dev]"

# OR, if you're on macOS with Homebrew Python and encounter the externally-managed-environment error:
pip install -e ".[dev]" --break-system-packages

# Install the required Ollama model
ollama pull qwen2.5-coder:latest
```

## ⚙️ Configuration

Code Ally uses a layered configuration approach:

1. **Command line arguments** (highest precedence)
2. **User config file** located at `~/.config/code-ally/config.json`
3. **Default values**

### Managing Configuration

```bash
# View your current configuration
code-ally --config-show

# Save current settings as defaults
code-ally --model qwen2.5-coder:latest --temperature 0.8 --config

# Reset to default configuration
code-ally --config-reset
```

### Configuration File Structure

The configuration file is a JSON file with the following structure:

```json
{
    "model": "qwen2.5-coder:latest",
    "endpoint": "http://localhost:11434",
    "context_size": 4096,
    "temperature": 0.7,
    "max_tokens": 1000,
    "bash_timeout": 30,
    "auto_confirm": false
}
```

## 🖥️ Usage

### Basic Usage

```bash
# Start Code Ally with default settings
code-ally

# Display help information about available commands
code-ally --help
```

### Advanced Options

```bash
# Use a specific model
code-ally --model qwen2.5-coder:latest

# Connect to a different Ollama endpoint
code-ally --endpoint http://localhost:11434

# Adjust generation parameters
code-ally --temperature 0.8 --context-size 8192 --max-tokens 2000

# Skip all confirmation prompts (use with caution!)
code-ally --yes-to-all
```

### Direct Commands and Slash Commands

Code Ally supports direct commands for common operations:

| Command                                       | Description                                                |
| --------------------------------------------- | ---------------------------------------------------------- |
| `ls`, `list`, `dir`                           | List files in the current directory without LLM processing |
| Previously `exit`, `quit` (now require slash) | Exit commands now require a slash: `/exit` or `/quit`      |

Code Ally also supports the following slash commands during a conversation:

| Command                     | Description                                                                             |
| --------------------------- | --------------------------------------------------------------------------------------- |
| `/help`                     | Display help information about available commands and tools                             |
| `/clear`                    | Clear the conversation history and free up context window                               |
| `/compact`                  | Create a summary of the conversation and reset context while preserving key information |
| `/config`                   | View current configuration settings                                                     |
| `/config [setting] [value]` | Change a configuration setting (e.g., `/config temperature 0.8`)                        |
| `/ls`                       | List files in the current directory                                                     |
| `/ls [path]`                | List files in the specified directory                                                   |
| `/exit` or `/quit`          | Exit the application                                                                    |

### Command-Line Options

| Option                | Description                                                               | Default                  |
| --------------------- | ------------------------------------------------------------------------- | ------------------------ |
| `--help`              | Display help information about available command-line options             | -                        |
| `--model`             | The model to use                                                          | `qwen2.5-coder:latest`   |
| `--endpoint`          | The Ollama API endpoint URL                                               | `http://localhost:11434` |
| `--temperature`       | Temperature for text generation (0.0-1.0)                                 | `0.7`                    |
| `--context-size`      | Context size in tokens                                                    | `32000`                  |
| `--max-tokens`        | Maximum tokens to generate                                                | `5000`                   |
| `--yes-to-all`        | Skip all confirmation prompts (dangerous, use with caution)               | `False`                  |
| `--check-context-msg` | Encourage LLM to check its context when redundant tool calls are detected | `True`                   |
| `--no-auto-dump`      | Disable automatic conversation dump when exiting                          | `True`                   |
| `--config`            | Save current options as config defaults                                   | `False`                  |
| `--config-show`       | Show current configuration                                                | `False`                  |
| `--config-reset`      | Reset configuration to defaults                                           | `False`                  |
| `--skip-ollama-check` | Skip the check for Ollama availability                                    | `False`                  |
| `--verbose`           | Enable verbose mode with detailed logging                                 | `False`                  |

## 🛠️ Available Tools

| Tool         | Description                                           |
| ------------ | ----------------------------------------------------- |
| `file_read`  | Read the contents of a file                           |
| `file_write` | Write content to a file (creates or overwrites)       |
| `file_edit`  | Edit an existing file by replacing a specific portion |
| `bash`       | Execute a shell command and return its output         |
| `glob`       | Find files matching a glob pattern                    |
| `grep`       | Search for a pattern in files                         |
| `ls`         | List directory contents                               |
| `git`        | Perform basic Git operations                          |

## 🔒 Security Considerations

-   Code Ally requires confirmation for potentially destructive operations
-   The `bash` tool filters dangerous commands and requires explicit user confirmation
-   Use `--yes-to-all` with caution as it bypasses confirmation prompts
-   All operations remain local to your machine

## 🤝 Contributing

Contributions are welcome. Here's how you can help:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
