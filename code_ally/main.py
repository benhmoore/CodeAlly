#!/usr/bin/env python3
"""Code Ally main entry point.

This module contains the main function and command-line interface for the
Code Ally application. It handles argument parsing, configuration management,
and initializing the agent with the appropriate tools and models.
"""

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, Optional, Tuple

import requests
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from code_ally.agent import Agent
from code_ally.config import DEFAULT_CONFIG, load_config, reset_config, save_config
from code_ally.llm_client import OllamaClient
from code_ally.prompts import get_main_system_prompt
from code_ally.tools import ToolRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("code_ally")


def configure_logging(verbose: bool) -> None:
    """Configure logging level based on verbose flag.

    Args:
        verbose: Whether to enable verbose logging
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    else:
        logger.setLevel(logging.INFO)


def check_ollama_availability(
    endpoint: str, model: str
) -> Tuple[bool, bool, Optional[str]]:
    """Check if Ollama is running and the specified model is available.

    Args:
        endpoint: The Ollama API endpoint
        model: The model name to check

    Returns:
        tuple: (is_running, model_available, error_message)
    """
    logger.debug(f"Checking Ollama availability at {endpoint} for model {model}")

    # Check if Ollama server is running
    try:
        response = requests.get(f"{endpoint}/api/tags", timeout=5)
        response.raise_for_status()

        # Server is running, check if the model is available
        data = response.json()

        if "models" not in data:
            logger.warning("Unexpected response format from Ollama API")
            return True, False, "Unexpected response format from Ollama API"

        available_models = [model_data["name"] for model_data in data["models"]]
        logger.debug(f"Available models: {available_models}")

        if model in available_models:
            logger.info(f"Model '{model}' is available")
            return True, True, None
        else:
            logger.warning(f"Model '{model}' is not available in Ollama")
            return True, False, f"Model '{model}' is not available in Ollama"

    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to Ollama at {endpoint}")
        return False, False, f"Could not connect to Ollama at {endpoint}"
    except requests.exceptions.Timeout:
        logger.error(f"Connection to Ollama timed out")
        return False, False, f"Connection to Ollama timed out"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Ollama: {str(e)}")
        return False, False, f"Error connecting to Ollama: {str(e)}"
    except (KeyError, ValueError) as e:
        logger.error(f"Error parsing Ollama response: {str(e)}")
        return True, False, f"Error parsing Ollama response: {str(e)}"


def print_ollama_instructions(endpoint: str, model: str, error_message: str) -> None:
    """Print instructions for setting up Ollama.

    Args:
        endpoint: The Ollama API endpoint
        model: The model name
        error_message: The specific error message
    """
    console = Console()

    instructions = f"""
1. Make sure Ollama is installed:
   - Download from: https://ollama.ai
   - Follow the installation instructions for your platform

2. Start the Ollama server:
   - Run the Ollama application
   - Or start it from the command line: `ollama serve`

3. Pull the required model:
   - Run: `ollama pull {model}`

4. Verify Ollama is running:
   - Run: `curl {endpoint}/api/tags`
   - You should see a JSON response with available models

Current error: {error_message}
    """

    console.print(
        Panel(
            instructions,
            title="[bold yellow]⚠️ Ollama Configuration Required[/]",
            border_style="yellow",
            expand=False,
        )
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        The parsed arguments
    """
    config = load_config()

    parser = argparse.ArgumentParser(
        description="Code Ally - Local LLM-powered pair programming assistant",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Model and API settings
    model_group = parser.add_argument_group("Model Settings")
    model_group.add_argument(
        "--model", default=config.get("model"), help=f"The model to use"
    )
    model_group.add_argument(
        "--endpoint",
        default=config.get("endpoint"),
        help=f"The Ollama API endpoint URL",
    )
    model_group.add_argument(
        "--temperature",
        type=float,
        default=config.get("temperature"),
        help=f"Temperature for text generation (0.0-1.0)",
    )
    model_group.add_argument(
        "--context-size",
        type=int,
        default=config.get("context_size"),
        help=f"Context size in tokens",
    )
    model_group.add_argument(
        "--max-tokens",
        type=int,
        default=config.get("max_tokens"),
        help=f"Maximum tokens to generate",
    )

    # Configuration management
    config_group = parser.add_argument_group("Configuration")
    config_group.add_argument(
        "--config",
        action="store_true",
        help="Save the current command line options as config defaults",
    )
    config_group.add_argument(
        "--config-show", action="store_true", help="Show the current configuration"
    )
    config_group.add_argument(
        "--config-reset", action="store_true", help="Reset configuration to defaults"
    )

    # Security and behavior settings
    security_group = parser.add_argument_group("Security and Behavior")
    security_group.add_argument(
        "--yes-to-all",
        action="store_true",
        help="Skip all confirmation prompts (dangerous, use with caution)",
    )
    security_group.add_argument(
        "--check-context-msg",
        action="store_true",
        dest="check_context_msg",
        default=config.get("check_context_msg"),
        help="Encourage LLM to check its context when redundant tool calls are detected",
    )
    security_group.add_argument(
        "--no-auto-dump",
        action="store_false",
        dest="auto_dump",
        default=config.get("auto_dump", True),
        help="Disable automatic conversation dump when exiting",
    )

    # Debug and diagnostics
    debug_group = parser.add_argument_group("Debug and Diagnostics")
    debug_group.add_argument(
        "--skip-ollama-check",
        action="store_true",
        help="Skip the check for Ollama availability",
    )
    debug_group.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose mode with detailed logging",
    )

    return parser.parse_args()


