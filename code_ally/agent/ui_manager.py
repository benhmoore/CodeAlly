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
        self.active_live_display = None  # Track the current active Live display

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
        
        # Interactive planning state
        self.current_interactive_plan = None
        self.current_interactive_plan_tasks = []
        
        # Add these attributes
        self.active_live_display = None
        self.plan_panel = None  # Store the entire panel
        self.plan_tasks_table = None
        self.plan_panel_group = None  # This is important

    def set_verbose(self, verbose: bool) -> None:
        """Set verbose mode.

        Args:
            verbose: Whether to enable verbose mode
        """
        self.verbose = verbose

    def start_thinking_animation(self, token_percentage: int = 0) -> threading.Thread:
        """Start the thinking animation."""
        # Make sure any existing live display is stopped
        if self.active_live_display:
            self.active_live_display.stop()
            self.active_live_display = None

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
            try:
                with Live(
                    self.thinking_spinner, refresh_per_second=10, console=self.console
                ) as live:
                    self.active_live_display = live  # Store reference to current live display
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
            finally:
                # Clear the reference when done
                if self.active_live_display:
                    self.active_live_display = None

        thread = threading.Thread(target=animate, daemon=True)
        thread.start()
        return thread

    def stop_thinking_animation(self) -> None:
        """Stop the thinking animation."""
        self.thinking_event.set()
        # Make sure the live display reference is cleared in the animation thread

    def get_user_input(self) -> str:
        """Get user input with history navigation support.

        Returns:
            The user input string
        """
        # prompt_toolkit will raise KeyboardInterrupt if Ctrl+C is pressed
        # when the input buffer is empty, which is caught by Agent.run_conversation
        return self.prompt_session.prompt("\n> ")

    def print_content(
        self,
        content: str,
        style: str = None,
        panel: bool = False,
        title: str = None,
        border_style: str = None,
        use_markdown: bool = False
    ) -> None:
        """Print content with optional styling and panel."""
        renderable = content
        if isinstance(content, str):
            if use_markdown:
                renderable = Markdown(content)
            elif style:
                # Use Rich's Text object for styled content
                renderable = Text(content, style=style)
            else:
                # Check if the content has Rich formatting tags
                if "[" in content and "]" in content and "/]" in content:
                    # Let Rich render the formatting
                    renderable = content
                else:
                    # For plain text with no Rich tags
                    renderable = Text(content)

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
        self.print_content(content, use_markdown=True)

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

    def confirm(self, prompt: str, default: bool = True) -> bool:
        """Ask the user for confirmation.
        
        Args:
            prompt: The confirmation prompt
            default: Default return value if user just presses Enter
            
        Returns:
            The user's confirmation choice
        """
        prompt_text = f"{prompt} (Y/n)" if default else f"{prompt} (y/N)"
        response = self.prompt_session.prompt(f"\n{prompt_text} > ")
        
        # Handle empty response
        if not response:
            return default
            
        # Process user input
        response = response.strip().lower()
        if response in ('y', 'yes'):
            return True
        elif response in ('n', 'no'):
            return False
        else:
            # For invalid responses, fall back to default
            self.print_warning(f"Invalid response '{response}'. Using default: {default}")
            return default
    
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

    # ----- Interactive Planning UI Methods -----
    
    def display_interactive_plan_started(self, name: str, description: str) -> None:
        """Start displaying an interactive plan with a live-updating panel."""
        # Make sure any existing live display is stopped
        if self.active_live_display:
            self.active_live_display.stop()
            self.active_live_display = None

        # Save plan info
        self.current_interactive_plan = {
            "name": name,
            "description": description
        }
        self.current_interactive_plan_tasks = []

        
        # Create the initial table for tasks
        from rich.table import Table
        self.plan_tasks_table = Table(box=None, expand=False, show_header=True)
        
        # We'll show a full set of columns so the single panel can carry
        # everything from creation to finalization:
        self.plan_tasks_table.add_column("#", style="dim", width=3)
        self.plan_tasks_table.add_column("Task ID", style="cyan")
        self.plan_tasks_table.add_column("Tool", style="green")
        self.plan_tasks_table.add_column("Description", style="yellow")
        self.plan_tasks_table.add_column("Dependencies", style="blue")
        self.plan_tasks_table.add_column("Conditional", style="magenta")
        
        # Create the header text
        from rich.text import Text
        from rich.console import Group
        
        header_content = Text.assemble(
            Text(f"Name: ", style="bold"), Text(name), Text("\n"),
            Text(f"Description: ", style="bold"), Text(description), Text("\n\n"),
            Text("Tasks:", style="bold cyan")
        )
        
        # Group the header and tasks table - store this separately
        self.plan_panel_group = Group(header_content, self.plan_tasks_table)
        
        # Create the panel - use the group
        from rich.panel import Panel
        title_text = Text("📋 Creating Task Plan", style="bold blue")
        self.plan_panel = Panel(
            self.plan_panel_group,
            title=title_text,
            border_style="blue",
            expand=False
        )
        
        # Start the live display with the panel
        from rich.live import Live
        live = Live(self.plan_panel, console=self.console, refresh_per_second=4)
        self.active_live_display = live
        live.start()

    def display_interactive_plan_task_added(self, task_index: int, task_id: str, description: str) -> None:
        """Update the plan panel with a new task."""
        self.current_interactive_plan_tasks.append(
            {
                "index": task_index,
                "id": task_id,
                "description": description
            }
        )

        # We'll rely on the 'tmp_tool', 'tmp_depends', 'tmp_cond' that we store in the TaskPlanner
        # In a more ideal design, you'd pass them in as direct arguments to this function.
        tool_name = getattr(self, "tmp_tool", "???")
        depends_on = getattr(self, "tmp_depends", [])
        condition_str = getattr(self, "tmp_cond", "No")

        depends_txt = ", ".join(depends_on) if depends_on else "—"

        self.plan_tasks_table.add_row(
            str(task_index),
            task_id,
            tool_name,
            description,
            depends_txt,
            condition_str,
        )

        if self.active_live_display:
            self.active_live_display.update(self.plan_panel)

    def confirm_interactive_plan(self, plan_name: str) -> bool:
        """Finalize the plan display and ask for confirmation."""
        # Stop the live display
        if self.active_live_display:
            self.active_live_display.stop()
            self.active_live_display = None
        
        # Ask for confirmation
        return self.confirm(f"Execute the task plan '{plan_name}'?", default=True)