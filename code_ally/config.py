"""Configuration management for the AI Pair Programmer.

This module handles loading, saving, and accessing configuration settings
for the Code Ally application. It provides a consistent way to manage
user preferences and default values.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union, cast

# Configure logging
logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_CONFIG = {
    "model": "llama3",
    "endpoint": "http://localhost:11434",
    "context_size": 32000,
    "temperature": 0.7,
    "max_tokens": 5000,
    "bash_timeout": 30,
    "auto_confirm": False,
    "check_context_msg": True,
    "dump_dir": "ally",
    "auto_dump": True,  # Whether to automatically dump conversations on exit
}

# Config keys that should be type-checked
CONFIG_TYPES = {
    "model": str,
    "endpoint": str,
    "context_size": int,
    "temperature": float,
    "max_tokens": int,
    "bash_timeout": int,
    "auto_confirm": bool,
    "check_context_msg": bool,
    "dump_dir": str,  # Type for dump directory
    "auto_dump": bool,  # Type for auto dump option
}


def get_config_dir() -> Path:
    """Get the configuration directory path.

    Returns:
        Path: The path to the configuration directory
    """
    # Check if running in development mode
    setup_py_path = Path(__file__).parent.parent / "setup.py"

    if setup_py_path.exists():
        # Development mode - use local config
        config_dir = Path(__file__).parent
        logger.debug(f"Using development mode config directory: {config_dir}")
    else:
        # User mode - use user config directory
        config_dir = Path.home() / ".config" / "code-ally"
        os.makedirs(config_dir, exist_ok=True)
        logger.debug(f"Using user mode config directory: {config_dir}")

    return config_dir


def get_config_file_path() -> Path:
    """Get the path to the config file.

    Returns:
        Path: The path to the config file
    """
    return get_config_dir() / "config.json"


def load_config() -> Dict[str, Any]:
    """Load configuration from file or use defaults.

    Returns:
        Dict[str, Any]: The configuration dictionary with all required keys
    """
    config_file = get_config_file_path()

    # Start with default config
    config = DEFAULT_CONFIG.copy()

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                user_config = json.load(f)

                # Validate and type-check user config values
                for key, value in user_config.items():
                    if key in CONFIG_TYPES:
                        expected_type = CONFIG_TYPES[key]

                        # Try to convert the value to the expected type
                        try:
                            if expected_type == bool and isinstance(value, str):
                                # Handle string boolean conversion separately
                                value = value.lower() in ("true", "yes", "y", "1")
                            else:
                                value = expected_type(value)

                            # Update config with validated value
                            config[key] = value
                        except (ValueError, TypeError):
                            logger.warning(
                                f"Invalid type for config key '{key}': "
                                f"expected {expected_type.__name__}, got {type(value).__name__}"
                            )
                    else:
                        # Include unknown keys but log a warning
                        logger.debug(f"Unknown config key: {key}")
                        config[key] = value

                logger.debug("Configuration loaded successfully")
        except json.JSONDecodeError:
            logger.warning(
                f"Invalid JSON in config file at {config_file}. Using defaults."
            )
        except Exception as e:
            logger.warning(f"Error loading config: {str(e)}. Using defaults.")
    else:
        logger.debug("No config file found. Using defaults.")

    return config


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file.

    Args:
        config: The configuration dictionary to save
    """
    config_file = get_config_file_path()

    try:
        # Ensure the directory exists
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Configuration saved to {config_file}")
    except Exception as e:
        logger.error(f"Error saving config to {config_file}: {str(e)}")
        raise


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a specific configuration value.

    Args:
        key: The configuration key to retrieve
        default: The default value to return if the key is not found
                (if None, uses the value from DEFAULT_CONFIG)

    Returns:
        The value for the specified key
    """
    config = load_config()

    if default is None:
        default = DEFAULT_CONFIG.get(key)

    return config.get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """Set a specific configuration value.

    Args:
        key: The configuration key to set
        value: The value to set

    Raises:
        ValueError: If the value has an invalid type for the key
    """
    # Validate the value type
    if key in CONFIG_TYPES:
        expected_type = CONFIG_TYPES[key]

        # For booleans, accept string representations
        if expected_type == bool and isinstance(value, str):
            value = value.lower() in ("true", "yes", "y", "1")
        elif not isinstance(value, expected_type):
            try:
                value = expected_type(value)
            except (ValueError, TypeError):
                raise ValueError(
                    f"Invalid type for config key '{key}': "
                    f"expected {expected_type.__name__}, got {type(value).__name__}"
                )

    # Load, update, and save the config
    config = load_config()
    config[key] = value
    save_config(config)

    logger.debug(f"Config value updated: {key} = {value}")


def reset_config() -> None:
    """Reset the configuration to default values."""
    save_config(DEFAULT_CONFIG.copy())
    logger.info("Configuration reset to defaults")
