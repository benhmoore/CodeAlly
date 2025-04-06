"""File: ui_manager.py

Manages UI rendering and user interaction.
"""

import os
import time
import threading
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text


class UIManager:
    """Manages UI rendering and user interaction."""

    def __init__(self):
        """Initialize the UI manager."""
        self.console = Console()
        self.thinking_spinner = Spinner("dots2", text="[cyan]Thinking[/]")
        self.thinking_event = threading.Event()
        self.verbose = False

        # Create history directory if it doesn't exist
        history_dir = os.path.expanduser("~/.ally")
        os.makedirs(history_dir, exist_ok=True)

        # Create custom key bindings
        kb = KeyBindings()

        @kb.add("c-c")
        def _(event):
            """Custom Ctrl+C handler.

            Clear buffer if not empty, otherwise exit.
            """
            if event.app.current_buffer.text:
                # If there's text, clear the buffer
                event.app.current_buffer.text = ""
            else:
                # If empty, exit as normal by raising KeyboardInterrupt
                event.app.exit(exception=KeyboardInterrupt())

        # Initialize prompt session with command history and custom key bindings
        history_file = os.path.join(history_dir, "command_history")
        self.prompt_session = PromptSession(
            history=FileHistory(history_file), key_bindings=kb
        )

    def set_verbose(self, verbose: bool) -> None:
        """Set verbose mode.

        Args:
            verbose: Whether to enable verbose mode
        """
        self.verbose = verbose

    def start_thinking_animation(self, token_percentage: int = 0) -> threading.Thread:
        """Start the thinking animation."""
        self.thinking_event.clear()

        def animate():
            # Determine display color based on token percentage
            if token_percentage > 80:
                color = "red"
            elif token_percentage > 50:
                color = "yellow"
            else:
                color = "green"

            # Show special intro message in verbose mode
            if self.verbose:
                self.console.print(
                    "[bold cyan]🤔 VERBOSE MODE: Waiting for model to respond[/]",
                    highlight=False,
                )
                self.console.print(
                    "[dim]Complete model reasoning will be shown with the response[/]",
                    highlight=False,
                )

            start_time = time.time()
            with Live(
                self.thinking_spinner, refresh_per_second=10, console=self.console
            ) as live:
                while not self.thinking_event.is_set():
                    elapsed_seconds = int(time.time() - start_time)
                    if token_percentage > 0:
                        context_info = f"({token_percentage}% context used)"
                        thinking_text = f"[cyan]Thinking[/] [dim {color}]{context_info}[/] [{elapsed_seconds}s]"
                    else:
                        thinking_text = f"[cyan]Thinking[/] [{elapsed_seconds}s]"

                    spinner = Spinner("dots2", text=thinking_text)
                    live.update(spinner)
                    time.sleep(0.1)

        thread = threading.Thread(target=animate, daemon=True)
        thread.start()
        return thread

    def stop_thinking_animation(self) -> None:
        """Stop the thinking animation."""
        self.thinking_event.set()

    def get_user_input(self) -> str:
        """Get user input with history navigation support.

        Returns:
            The user input string
        """
        return self.prompt_session.prompt("\n> ")

    def print_content(
        self,
        content: str,
        style: str = None,
        panel: bool = False,
        title: str = None,
        border_style: str = None,
    ) -> None:
        """Print content with optional styling and panel."""
        renderable = content
        if isinstance(content, str):
            renderable = Markdown(content) if not style else Text(content, style=style)

        if panel:
            renderable = Panel(
                renderable,
                title=title,
                border_style=border_style or "none",
                expand=False,
            )

        self.console.print(renderable)

    def print_markdown(self, content: str) -> None:
        """Print markdown-formatted content."""
        self.print_content(content)

    def print_assistant_response(self, content: str) -> None:
        """Print an assistant's response."""
        # If verbose, show "THINKING" part in a separate panel if present
        if self.verbose and "THINKING:" in content:
            parts = content.split("\n\n", 1)
            if len(parts) == 2 and parts[0].startswith("THINKING:"):
                thinking, response = parts
                self.print_content(
                    thinking,
                    panel=True,
                    title="[bold cyan]Thinking Process[/]",
                    border_style="cyan",
                )
                self.print_markdown(response)
            else:
                self.print_markdown(content)
        else:
            self.print_markdown(content)

    def print_tool_call(self, tool_name: str, arguments: dict) -> None:
        """Print a tool call notification."""
        args_str = ", ".join(f"{k}={v}" for k, v in arguments.items())
        self.print_content(f"> Running {tool_name}({args_str})", style="dim yellow")

    def print_error(self, message: str) -> None:
        """Print an error message."""
        self.print_content(f"Error: {message}", style="bold red")

    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        self.print_content(f"Warning: {message}", style="bold yellow")

    def print_success(self, message: str) -> None:
        """Print a success message."""
        self.print_content(f"✓ {message}", style="bold green")

    def print_help(self) -> None:
        """Print help information."""
        help_text = """
# Code Ally Commands

- `/help` - Show this help message
- `/clear` - Clear the conversation history
- `/config` - Show or update configuration settings
- `/debug` - Toggle debug mode
- `/dump` - Dump the conversation history to file
- `/compact` - Compact the conversation to reduce context size
- `/trust` - Show trust status for tools
- `/verbose` - Toggle verbose mode (show model thinking)

Type a message to chat with the AI assistant.
Use up/down arrow keys to navigate through command history.
"""
        self.print_markdown(help_text)
