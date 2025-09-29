"""Interactive REPL interface using prompt_toolkit."""
import asyncio
import re
import importlib
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
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
from .auto_suggest import SlashCommandAutoSuggest
from ..generation import PremiseGenerator, TreatmentGenerator, ChapterGenerator, ProseGenerator
from ..generation.taxonomies import TaxonomyLoader, PremiseAnalyzer, PremiseHistory
from ..utils.logging import setup_logging, get_logger


class InteractiveSession:
    """Interactive REPL session for AgenticAuthor."""

    def __init__(self, project_path: Optional[Path] = None, logger=None):
        """
        Initialize interactive session.

        Args:
            project_path: Optional path to existing project
            logger: Optional SessionLogger instance
        """
        self.settings = get_settings()
        self.console = Console()
        self.client: Optional[OpenRouterClient] = None
        self.project: Optional[Project] = None
        self.story: Optional[Story] = None
        self.git: Optional[GitManager] = None
        self.running = False

        # Use provided logger or setup basic logging
        self.session_logger = logger
        self.logger = setup_logging(level="DEBUG")
        self.logger.info("InteractiveSession initialized")

        # Log initialization
        if self.session_logger:
            self.session_logger.log("InteractiveSession initialized", "INFO")

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
            'reload': self.reload_modules,
            'logs': self.show_logs,
        }

        # Cache for model IDs (populated when client is initialized)
        self._cached_model_ids = []

        # Initialize taxonomy loader for genre support
        self.taxonomy_loader = TaxonomyLoader()
        self.premise_history = PremiseHistory()

        # Setup prompt session (after commands are defined)
        self.session = self._create_prompt_session()

        # Initialize project if provided
        if project_path:
            self.load_project(project_path)

    def _create_prompt_session(self) -> PromptSession:
        """Create configured prompt session."""
        # Create command completer with descriptions and model provider
        command_descriptions = create_command_descriptions()

        # Model provider lambda that returns cached model IDs
        model_provider = lambda: self._cached_model_ids

        # Genre provider lambda that returns available genres
        genre_provider = lambda: self.taxonomy_loader.get_available_genres()

        completer = SlashCommandCompleter(command_descriptions, model_provider, genre_provider)

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
            """Just insert / without starting completion (since complete_while_typing=False)."""
            event.current_buffer.insert_text('/')

        @kb.add('tab')
        def _(event):
            """Handle tab completion - accept suggestion or complete."""
            buff = event.current_buffer

            # If there's an auto-suggestion, accept it
            if buff.suggestion and buff.suggestion.text:
                buff.insert_text(buff.suggestion.text)
                return

            # If we're already in completion state, cycle through
            if buff.complete_state:
                buff.complete_next()
            else:
                # Get current text to check for completions
                text = buff.text

                # Start completion to get the list
                buff.start_completion()

                # If there's only one completion, insert it directly and cancel menu
                if buff.complete_state and len(buff.complete_state.completions) == 1:
                    completion = buff.complete_state.completions[0]
                    # Insert the completion text
                    buff.insert_text(completion.text)
                    # Cancel the completion menu
                    buff.cancel_completion()

        # Create session
        history_file = Path.home() / '.agentic' / 'history'
        history_file.parent.mkdir(exist_ok=True)

        # Create history and custom auto-suggest
        history = FileHistory(str(history_file))
        auto_suggest = SlashCommandAutoSuggest(history)

        return PromptSession(
            history=history,
            auto_suggest=auto_suggest,
            completer=completer,
            style=style,
            multiline=False,
            mouse_support=True,
            complete_while_typing=False,  # Only complete on Tab
            key_bindings=kb,
            enable_history_search=True
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

        # Clear screen on startup
        self.console.clear()

        # Initialize API client
        try:
            self.client = OpenRouterClient(console=self.console)
            await self.client.ensure_session()

            # Populate model cache for autocomplete
            try:
                models = await self.client.discover_models()
                self._cached_model_ids = [m.id for m in models]
            except Exception:
                # If we can't get models, just continue without autocomplete
                pass

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
                self.logger.debug(f"User input: {user_input}")

                if not user_input.strip():
                    continue

                # Process input
                await self.process_input(user_input.strip())

            except KeyboardInterrupt:
                self.logger.debug("KeyboardInterrupt caught")
                continue
            except EOFError:
                self.logger.info("EOFError - exiting")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                self.console.print(f"[red]Error: {e}[/red]")

        # Cleanup
        if self.client:
            await self.client.close()

    def _build_prompt(self) -> HTML:
        """Build the prompt string."""
        return HTML('<prompt>></prompt> ')

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
        self.logger.debug(f"Processing input: {user_input}")

        # Log user input
        if self.session_logger:
            self.session_logger.log(f"USER INPUT: {user_input}", "INFO")

        # Check if it's a slash command
        if user_input.startswith('/'):
            # Command format: /command args
            parts = user_input[1:].split(None, 1)
            command = parts[0] if parts else ''
            args = parts[1] if len(parts) > 1 else ''
            self.logger.debug(f"Parsed command: {command}, args: {args}")

            if command in self.commands:
                await self._run_command(command, args)
            else:
                error_msg = f"Unknown command: /{command}"
                if self.session_logger:
                    self.session_logger.log(error_msg, "WARNING")
                self.console.print(f"[red]{error_msg}[/red]")
                self.console.print("[dim]Type /help for available commands[/dim]")

        else:
            # Natural language feedback - send to iteration system
            if not self.project:
                msg = "No project loaded. Use /new or /open first."
                if self.session_logger:
                    self.session_logger.log(msg, "WARNING")
                self.console.print(f"[yellow]{msg}[/yellow]")
            else:
                await self.process_feedback(user_input)

    async def _run_command(self, command: str, args: str):
        """Run a command handler."""
        handler = self.commands[command]

        # Log command execution
        if self.session_logger:
            self.session_logger.log_command(command, args)

        try:
            # Check if handler is async
            if asyncio.iscoroutinefunction(handler):
                result = await handler(args)
            else:
                result = handler(args)

            # Log successful command
            if self.session_logger:
                self.session_logger.log_command(command, args, result=result)

        except Exception as e:
            # Log command error
            if self.session_logger:
                self.session_logger.log_command(command, args, error=str(e))
                self.session_logger.log_error(e, f"Command failed: /{command}")
            raise

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
            ("/reload", "Reload modules (development)"),
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
            projects = []
            for p in self.settings.books_dir.glob("*"):
                if (p / "project.yaml").exists():
                    projects.append(p)

            if not projects:
                self.console.print("[yellow]No projects found[/yellow]")
                self.console.print("[dim]Create one with /new[/dim]")
                return

            # Display projects with inline selection
            self.console.print("\n[cyan]Available projects:[/cyan]")

            # Collect project info
            project_list = []
            for i, p in enumerate(projects, 1):
                try:
                    project = Project(p)
                    info_parts = []
                    if project.metadata:
                        if project.metadata.genre:
                            info_parts.append(f"[dim]{project.metadata.genre}[/dim]")
                        if project.metadata.word_count:
                            info_parts.append(f"[dim]{project.metadata.word_count:,} words[/dim]")
                        if project.metadata.updated_at:
                            days_ago = (datetime.now(timezone.utc) - project.metadata.updated_at).days
                            if days_ago == 0:
                                info_parts.append("[dim]updated today[/dim]")
                            elif days_ago == 1:
                                info_parts.append("[dim]updated yesterday[/dim]")
                            else:
                                info_parts.append(f"[dim]updated {days_ago} days ago[/dim]")

                    description = " • ".join(info_parts) if info_parts else ""
                    project_list.append((p, description))
                except:
                    project_list.append((p, ""))

            # Display numbered list
            for i, (project_path, description) in enumerate(project_list, 1):
                if description:
                    self.console.print(f"  {i}. [green]{project_path.name}[/green] {description}")
                else:
                    self.console.print(f"  {i}. [green]{project_path.name}[/green]")

            # Prompt for selection
            self.console.print("\n[dim]Enter number to select, or press Enter to cancel:[/dim]")
            try:
                choice = self.console.input("> ")
                if not choice:
                    return

                choice_num = int(choice)
                if 1 <= choice_num <= len(project_list):
                    path = project_list[choice_num - 1][0]
                else:
                    self.console.print("[red]Invalid selection[/red]")
                    return
            except ValueError:
                self.console.print("[red]Please enter a number[/red]")
                return
            except (KeyboardInterrupt, EOFError):
                return
        else:
            # If argument provided, use it directly
            if (self.settings.books_dir / args).exists():
                path = self.settings.books_dir / args
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
            self.console.print("[dim]Tip: Use /model <search> to change model (e.g., /model opus)[/dim]")
            return

        # Get available models
        if not self.client:
            self.console.print("[red]API client not initialized[/red]")
            return

        models = await self.client.discover_models()

        # Try exact match first
        exact_match = None
        for model in models:
            if model.id == args:
                exact_match = model
                break

        if exact_match:
            # Direct match found
            selected_model = exact_match.id
        else:
            # Try fuzzy search
            search_term = args.lower()
            matches = []

            for model in models:
                model_lower = model.id.lower()
                # Check if search term is in model ID
                if search_term in model_lower:
                    # Calculate relevance score (prefer matches at start or after /)
                    score = 0
                    if model_lower.startswith(search_term):
                        score = 3
                    elif '/' + search_term in model_lower:
                        score = 2
                    else:
                        score = 1
                    matches.append((model, score))

            # Sort alphabetically by model ID
            matches.sort(key=lambda x: x[0].id.lower())

            if not matches:
                self.console.print(f"[red]No models found matching '{args}'[/red]")
                self.console.print("[dim]Try: /models to see all available models[/dim]")
                return

            if len(matches) == 1:
                # Single match - use it
                selected_model = matches[0][0].id
                self.console.print(f"[dim]Found: {selected_model}[/dim]")
            else:
                # Multiple matches - show selection menu
                self.console.print(f"\n[yellow]Multiple models found matching '{args}':[/yellow]\n")

                # Show numbered list with details
                for i, (model, _) in enumerate(matches[:9], 1):
                    price = f"${model.cost_per_1k_tokens * 1000:.2f}/1M"
                    if model.is_free:
                        price = "Free"

                    # Highlight current model
                    if model.id == self.settings.active_model:
                        self.console.print(f"  [cyan]{i}[/cyan]. [bold cyan]{model.id}[/bold cyan] [{price}] [dim]← current[/dim]")
                    else:
                        self.console.print(f"  [cyan]{i}[/cyan]. {model.id} [dim][{price}][/dim]")

                # Get user selection
                try:
                    self.console.print("\n[bold]Select model[/bold] (1-{}) or [dim]Enter to cancel[/dim]: ".format(len(matches[:9])), end="")

                    # Use simple input for selection
                    import sys
                    selection = input().strip()

                    if not selection:
                        self.console.print("[dim]Cancelled[/dim]")
                        return

                    index = int(selection) - 1
                    if 0 <= index < len(matches[:9]):
                        selected_model = matches[index][0].id
                    else:
                        self.console.print("[red]Invalid selection[/red]")
                        return

                except (ValueError, EOFError, KeyboardInterrupt):
                    self.console.print("[dim]Cancelled[/dim]")
                    return

        # Update model
        self.settings.set_model(selected_model)
        self.console.print(f"[green]✓ Model changed to: {selected_model}[/green]")

        # Show model details
        for model in models:
            if model.id == selected_model:
                price = f"${model.cost_per_1k_tokens * 1000:.2f}/1M"
                if model.is_free:
                    price = "Free"
                self.console.print(f"[dim]  Context: {model.context_length:,} tokens | Price: {price}[/dim]")
                break

        # Update project metadata if loaded
        if self.project and self.project.metadata:
            self.project.metadata.model = selected_model
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

            # Group models by provider
            grouped = {}
            for model in models:
                provider = model.id.split('/')[0] if '/' in model.id else 'other'
                if provider not in grouped:
                    grouped[provider] = []
                grouped[provider].append(model)

            # Sort each group by price
            for provider in grouped:
                grouped[provider].sort(key=lambda m: m.cost_per_1k_tokens)

            # Create table
            table = Table(title="Available Models", show_lines=True)
            table.add_column("Provider", style="magenta", width=12)
            table.add_column("Model", style="cyan", width=30)
            table.add_column("Context", justify="right", width=12)
            table.add_column("$/1M Input", justify="right", style="green", width=12)
            table.add_column("$/1M Output", justify="right", style="yellow", width=12)

            # Display all models grouped by provider
            for provider in sorted(grouped.keys()):
                provider_models = grouped[provider]
                for i, model in enumerate(provider_models):
                    # Show provider name only on first row
                    provider_display = provider.capitalize() if i == 0 else ""

                    # Convert price from per 1K to per 1M tokens
                    input_price = model.cost_per_1k_tokens * 1000
                    # Assume output is 2x input price (typical for most models)
                    output_price = model.cost_per_1k_tokens * 2000

                    # Format prices
                    if model.is_free:
                        input_str = "Free"
                        output_str = "Free"
                    else:
                        input_str = f"${input_price:.2f}"
                        output_str = f"${output_price:.2f}"

                    # Extract model name (remove provider prefix)
                    model_name = model.id.split('/')[-1] if '/' in model.id else model.id
                    # Truncate long model names
                    if len(model_name) > 28:
                        model_name = model_name[:25] + "..."

                    table.add_row(
                        provider_display,
                        model_name,
                        f"{model.context_length:,}",
                        input_str,
                        output_str
                    )

            self.console.print(table)
            self.console.print(f"\n[dim]Total models: {len(models)}[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error fetching models: {e}[/red]")

    async def generate_content(self, args: str):
        """Generate content command."""
        if not self.project:
            self.console.print("[yellow]No project loaded. Use /new or /open first.[/yellow]")
            return

        if not self.client:
            self.console.print("[red]API client not initialized[/red]")
            return

        # Parse generation type
        parts = args.strip().split(None, 1)
        if not parts:
            self.console.print("[yellow]Usage: /generate <premise|treatment|chapters|prose> [options][/yellow]")
            return

        gen_type = parts[0].lower()
        options = parts[1] if len(parts) > 1 else ""

        try:
            if gen_type == "premise":
                await self._generate_premise(options)
            elif gen_type == "treatment":
                await self._generate_treatment(options)
            elif gen_type == "chapters":
                await self._generate_chapters(options)
            elif gen_type == "prose":
                await self._generate_prose(options)
            else:
                self.console.print(f"[red]Unknown generation type: {gen_type}[/red]")
                self.console.print("[dim]Valid types: premise, treatment, chapters, prose[/dim]")
        except Exception as e:
            self.console.print(f"[red]Generation failed: {e}[/red]")

    async def _generate_premise(self, user_input: str = ""):
        """Generate story premise with enhanced genre and taxonomy support."""
        # Parse input for genre and concept
        parts = user_input.strip().split(None, 1)
        genre = None
        concept = ""

        if parts:
            # Check if first part is a genre
            normalized = self.taxonomy_loader.normalize_genre(parts[0])
            if normalized != 'general' or parts[0].lower() in ['custom', 'general']:
                genre = parts[0]
                concept = parts[1] if len(parts) > 1 else ""
            else:
                # First part is not a genre, treat all as concept
                concept = user_input

        # If no genre specified, try interactive selection
        if not genre and not concept:
            genre = await self._select_genre_interactive()
            if not genre:
                return  # User cancelled

        # Analyze the input to see if it's already a treatment
        analysis = PremiseAnalyzer.analyze(concept)

        if analysis['is_treatment']:
            self.console.print(f"[yellow]Detected full treatment ({analysis['word_count']} words)[/yellow]")
            self.console.print("[cyan]Preserving your treatment and generating parameters...[/cyan]")

            # Use the treatment as the premise
            self.project.save_premise(analysis['text'])

            # Generate only taxonomy selections
            generator = PremiseGenerator(self.client, self.project, model=self.settings.active_model)
            result = await generator.generate_taxonomy_only(
                treatment=analysis['text'],
                genre=genre or self.project.metadata.genre
            )

            if result:
                self.console.print("[green]✓ Treatment preserved with generated parameters[/green]")
                self.console.print(f"\n{analysis['text'][:500]}...\n")

                if 'selections' in result:
                    self.console.print("[dim]Generated parameters:[/dim]")
                    for category, values in result['selections'].items():
                        if isinstance(values, list):
                            values_str = ', '.join(values[:3])
                        else:
                            values_str = str(values)
                        display_name = category.replace('_', ' ').title()
                        self.console.print(f"  {display_name}: {values_str}")

        else:
            # Normal premise generation
            self.console.rule(style="dim")
            self.console.print(f"[cyan]Generating {genre or 'general'} premise...[/cyan]\n")

            generator = PremiseGenerator(self.client, self.project, model=self.settings.active_model)
            result = await generator.generate(
                user_input=concept if concept else None,
                genre=genre or self.project.metadata.genre,
                premise_history=self.premise_history
            )

            if result and 'premise' in result:
                # For premise, we need to print since JSON completion doesn't show during streaming
                self.console.print(result['premise'])
                self.console.print()  # Blank line

                # Print metadata
                if 'hook' in result:
                    self.console.print(f"[dim]Hook: {result['hook']}[/dim]")
                if 'themes' in result:
                    self.console.print(f"[dim]Themes: {', '.join(result['themes'])}[/dim]")

                self.console.print()  # Blank line
                self.console.rule(style="dim")
                self.console.print("[green]✓ Premise generated[/green]")
                self.console.print("[dim]Saved to premise.md[/dim]")

                # Add to history
                self.premise_history.add(
                    result['premise'],
                    genre or 'general',
                    result.get('selections', {})
                )
            else:
                self.console.print("[red]Failed to generate premise[/red]")

    async def _select_genre_interactive(self):
        """Interactive genre selection."""
        genres = self.taxonomy_loader.get_available_genres()

        self.console.print("\n[cyan]Select a genre:[/cyan]")
        for i, genre in enumerate(genres, 1):
            display_name = genre.replace('-', ' ').title()
            self.console.print(f"  {i:2}. {display_name}")

        self.console.print(f"  {len(genres) + 1:2}. Custom")

        try:
            choice = input("\nSelect (1-{}) or Enter to cancel: ".format(len(genres) + 1))
            if not choice:
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(genres):
                return genres[idx]
            elif idx == len(genres):
                return 'custom'
            else:
                self.console.print("[red]Invalid selection[/red]")
                return None

        except (ValueError, KeyboardInterrupt):
            return None

    async def _generate_treatment(self, options: str = ""):
        """Generate story treatment."""
        # Check for premise
        if not self.project.get_premise():
            self.console.print("[yellow]No premise found. Generating premise first...[/yellow]")
            await self._generate_premise()

        # Parse word count if provided
        target_words = 2500
        if options:
            try:
                target_words = int(options)
            except ValueError:
                pass

        # Print divider line before generation
        self.console.rule(style="dim")
        self.console.print(f"[cyan]Generating treatment ({target_words} words)...[/cyan]\n")

        generator = TreatmentGenerator(self.client, self.project)
        result = await generator.generate(target_words=target_words)

        if result:
            word_count = len(result.split())
            self.console.print()  # Blank line
            self.console.rule(style="dim")  # Divider after content
            self.console.print(f"[green]✓ Treatment generated: {word_count} words[/green]")
            self.console.print("[dim]Saved to treatment.md[/dim]")
        else:
            self.console.print("[red]Failed to generate treatment[/red]")

    async def _generate_chapters(self, options: str = ""):
        """Generate chapter outlines."""
        # Check for treatment
        if not self.project.get_treatment():
            self.console.print("[yellow]No treatment found. Generate treatment first with /generate treatment[/yellow]")
            return

        # Parse options (chapter count or word count)
        chapter_count = None
        total_words = 50000

        if options:
            parts = options.split()
            for part in parts:
                if part.isdigit():
                    num = int(part)
                    if num < 50:  # Assume it's chapter count
                        chapter_count = num
                    else:  # Assume it's word count
                        total_words = num

        self.console.rule(style="dim")
        self.console.print(f"[cyan]Generating chapter outlines...[/cyan]\n")

        generator = ChapterGenerator(self.client, self.project)
        chapters = await generator.generate(
            chapter_count=chapter_count,
            total_words=total_words
        )

        if chapters:
            # Show all chapters
            for chapter in chapters:
                self.console.print(f"Chapter {chapter.number}: {chapter.title}")
                self.console.print(f"  [dim]{chapter.summary}[/dim]")

            self.console.print()  # Blank line
            self.console.rule(style="dim")
            self.console.print(f"[green]✓ Generated {len(chapters)} chapter outlines[/green]")
            self.console.print("[dim]Saved to chapters.yaml[/dim]")
        else:
            self.console.print("[red]Failed to generate chapters[/red]")

    async def _generate_prose(self, options: str = ""):
        """Generate prose for chapters with full sequential context."""
        # Check for chapter outlines
        chapters_file = self.project.path / "chapters.yaml"
        if not chapters_file.exists():
            self.console.print("[yellow]No chapter outlines found. Generate chapters first with /generate chapters[/yellow]")
            return

        # Parse options: chapter number or "all"
        if not options:
            self.console.print("[yellow]Usage: /generate prose <chapter_number|all>[/yellow]")
            self.console.print("[dim]  Examples:[/dim]")
            self.console.print("[dim]    /generate prose 1   - Generate chapter 1 with full context[/dim]")
            self.console.print("[dim]    /generate prose all - Generate all chapters sequentially[/dim]")
            return

        generator = ProseGenerator(self.client, self.project)

        if options.lower() == "all":
            # Generate all chapters sequentially
            self.console.print(f"[cyan]Generating all chapters sequentially with full context...[/cyan]")

            try:
                results = await generator.generate_all_chapters()

                if results:
                    # Git commit
                    if self.project.git:
                        self.project.git.add()
                        self.project.git.commit(f"Generate prose for {len(results)} chapters (sequential)")

                    self.console.print(f"\n[green]✅ Successfully generated {len(results)} chapters[/green]")
                    total_words = sum(len(p.split()) for p in results.values())
                    self.console.print(f"[dim]Total word count: {total_words:,}[/dim]")
                else:
                    self.console.print("[red]No chapters were generated[/red]")

            except Exception as e:
                self.console.print(f"[red]Error generating chapters: {e}[/red]")

        else:
            # Generate single chapter
            try:
                chapter_num = int(options.split()[0])

                # Show token analysis first
                token_calc = generator.calculate_prose_context_tokens(chapter_num)

                self.console.rule(style="dim")
                self.console.print(f"[cyan]Generating prose for chapter {chapter_num}...[/cyan]")
                self.console.print(f"[dim]Mode: Sequential (Full Context)[/dim]")
                self.console.print(f"[dim]Context tokens: {token_calc['total_context_tokens']:,}[/dim]")
                self.console.print(f"[dim]Response tokens: {token_calc['response_tokens']:,}[/dim]")
                self.console.print(f"[dim]Total needed: {token_calc['total_needed']:,}[/dim]")

                self.console.print()

                result = await generator.generate_chapter(chapter_number=chapter_num)

                if result:
                    word_count = len(result.split())
                    self.console.print()  # Blank line
                    self.console.rule(style="dim")
                    self.console.print(f"[green]✓ Chapter {chapter_num} generated: {word_count} words[/green]")
                    self.console.print(f"[dim]Saved to chapters/chapter-{chapter_num:02d}.md[/dim]")

                    # Git commit
                    if self.project.git:
                        self.project.git.add()
                        self.project.git.commit(f"Generate prose for chapter {chapter_num} (sequential)")
                else:
                    self.console.print("[red]Failed to generate prose[/red]")

            except ValueError:
                self.console.print("[red]Invalid chapter number[/red]")
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")

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
            args = "status"

        parts = args.split(None, 1)
        command = parts[0].lower()

        try:
            if command == "status":
                result = self.git.status()
                if result:
                    self.console.print("[cyan]Git Status:[/cyan]")
                    self.console.print(result)
                else:
                    self.console.print("[green]Working tree clean[/green]")

            elif command == "log":
                limit = 10
                if len(parts) > 1:
                    try:
                        limit = int(parts[1])
                    except ValueError:
                        pass

                result = self.git.log(limit=limit)
                if result:
                    self.console.print(f"[cyan]Git Log (last {limit} commits):[/cyan]")
                    self.console.print(result)
                else:
                    self.console.print("[yellow]No commits yet[/yellow]")

            elif command == "diff":
                result = self.git.diff()
                if result:
                    self.console.print("[cyan]Git Diff:[/cyan]")
                    self.console.print(result)
                else:
                    self.console.print("[green]No changes[/green]")

            elif command == "add":
                self.git.add()
                self.console.print("[green]✓ All changes staged[/green]")

            elif command == "commit":
                if len(parts) > 1:
                    message = parts[1]
                    self.git.commit(message)
                    self.console.print(f"[green]✓ Committed: {message}[/green]")
                else:
                    self.console.print("[yellow]Usage: /git commit <message>[/yellow]")

            elif command == "rollback":
                steps = 1
                if len(parts) > 1:
                    try:
                        steps = int(parts[1])
                    except ValueError:
                        pass

                self.git.rollback(steps=steps)
                self.console.print(f"[green]✓ Rolled back {steps} commit(s)[/green]")

            elif command == "branch":
                if len(parts) > 1:
                    branch_name = parts[1]
                    self.git.create_branch(branch_name)
                    self.console.print(f"[green]✓ Created branch: {branch_name}[/green]")
                else:
                    # List branches
                    branches = self.git.list_branches()
                    if branches:
                        self.console.print("[cyan]Branches:[/cyan]")
                        for branch in branches:
                            self.console.print(f"  {branch}")
                    else:
                        self.console.print("[yellow]No branches found[/yellow]")

            else:
                # Fallback to generic git command
                result = self.git.run_command(args)
                if result:
                    self.console.print(result)

        except Exception as e:
            self.console.print(f"[red]Git error: {e}[/red]")

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

    def reload_modules(self, args: str = ""):
        """Reload Python modules for development (experimental)."""
        self.console.print("[yellow]Reloading modules...[/yellow]")

        # List of modules to reload
        modules_to_reload = [
            'src.generation.premise',
            'src.generation.treatment',
            'src.generation.chapters',
            'src.generation.prose',
            'src.generation.taxonomies',
            'src.cli.command_completer',
            'src.cli.auto_suggest',
            'src.models',
            'src.api.openrouter',
            'src.config',
            'src.storage.git_manager',
        ]

        reloaded = []
        for module_name in modules_to_reload:
            if module_name in sys.modules:
                try:
                    importlib.reload(sys.modules[module_name])
                    reloaded.append(module_name)
                except Exception as e:
                    self.console.print(f"[red]Failed to reload {module_name}: {e}[/red]")

        if reloaded:
            self.console.print(f"[green]Reloaded {len(reloaded)} modules:[/green]")
            for module in reloaded:
                self.console.print(f"  • {module}")

            # Re-initialize command completer with reloaded modules
            try:
                from src.cli.command_completer import create_command_descriptions
                command_descriptions = create_command_descriptions()
                # Note: Can't easily update the existing completer, would need to recreate prompt session
                self.console.print("[yellow]Note: Some changes may require restart for full effect[/yellow]")
            except Exception as e:
                self.console.print(f"[red]Error reinitializing components: {e}[/red]")
        else:
            self.console.print("[yellow]No modules were reloaded[/yellow]")

        self.console.print("[dim]For complete reload, use /exit and restart[/dim]")

    async def show_logs(self, args: str = ""):
        """Show recent log entries from session log."""
        # Parse arguments
        parts = args.split() if args else []
        lines_to_show = 50  # Default
        show_errors = False

        if parts:
            if parts[0] == "errors":
                show_errors = True
            else:
                try:
                    lines_to_show = int(parts[0])
                except ValueError:
                    pass

        # Get log file - prefer current session log
        if self.session_logger and self.session_logger.log_file_path:
            log_file = self.session_logger.log_file_path
        else:
            # Fall back to latest log in logs directory
            logs_dir = Path("./logs")
            if logs_dir.exists():
                log_files = sorted(
                    logs_dir.glob("session_*.log"),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True
                )
                log_file = log_files[0] if log_files else None
            else:
                # Try old location
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d")
                log_file = Path.home() / ".agentic" / "logs" / f"agentic_{timestamp}.log"

        if not log_file or not log_file.exists():
            self.console.print("[yellow]No log file found[/yellow]")
            return

        self.console.print(f"[cyan]Log: {log_file.name}[/cyan]\n")

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if show_errors:
                # Show only error lines
                error_lines = [l for l in lines if "[ERROR]" in l or "ERROR:" in l or "Error:" in l]
                if error_lines:
                    self.console.print(f"[red]Errors found: {len(error_lines)}[/red]\n")
                    for line in error_lines[-20:]:  # Last 20 errors
                        self.console.print(line.rstrip())
                else:
                    self.console.print("[green]No errors found in log[/green]")
            else:
                # Show last N lines
                self.console.print(f"[dim]Last {min(lines_to_show, len(lines))} lines:[/dim]\n")
                for line in lines[-lines_to_show:]:
                    # Color-code by log level
                    line_str = line.rstrip()
                    if "[ERROR]" in line_str or "ERROR:" in line_str:
                        self.console.print(f"[red]{line_str}[/red]")
                    elif "[WARNING]" in line_str or "WARNING:" in line_str:
                        self.console.print(f"[yellow]{line_str}[/yellow]")
                    elif "[INFO]" in line_str:
                        self.console.print(f"[cyan]{line_str}[/cyan]")
                    elif "[DEBUG]" in line_str:
                        self.console.print(f"[dim]{line_str}[/dim]")
                    else:
                        self.console.print(line_str)

            self.console.print(f"\n[dim]Full log: {log_file}[/dim]")
            self.console.print("[dim]Usage: /logs [lines] or /logs errors[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error reading log: {e}[/red]")