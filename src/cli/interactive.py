"""Interactive REPL interface using prompt_toolkit."""
import asyncio
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from ..config import get_settings
from ..api import OpenRouterClient
from ..models import Project, Story
from ..storage.git_manager import GitManager
from .command_completer import SlashCommandCompleter, create_command_descriptions


class InteractiveSession:
    """Interactive REPL session for AgenticAuthor."""

    def __init__(self, project_path: Optional[Path] = None):
        """
        Initialize interactive session.

        Args:
            project_path: Optional path to existing project
        """
        self.settings = get_settings()
        self.console = Console()
        self.client: Optional[OpenRouterClient] = None
        self.project: Optional[Project] = None
        self.story: Optional[Story] = None
        self.git: Optional[GitManager] = None
        self.running = False

        # Command handlers - initialize before prompt session
        self.commands = {
            'help': self.show_help,
            'exit': self.exit_session,
            'quit': self.exit_session,
            'new': self.new_project,
            'open': self.open_project,
            'status': self.show_status,
            'model': self.change_model,
            'models': self.list_models,
            'generate': self.generate_content,
            'iterate': self.iterate_content,
            'analyze': self.analyze_story,
            'export': self.export_story,
            'git': self.git_command,
            'config': self.show_config,
            'clear': self.clear_screen,
        }

        # Setup prompt session (after commands are defined)
        self.session = self._create_prompt_session()

        # Initialize project if provided
        if project_path:
            self.load_project(project_path)

    def _create_prompt_session(self) -> PromptSession:
        """Create configured prompt session."""
        # Create command completer with descriptions
        command_descriptions = create_command_descriptions()
        completer = SlashCommandCompleter(command_descriptions)

        # Custom style
        style = Style.from_dict({
            'prompt': '#00aa00 bold',
            'project': '#0088ff',
            # Completion menu styling
            'completion-menu': 'bg:#1a1a1a #ffffff',
            'completion-menu.completion': '',
            'completion-menu.completion.current': 'bg:#003d7a #ffffff',
            'completion-menu.meta': '#999999',
            'completion-menu.meta.current': '#ffffff',
        })

        # Key bindings
        kb = KeyBindings()

        @kb.add('/')
        def _(event):
            """Auto-show completions when / is typed."""
            event.current_buffer.insert_text('/')
            event.current_buffer.start_completion()

        # Create session
        history_file = Path.home() / '.agentic' / 'history'
        history_file.parent.mkdir(exist_ok=True)

        return PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=completer,
            style=style,
            multiline=False,
            mouse_support=True,
            complete_while_typing=True,
            key_bindings=kb
        )

    def load_project(self, path: Path):
        """Load a project from path."""
        try:
            self.project = Project(path)
            if not self.project.is_valid:
                self.console.print(f"[red]Invalid project at {path}[/red]")
                self.project = None
                return

            # Load story data
            self.story = Story()
            if premise := self.project.get_premise():
                self.story.premise = premise
            if treatment := self.project.get_treatment():
                self.story.treatment = treatment

            # Initialize git manager
            self.git = GitManager(self.project.path)
            if not self.project.is_git_repo:
                self.git.init()

            self.console.print(f"[green]Loaded project: {self.project.name}[/green]")

        except Exception as e:
            self.console.print(f"[red]Error loading project: {e}[/red]")
            self.project = None

    async def run(self):
        """Run the interactive session."""
        self.running = True

        # Initialize API client
        try:
            self.client = OpenRouterClient(console=self.console)
            await self.client.ensure_session()
        except Exception as e:
            self.console.print(f"[red]Failed to initialize API client: {e}[/red]")
            self.console.print("[yellow]Please check your OPENROUTER_API_KEY[/yellow]")
            return

        # Show welcome message
        self._show_welcome()

        # Main REPL loop
        while self.running:
            try:
                # Build prompt
                prompt = self._build_prompt()

                # Get user input
                user_input = await self.session.prompt_async(prompt)

                if not user_input.strip():
                    continue

                # Process input
                await self.process_input(user_input.strip())

            except KeyboardInterrupt:
                continue
            except EOFError:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")

        # Cleanup
        if self.client:
            await self.client.close()

    def _build_prompt(self) -> HTML:
        """Build the prompt string."""
        parts = []

        if self.project:
            parts.append(f'<project>{self.project.name}</project>')

        if self.settings.current_model:
            model_name = self.settings.current_model.split('/')[-1][:15]
            parts.append(f'<b>{model_name}</b>')

        prompt_str = ' '.join(parts) if parts else 'agentic'
        return HTML(f'<prompt>{prompt_str}></prompt> <b>></b> ')

    def _show_welcome(self):
        """Show welcome message."""
        panel = Panel(
            "[bold cyan]AgenticAuthor[/bold cyan]\n"
            "AI-powered iterative book generation\n\n"
            "Commands start with [yellow]/[/yellow]\n"
            "Type [yellow]/[/yellow] to see available commands\n"
            "Type [yellow]/help[/yellow] for command details\n"
            "Type [yellow]/new[/yellow] to create a project\n"
            "Type [yellow]/open[/yellow] to open a project\n\n"
            "Or just start typing to iterate with AI!",
            title="Welcome",
            expand=False
        )
        self.console.print(panel)

    async def process_input(self, user_input: str):
        """
        Process user input - either command or natural language.

        Args:
            user_input: User's input string
        """
        # Check if it's a slash command
        if user_input.startswith('/'):
            # Command format: /command args
            parts = user_input[1:].split(None, 1)
            command = parts[0] if parts else ''
            args = parts[1] if len(parts) > 1 else ''

            if command in self.commands:
                await self._run_command(command, args)
            else:
                self.console.print(f"[red]Unknown command: /{command}[/red]")
                self.console.print("[dim]Type /help for available commands[/dim]")

        else:
            # Natural language feedback - send to iteration system
            if not self.project:
                self.console.print(
                    "[yellow]No project loaded. Use /new or /open first.[/yellow]"
                )
            else:
                await self.process_feedback(user_input)

    async def _run_command(self, command: str, args: str):
        """Run a command handler."""
        handler = self.commands[command]

        # Check if handler is async
        if asyncio.iscoroutinefunction(handler):
            await handler(args)
        else:
            handler(args)

    async def process_feedback(self, feedback: str):
        """
        Process natural language feedback.

        Args:
            feedback: User's feedback text
        """
        self.console.print("[cyan]Processing your feedback...[/cyan]")

        # This will be implemented with the iteration system
        # For now, just echo
        self.console.print(f"[dim]Feedback: {feedback}[/dim]")
        self.console.print("[yellow]Iteration system not yet implemented[/yellow]")

    def show_help(self, args: str = ""):
        """Show help information."""
        if args:
            # Show help for specific command
            if args in self.commands:
                cmd_info = create_command_descriptions().get(args, {})
                self.console.print(f"\n[cyan]/{args}[/cyan]")
                self.console.print(f"  {cmd_info.get('description', 'No description')}")
                self.console.print(f"  [dim]Usage: {cmd_info.get('usage', '/' + args)}[/dim]\n")
            else:
                self.console.print(f"[red]Unknown command: /{args}[/red]")
            return

        # Show all commands
        table = Table(title="Commands", show_header=True)
        table.add_column("Command", style="cyan")
        table.add_column("Description")

        commands = [
            ("/help", "Show this help message"),
            ("/new [name]", "Create new project"),
            ("/open [path]", "Open existing project"),
            ("/status", "Show project status"),
            ("/model [name]", "Change or show current model"),
            ("/models", "List available models"),
            ("/generate <type>", "Generate content (premise/treatment/chapters/prose)"),
            ("/iterate <text>", "Iterate with feedback"),
            ("/analyze [type]", "Run story analysis"),
            ("/export [format]", "Export story"),
            ("/git <command>", "Run git command"),
            ("/config", "Show configuration"),
            ("/clear", "Clear screen"),
            ("/exit or /quit", "Exit the session"),
        ]

        for cmd, desc in commands:
            table.add_row(cmd, desc)

        self.console.print(table)
        self.console.print("\n[dim]Type / to see command completions[/dim]")
        self.console.print("[dim]Or just type natural language to iterate with AI![/dim]")

    def exit_session(self, args: str = ""):
        """Exit the interactive session."""
        if self.project:
            self.console.print(f"[dim]Saving {self.project.name}...[/dim]")
            if self.project.metadata:
                self.project.save_metadata()

        self.console.print("[cyan]Goodbye![/cyan]")
        self.running = False

    def new_project(self, args: str = ""):
        """Create a new project."""
        name = args.strip() or self.console.input("Project name: ")

        if not name:
            self.console.print("[red]Project name required[/red]")
            return

        # Create project directory
        project_dir = self.settings.books_dir / name
        if project_dir.exists():
            self.console.print(f"[red]Project '{name}' already exists[/red]")
            return

        try:
            # Create project
            self.project = Project.create(
                project_dir,
                name=name,
                model=self.settings.active_model
            )

            # Initialize git
            self.git = GitManager(self.project.path)
            self.git.init()
            self.git.commit("Initial project creation")

            # Initialize story
            self.story = Story()

            self.console.print(f"[green]Created project: {name}[/green]")
            self.console.print(f"[dim]Location: {project_dir}[/dim]")

        except Exception as e:
            self.console.print(f"[red]Failed to create project: {e}[/red]")

    def open_project(self, args: str = ""):
        """Open an existing project."""
        if not args:
            # List available projects
            projects = list(self.settings.books_dir.glob("*"))
            if not projects:
                self.console.print("[yellow]No projects found[/yellow]")
                self.console.print("[dim]Create one with /new[/dim]")
                return

            self.console.print("[cyan]Available projects:[/cyan]")
            for p in projects:
                if (p / "project.yaml").exists():
                    self.console.print(f"  - {p.name}")

            name = self.console.input("Project name: ")
            if not name:
                return

            path = self.settings.books_dir / name
        else:
            path = Path(args).expanduser().resolve()

        self.load_project(path)

    def show_status(self, args: str = ""):
        """Show current project status."""
        if not self.project:
            self.console.print("[yellow]No project loaded[/yellow]")
            return

        # Create status table
        table = Table(title=f"Project: {self.project.name}", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        # Add project info
        if self.project.metadata:
            table.add_row("Created", str(self.project.metadata.created_at)[:19])
            table.add_row("Updated", str(self.project.metadata.updated_at)[:19])
            table.add_row("Genre", self.project.metadata.genre or "Not set")
            table.add_row("Model", self.project.metadata.model or "Not set")
            table.add_row("Words", str(self.project.metadata.word_count))
            table.add_row("Chapters", str(self.project.metadata.chapter_count))
            table.add_row("Status", self.project.metadata.status)

        # Check what exists
        has_premise = self.project.premise_file.exists()
        has_treatment = self.project.treatment_file.exists()
        has_outlines = self.project.chapters_file.exists()
        num_chapters = len(self.project.list_chapters())

        table.add_row("", "")  # Separator
        table.add_row("Premise", "✓" if has_premise else "✗")
        table.add_row("Treatment", "✓" if has_treatment else "✗")
        table.add_row("Outlines", "✓" if has_outlines else "✗")
        table.add_row("Prose Chapters", str(num_chapters))

        self.console.print(table)

        # Show git status if available
        if self.git and self.project.is_git_repo:
            status = self.git.status()
            if status:
                self.console.print("\n[cyan]Git Status:[/cyan]")
                self.console.print(f"[dim]{status}[/dim]")

    async def change_model(self, args: str = ""):
        """Change the current model."""
        if not args:
            # Show current model
            current = self.settings.active_model
            self.console.print(f"Current model: [cyan]{current}[/cyan]")
            return

        # Validate model exists
        if self.client:
            models = await self.client.discover_models()
            model_ids = [m.id for m in models]

            if args not in model_ids:
                # Try partial match
                matches = [m for m in model_ids if args.lower() in m.lower()]
                if matches:
                    if len(matches) == 1:
                        args = matches[0]
                    else:
                        self.console.print("[yellow]Multiple matches:[/yellow]")
                        for m in matches[:5]:
                            self.console.print(f"  - {m}")
                        return
                else:
                    self.console.print(f"[red]Model not found: {args}[/red]")
                    return

        # Update model
        self.settings.set_model(args)
        self.console.print(f"[green]Model changed to: {args}[/green]")

        # Update project metadata if loaded
        if self.project and self.project.metadata:
            self.project.metadata.model = args
            self.project.save_metadata()

    async def list_models(self, args: str = ""):
        """List available models."""
        if not self.client:
            self.console.print("[red]API client not initialized[/red]")
            return

        self.console.print("[cyan]Fetching available models...[/cyan]")

        try:
            models = await self.client.discover_models()

            # Filter by search term if provided
            if args:
                search = args.lower()
                models = [m for m in models if search in m.id.lower() or
                         (m.name and search in m.name.lower())]

            if not models:
                self.console.print("[yellow]No models found[/yellow]")
                return

            # Create table
            table = Table(title="Available Models")
            table.add_column("ID", style="cyan")
            table.add_column("Context", justify="right")
            table.add_column("Price/1K", justify="right")

            # Sort by price
            models.sort(key=lambda m: m.cost_per_1k_tokens)

            # Show top models
            for model in models[:20]:
                price = f"${model.cost_per_1k_tokens:.4f}"
                if model.is_free:
                    price = "Free"

                table.add_row(
                    model.id,
                    f"{model.context_length:,}",
                    price
                )

            self.console.print(table)

            if len(models) > 20:
                self.console.print(f"[dim]... and {len(models) - 20} more[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error fetching models: {e}[/red]")

    async def generate_content(self, args: str):
        """Generate content command."""
        self.console.print(f"[cyan]Generate: {args}[/cyan]")
        self.console.print("[yellow]Generation system not yet implemented[/yellow]")

    async def iterate_content(self, args: str):
        """Iterate content command."""
        await self.process_feedback(args)

    async def analyze_story(self, args: str):
        """Run story analysis."""
        self.console.print(f"[cyan]Analyze: {args or 'all'}[/cyan]")
        self.console.print("[yellow]Analysis system not yet implemented[/yellow]")

    async def export_story(self, args: str):
        """Export story to different format."""
        self.console.print(f"[cyan]Export to: {args or 'markdown'}[/cyan]")
        self.console.print("[yellow]Export system not yet implemented[/yellow]")

    def git_command(self, args: str):
        """Run git command."""
        if not self.project or not self.git:
            self.console.print("[yellow]No project loaded[/yellow]")
            return

        if not args:
            # Show status by default
            status = self.git.status()
            self.console.print(status)
        else:
            # Run git command
            result = self.git.run_command(args)
            self.console.print(result)

    def show_config(self, args: str = ""):
        """Show current configuration."""
        table = Table(title="Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value")

        table.add_row("API Key", f"{self.settings.openrouter_api_key[:10]}...")
        table.add_row("Base URL", self.settings.openrouter_base_url)
        table.add_row("Books Dir", str(self.settings.books_dir))
        table.add_row("Default Model", self.settings.default_model)
        table.add_row("Current Model", self.settings.active_model)
        table.add_row("Auto Commit", str(self.settings.auto_commit))
        table.add_row("Streaming", str(self.settings.streaming_output))

        self.console.print(table)

    def clear_screen(self, args: str = ""):
        """Clear the screen."""
        self.console.clear()