def handle_config_commands(args: argparse.Namespace) -> bool:
    """Handle configuration-related commands.

    Args:
        args: The parsed command line arguments

    Returns:
        True if a config command was handled and the program should exit,
        False otherwise
    """
    console = Console()

    # Show current configuration
    if args.config_show:
        console.print(json.dumps(load_config(), indent=2))
        return True

    # Reset configuration to defaults
    if args.config_reset:
        reset_config()
        console.print("[green]Configuration reset to defaults[/]")
        return True

    # Save current settings as new defaults
    if args.config:  # This if statement was missing
        new_config = load_config()
        new_config.update(
            {
                "model": args.model,
                "endpoint": args.endpoint,
                "temperature": args.temperature,
                "context_size": args.context_size,
                "max_tokens": args.max_tokens,
                "auto_confirm": args.yes_to_all,
                "check_context_msg": args.check_context_msg,
                "auto_dump": args.auto_dump,
            }
        )
        save_config(new_config)
        console.print("[green]Configuration saved successfully[/]")
        return True

    return False


def main() -> None:
    """Main entry point for the application."""
    # Create console for rich output
    console = Console()

    # Parse command line arguments
    args = parse_args()

    # Configure logging based on verbose flag
    configure_logging(args.verbose)

    # Handle configuration commands (these don't require Ollama)
    if handle_config_commands(args):
        return

    # Check if Ollama is configured correctly (unless explicitly skipped)
    if not args.skip_ollama_check:
        console.print("[bold]Checking Ollama availability...[/]")
        is_running, model_available, error_message = check_ollama_availability(
            args.endpoint, args.model
        )

        if not is_running or not model_available:
            console.print(f"[bold red]Error:[/] {error_message}")
            print_ollama_instructions(args.endpoint, args.model, error_message)

            # Ask user if they want to continue anyway
            continue_anyway = input("Do you want to continue anyway? (y/n): ").lower()
            if continue_anyway not in ("y", "yes"):
                console.print(
                    "[yellow]Exiting. Please configure Ollama and try again.[/]"
                )
                return

            console.print("[yellow]Continuing without validated Ollama setup...[/]")
        else:
            console.print(
                f"[green]✓ Ollama is running and model '{args.model}' is available[/]"
            )

    # Create the LLM client
    model_client = OllamaClient(
        endpoint=args.endpoint,
        model_name=args.model,
        temperature=args.temperature,
        context_size=args.context_size,
        max_tokens=args.max_tokens,
    )

    # Get tools from the registry
    tools = ToolRegistry().get_tool_instances()

    # Get the system prompt
    system_prompt = get_main_system_prompt()

    # Create the agent
    agent = Agent(
        model_client=model_client,
        tools=tools,
        system_prompt=system_prompt,
        verbose=args.verbose,
        check_context_msg=args.check_context_msg,
        auto_dump=args.auto_dump,
    )

    # Set auto-confirm if specified
    if args.yes_to_all:
        agent.trust_manager.set_auto_confirm(True)
        logger.warning("Auto-confirm mode enabled - will skip all confirmation prompts")

    try:
        # Run the conversation loop
        agent.run_conversation()
    except KeyboardInterrupt:
        # Only dump conversation if auto_dump is enabled
        if agent.auto_dump:  # Use agent's property instead of args.auto_dump
            agent.command_handler.dump_conversation(agent.messages, "")
        console.print("\n[bold]Goodbye![/]")
        sys.exit(0)
    except requests.exceptions.RequestException as e:
        console.print(f"\n[bold red]Error connecting to Ollama:[/] {str(e)}")
        print_ollama_instructions(args.endpoint, args.model, str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error occurred:")
        console.print(f"\n[bold red]Unexpected error:[/] {str(e)}")
        if args.verbose:
            import traceback

            console.print(
                Panel(
                    traceback.format_exc(),
                    title="[bold red]Error Details[/]",
                    border_style="red",
                )
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
