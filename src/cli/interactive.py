"""Interactive REPL interface using prompt_toolkit."""
import asyncio
import json
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

from ..config import get_settings
from ..api import OpenRouterClient
from ..models import Project
from ..storage.git_manager import GitManager
from .command_completer import SlashCommandCompleter, create_command_descriptions
from .auto_suggest import SlashCommandAutoSuggest
from ..generation import PremiseGenerator, TreatmentGenerator, ChapterGenerator, ProseGenerator
from ..generation.taxonomies import TaxonomyLoader, PremiseAnalyzer, PremiseHistory
from ..generation.analysis import AnalysisCoordinator
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
        self.git: Optional[GitManager] = None
        self.running = False
        self.iteration_target: Optional[str] = None  # Current iteration target (premise, treatment, chapters, prose)

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
            'clone': self.clone_project,
            'status': self.show_status,
            'model': self.change_model,
            'models': self.list_models,
            'generate': self.generate_content,
            'finalize': self.finalize_content,
            'cull': self.cull_content,
            'iterate': self.iterate_command,
            'improve': self.improve_content,
            'analyze': self.analyze_story,
            'metadata': self.manage_metadata,
            'export': self.export_story,
            'copyedit': self.copyedit_story,
            'split': self.split_combined,
            'git': self.git_command,
            'config': self.show_config,
            'clear': self.clear_screen,
            'logs': self.show_logs
        }

        # Cache for model IDs (populated when client is initialized)
        self._cached_model_ids = []

        # Initialize taxonomy loader for genre support
        self.taxonomy_loader = TaxonomyLoader()
        self.premise_history = PremiseHistory()

        # Setup prompt session (after commands are defined)
        self.session = self._create_prompt_session()

        # Initialize shared git manager at books/ level
        self._init_shared_git()

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

        # Log available commands for debugging autocomplete
        self.logger.debug(f"Autocomplete: {len(command_descriptions)} commands registered: {sorted(command_descriptions.keys())}")

        # Custom style - Claude Code aesthetic
        # Using muted, professional colors similar to Claude Code
        style = Style.from_dict({
            'prompt': '#8b9bb3',  # Muted blue-gray for prompt
            'project': '#7c8ba3',  # Slightly darker blue-gray for project name
            # Completion menu styling - darker, more sophisticated
            'completion-menu': 'bg:#1c1e26 #c5cdd9',
            'completion-menu.completion': '',
            'completion-menu.completion.current': 'bg:#2d3748 #e2e8f0',
            'completion-menu.meta': '#6b7280',
            'completion-menu.meta.current': '#9ca3af',
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

        @kb.add('escape')
        def _(event):
            """Clear the current input when Escape is pressed."""
            event.current_buffer.reset()

        # Create session with project-local history
        history_file = Path('.agentic') / 'history'
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
            mouse_support=False,  # Disable to allow text selection on Mac
            complete_while_typing=False,  # Only complete on Tab
            key_bindings=kb,
            enable_history_search=True
        )

    def _init_shared_git(self):
        """Initialize shared git manager at books/ level."""
        books_dir = self.settings.books_dir
        git_dir = books_dir / ".git"

        # Initialize GitManager at books/ level
        self.git = GitManager(books_dir)

        # Initialize git repository if it doesn't exist
        if not git_dir.exists():
            self.git.init()
            self.git.commit("Initialize books repository")
            self.logger.info(f"Initialized git repository at {books_dir}")

    def _commit(self, message: str):
        """Commit changes with project name prefix.

        Args:
            message: Commit message (will be prefixed with project name)
        """
        if not self.git:
            return

        if self.project:
            prefixed_message = f"[{self.project.name}] {message}"
        else:
            prefixed_message = message

        self.git.add()
        self.git.commit(prefixed_message)

    def load_project(self, path: Path, auto_opened: bool = False):
        """Load a project from path."""
        try:
            self.project = Project(path)
            if not self.project.is_valid:
                self.console.print(f"[red]Invalid project at {path}[/red]")
                self.project = None
                return

            # Load story data
            # Save as last opened project
            self.settings.last_opened_project = self.project.name
            self.settings.save_config_file(Path('config.yaml'))

            # Display project status
            if auto_opened:
                self._print(f"[dim]Auto-opened:[/dim] [bold]{self.project.name}[/bold]")
            else:
                self._print(f"[dim]Loaded project:[/dim] [bold]{self.project.name}[/bold]")

        except Exception as e:
            self._print(f"[bold red]Error loading project:[/bold red] {self._escape_markup(e)}")
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
            except Exception as e:
                # Warn user but continue without autocomplete
                self._print(f"[dim]⚠  Warning:[/dim] Failed to fetch models: {self._escape_markup(e)}")
                self._print("[dim]Model autocomplete will not be available[/dim]")
                self._cached_model_ids = []

        except Exception as e:
            self._print(f"[bold red]Failed to initialize API client:[/bold red] {self._escape_markup(e)}")
            self._print("[dim]Please check your OPENROUTER_API_KEY[/dim]")
            return

        # Show welcome message
        self._show_welcome()

        # Auto-open last opened project if set
        if self.settings.last_opened_project and not self.project:
            last_project_path = self.settings.books_dir / self.settings.last_opened_project
            if last_project_path.exists() and (last_project_path / "project.yaml").exists():
                self.load_project(last_project_path, auto_opened=True)
            else:
                # Project no longer exists, clear from settings
                self.settings.last_opened_project = None
                self.settings.save_config_file(Path('config.yaml'))
                self._print("[dim]⚠  Last opened project no longer exists[/dim]")

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
                self._print(f"[bold red]Error:[/bold red] {self._escape_markup(e)}")

        # Cleanup
        if self.client:
            await self.client.close()

    def _build_prompt(self) -> HTML:
        """Build the prompt string."""
        return HTML('<prompt>></prompt> ')

    def _print(self, *args, **kwargs):
        """Print with 2-space left margin (Claude Code style)."""
        # Get the message
        if args:
            message = args[0]
            # Add 2-space indent if not already present and not empty line
            if message and not message.startswith('  '):
                message = '  ' + message
            self.console.print(message, *args[1:], **kwargs)
        else:
            self.console.print(*args, **kwargs)

    def _escape_markup(self, text: str) -> str:
        """
        Escape Rich markup characters in text to prevent rendering errors.

        Use this when embedding exception messages or user input in Rich markup tags.
        Rich markup like [red], [yellow], [/red] etc. in exception messages will
        cause crashes if not escaped before embedding in other markup.
        """
        from rich.markup import escape
        return escape(str(text))

    def _show_welcome(self):
        """Show welcome message."""
        self._print()
        self._print("[bold]AgenticAuthor[/bold]")
        self._print("[dim]AI-powered iterative book generation[/dim]")
        self._print()
        self._print("Quick start:")
        self._print("  [bold]/new[/bold] [dim]my-book[/dim]     Create a new project")
        self._print("  [bold]/open[/bold]              Open an existing project")
        self._print("  [bold]/help[/bold]              Show all commands")
        self._print()
        self._print("[dim]Natural language mode: Just type your feedback![/dim]")
        self._print("[dim]Type [bold]exit[/bold] or [bold]/exit[/bold] to quit[/dim]")
        self._print()

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

        # Special handling for 'exit' and 'quit' without slash
        if user_input.lower() in ['exit', 'quit']:
            await self._run_command('exit', '')
            return

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
                self._print(f"[bold red]{error_msg}[/bold red]")
                self._print("[dim]Type /help for available commands[/dim]")

        else:
            # Natural language feedback - route to iteration system
            await self.handle_iteration_feedback(user_input)

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

    def _display_diff(self, diff: str):
        """Display a unified diff with syntax highlighting."""
        for line in diff.split('\n'):
            if line.startswith('---') or line.startswith('+++'):
                # File headers
                self._print(f"[bold cyan]{line}[/bold cyan]")
            elif line.startswith('@@'):
                # Hunk headers
                self._print(f"[bold magenta]{line}[/bold magenta]")
            elif line.startswith('+'):
                # Added lines
                self._print(f"[green]{line}[/green]")
            elif line.startswith('-'):
                # Removed lines
                self._print(f"[red]{line}[/red]")
            else:
                # Context lines
                self._print(f"[dim]{line}[/dim]")

    def _ensure_git_repo(self):
        """Ensure shared git repository is initialized (no-op with shared git)."""
        # Git is now initialized at books/ level during startup
        # This method is kept for backward compatibility but does nothing
        pass

    def show_help(self, args: str = ""):
        """Show help information."""
        if args:
            # Show help for specific command
            if args in self.commands:
                cmd_info = create_command_descriptions().get(args, {})
                self._print(f"\n[bold]/{args}[/bold]")
                self._print(f"  {cmd_info.get('description', 'No description')}")
                self._print(f"  [dim]Usage: {cmd_info.get('usage', '/' + args)}[/dim]\n")
            else:
                self._print(f"[bold red]Unknown command: /{args}[/bold red]")
            return

        # Show all commands
        table = Table(title="Commands", show_header=True)
        table.add_column("Command", style="cyan")
        table.add_column("Description")

        # Get command descriptions from the completer
        cmd_descriptions = create_command_descriptions()

        # Sort commands alphabetically but put exit/quit at the end
        sorted_commands = sorted(cmd_descriptions.items(),
                                key=lambda x: (x[0] in ['exit', 'quit'], x[0]))

        for cmd_name, cmd_info in sorted_commands:
            usage = cmd_info.get('usage', f'/{cmd_name}')
            desc = cmd_info.get('description', 'No description')
            table.add_row(usage, desc)

        self._print(table)
        self._print("\n[bold]Natural Language Iteration:[/bold]")
        self._print("  1. Set target: [cyan]/iterate treatment[/cyan]")
        self._print("  2. Type feedback: [dim]Add more conflict in act 2[/dim]")
        self._print("  3. AI understands and executes automatically")
        self._print()
        self._print("[dim]Type / to see command completions[/dim]")

    def exit_session(self, args: str = ""):
        """Exit the interactive session."""
        if self.project:
            self._print(f"[dim]Saving {self.project.name}...[/dim]")
            if self.project.metadata:
                self.project.save_metadata()

        self._print("[dim]Goodbye![/dim]")
        self.running = False

    def new_project(self, args: str = ""):
        """Create a new project."""
        name = args.strip() or self.console.input("Project name: ")

        if not name:
            self._print("[bold red]Project name required[/bold red]")
            return

        # Create project directory
        project_dir = self.settings.books_dir / name
        if project_dir.exists():
            self._print(f"[bold red]Project '{name}' already exists[/bold red]")
            return

        try:
            # Create project
            self.project = Project.create(
                project_dir,
                name=name,
                model=self.settings.active_model
            )

            # Commit to shared git
            self._commit("Initial project creation")

            self._print(f"[dim]Created project:[/dim] [bold]{name}[/bold]")
            self._print(f"[dim]Location: {project_dir}[/dim]")

        except Exception as e:
            self._print(f"[bold red]Failed to create project:[/bold red] {self._escape_markup(e)}")

    def open_project(self, args: str = ""):
        """Open an existing project."""
        if not args:
            # List available projects
            projects = []
            for p in self.settings.books_dir.glob("*"):
                if (p / "project.yaml").exists():
                    projects.append(p)

            if not projects:
                self._print("[dim]No projects found[/dim]")
                self._print("[dim]Create one with /new[/dim]")
                return

            # Display projects with inline selection
            self._print("\n[bold]Available projects:[/bold]")

            # Collect project info
            project_list = []
            for i, p in enumerate(projects, 1):
                try:
                    project = Project(p)
                    info_parts = []
                    if project.metadata:
                        if project.metadata.genre:
                            info_parts.append(f"[dim]{project.metadata.genre}[/dim]")
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

    def clone_project(self, args: str = ""):
        """Clone current project to a new name."""
        if not self.project:
            self._print("[yellow]No project loaded[/yellow]")
            return

        # Get new name
        new_name = args.strip() or self.console.input("New project name: ")

        if not new_name:
            self._print("[bold red]Project name required[/bold red]")
            return

        # Create destination path
        new_path = self.settings.books_dir / new_name

        try:
            # Clone the project
            cloned = self.project.clone(new_path, new_name)

            # Commit clone to shared git
            self._commit(f"Clone project: {self.project.name} → {new_name}")

            self._print(f"[dim]Cloned project:[/dim] [bold]{self.project.name}[/bold] → [bold]{new_name}[/bold]")
            self._print(f"[dim]Location: {new_path}[/dim]")

            # Ask if user wants to switch to the cloned project
            switch = self.console.input("\nSwitch to cloned project? (y/n): ").strip().lower()
            if switch == 'y':
                self.project = cloned
                self._print(f"[dim]Switched to:[/dim] [bold]{new_name}[/bold]")

        except FileExistsError as e:
            self._print(f"[bold red]Error:[/bold red] {self._escape_markup(e)}")
        except Exception as e:
            self._print(f"[bold red]Failed to clone project:[/bold red] {self._escape_markup(e)}")

    def show_status(self, args: str = ""):
        """Show current project status."""
        if not self.project:
            self.console.print("[yellow]No project loaded[/yellow]")
            return

        # Create status table
        table = Table(title=f"Project: {self.project.name}", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        # Detect story type
        is_short_form = self.project.is_short_form()
        target_words = self.project.get_target_words()

        # Add project info
        if self.project.metadata:
            table.add_row("Created", str(self.project.metadata.created_at)[:19])
            table.add_row("Updated", str(self.project.metadata.updated_at)[:19])
            table.add_row("Genre", self.project.metadata.genre or "Not set")

            # Show story type
            if is_short_form:
                if target_words:
                    if target_words < 1500:
                        story_type = "Flash Fiction"
                    elif target_words < 7500:
                        story_type = "Short Story"
                    else:
                        story_type = "Novelette"
                    table.add_row("Type", f"{story_type} (~{target_words:,} words target)")
                else:
                    table.add_row("Type", "Short Story")
            else:
                table.add_row("Type", "Novel")

            # Show current model (from global settings)
            table.add_row("Model", self.settings.active_model or "Not set")

        # Check what exists
        has_premise = self.project.premise_file.exists()
        has_treatment = self.project.treatment_file.exists()
        has_story = self.project.story_file.exists()
        has_outlines = self.project.chapters_file.exists()
        num_chapters = len(self.project.list_chapters())

        table.add_row("", "")  # Separator
        table.add_row("Premise", "✓ " if has_premise else "✗ ")
        table.add_row("Treatment", "✓ " if has_treatment else "✗ ")

        # Show different info based on story type
        if is_short_form:
            # Short story: show story.md status
            if has_story:
                story_content = self.project.get_story()
                word_count = len(story_content.split()) if story_content else 0
                table.add_row("Story", f"✓  ({word_count:,} words)")
            else:
                table.add_row("Story", "✗ ")
        else:
            # Novel: show chapters.yaml and prose chapters
            if has_outlines:
                chapters_yaml = self.project.get_chapters_yaml()
                if chapters_yaml:
                    # New self-contained format - show additional info
                    metadata = chapters_yaml.get('metadata', {})
                    characters = chapters_yaml.get('characters', [])
                    world = chapters_yaml.get('world', {})
                    chapters = chapters_yaml.get('chapters', [])

                    outline_info = f"✓  ({len(chapters)} chapters"
                    if metadata.get('genre'):
                        outline_info += f", {metadata.get('genre')}"
                    if len(characters) > 0:
                        outline_info += f", {len(characters)} chars"
                    outline_info += ")"
                    table.add_row("Outlines", outline_info)
                else:
                    table.add_row("Outlines", "✓ ")
            else:
                table.add_row("Outlines", "✗ ")

            table.add_row("Prose Chapters", str(num_chapters))

        self.console.print(table)

        # Show git status if available
        if self.git:
            status = self.git.status()
            if status:
                self.console.print("\n[cyan]Git Status:[/cyan]")
                self.console.print(f"[dim]{status}[/dim]")

    async def change_model(self, args: str = ""):
        """Change the current model."""
        # Get available models
        if not self.client:
            self.console.print("[red]API client not initialized[/red]")
            return

        models = await self.client.discover_models()

        if not args:
            # Launch interactive selector
            from .model_selector import select_model_interactive

            try:
                selected = await select_model_interactive(models, self.settings.active_model)

                if selected:
                    # Update settings
                    self.settings.set_model(selected)

                    self.console.print(f"\n[green]✓ Model changed to:[/green] [cyan]{selected}[/cyan]")
                else:
                    self.console.print("\n[yellow]Model selection cancelled[/yellow]")

            except Exception as e:
                self.console.print(f"\n[red]Error in model selector:[/red] {str(e)}")
                # Fall back to showing current model
                current = self.settings.active_model
                self.console.print(f"Current model: [cyan]{current}[/cyan]")
                self.console.print("[dim]Tip: Use /model <search> to change model (e.g., /model opus)[/dim]")

            return

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
        self.console.print(f"[green]✓  Model changed to: {selected_model}[/green]")
        self.console.print(f"[dim]   Saved to config.yaml[/dim]")

        # Show model details
        for model in models:
            if model.id == selected_model:
                price = f"${model.cost_per_1k_tokens * 1000:.2f}/1M"
                if model.is_free:
                    price = "Free"
                self.console.print(f"[dim]  Context: {model.context_length:,} tokens | Price: {price}[/dim]")
                break

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
            self.console.print(f"[red]Error fetching models: {self._escape_markup(e)}[/red]")

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
            self.console.print("[yellow]Usage: /generate <premise|premises|treatment|chapters|prose|marketing|dedication|combined> [options][/yellow]")
            return

        gen_type = parts[0].lower()
        options = parts[1] if len(parts) > 1 else ""

        try:
            if gen_type == "premise":
                await self._generate_premise(options)
                # Auto-set iteration target
                self.iteration_target = "premise"
                self._print(f"[dim]Iteration target set to: premise[/dim]")
            elif gen_type == "premises":
                # Batch premise generation
                await self._generate_premises_batch(options)
                # Auto-set iteration target
                self.iteration_target = "premise"
                self._print(f"[dim]Iteration target set to: premise[/dim]")
            elif gen_type == "treatment":
                await self._generate_treatment(options)
                # Auto-set iteration target
                self.iteration_target = "treatment"
                self._print(f"[dim]Iteration target set to: treatment[/dim]")
            elif gen_type == "chapters":
                # Check if short-form story
                if self.project.is_short_form():
                    self.console.print("[yellow]⚠  Short stories don't use chapters.yaml[/yellow]")
                    self.console.print("[dim]Use /generate prose to write the complete story[/dim]")
                    # Check if --force flag is present
                    if "--force" in options:
                        self.console.print("[dim]--force flag detected: proceeding with chapter generation[/dim]")
                        await self._generate_chapters(options.replace("--force", "").strip())
                        # Auto-set iteration target
                        self.iteration_target = "chapters"
                        self._print(f"[dim]Iteration target set to: chapters[/dim]")
                else:
                    await self._generate_chapters(options)
                    # Auto-set iteration target
                    self.iteration_target = "chapters"
                    self._print(f"[dim]Iteration target set to: chapters[/dim]")
            elif gen_type == "prose":
                # Route based on story type
                if self.project.is_short_form():
                    await self._generate_short_story_prose(options)
                else:
                    await self._generate_prose(options)
                # Auto-set iteration target
                self.iteration_target = "prose"
                self._print(f"[dim]Iteration target set to: prose[/dim]")
            elif gen_type == "marketing":
                await self._generate_marketing(options)
                # No iteration target for marketing
            elif gen_type == "dedication":
                await self._generate_dedication(options)
                # No iteration target for dedication
            elif gen_type == "combined":
                await self._generate_combined(options)
                # No iteration target for combined
            else:
                self.console.print(f"[red]Unknown generation type: {gen_type}[/red]")
                self.console.print("[dim]Valid types: premise, premises, treatment, chapters, prose, marketing, dedication, combined[/dim]")
        except Exception as e:
            self.console.print(f"[red]Generation failed: {self._escape_markup(e)}[/red]")

    async def finalize_content(self, args: str):
        """
        Finalize chapter variants by judging and selecting winner.

        Usage: /finalize chapters
        """
        if not self.project:
            self.console.print("[yellow]No project loaded. Use /new or /open first.[/yellow]")
            return

        if not self.client:
            self.console.print("[red]API client not initialized[/red]")
            return

        # Ensure git repo exists
        self._ensure_git_repo()

        # Parse finalize type
        parts = args.strip().split(None, 1)
        if not parts:
            self.console.print("[yellow]Usage: /finalize chapters[/yellow]")
            return

        finalize_type = parts[0].lower()

        if finalize_type != "chapters":
            self.console.print(f"[red]Unknown finalize type: {finalize_type}[/red]")
            self.console.print("[dim]Valid types: chapters[/dim]")
            return

        try:
            await self._finalize_chapters()
        except Exception as e:
            self.console.print(f"[red]Finalization failed: {self._escape_markup(e)}[/red]")
            from ..utils.logging import get_logger
            logger = get_logger()
            if logger:
                logger.error(f"Finalization error: {e}")

    async def _finalize_chapters(self):
        """
        Judge chapter variants and finalize winner to chapter-beats/.

        This method:
        1. Loads all variants from chapter-beats-variants/
        2. Calls LLM judge to evaluate and select best variant
        3. Copies winning variant to chapter-beats/ directory
        4. Saves decision record to decision.json
        """
        from ..generation.variants import VariantManager
        from ..generation.judging import JudgingCoordinator

        # Check for variants directory
        variants_dir = self.project.path / 'chapter-beats-variants'
        if not variants_dir.exists():
            self.console.print("[yellow]No variants found. Generate chapter variants first with /generate chapters[/yellow]")
            return

        # Load variant manager and judging coordinator
        # Note: We need a ChapterGenerator instance for VariantManager, but we're only using it for reading variants
        from ..generation.chapters import ChapterGenerator
        generator = ChapterGenerator(self.client, self.project, model=self.settings.active_model)

        variant_manager = VariantManager(generator, self.project)
        judging_coordinator = JudgingCoordinator(self.client, self.project, model=self.settings.active_model)

        # Load foundation
        foundation = variant_manager.get_foundation()
        if not foundation:
            self.console.print("[red]Foundation not found in variants directory[/red]")
            self.console.print("[dim]Expected: chapter-beats-variants/foundation.yaml[/dim]")
            return

        # Load all variant data
        variants_data = variant_manager.get_all_variants_data()

        if not variants_data:
            self.console.print("[yellow]No variant chapter data found[/yellow]")
            self.console.print("[dim]Expected: chapter-beats-variants/variant-1/, variant-2/, etc.[/dim]")
            return

        if len(variants_data) < 2:
            self.console.print(f"[yellow]Only {len(variants_data)} variant(s) found. Need at least 2 to judge.[/yellow]")
            return

        self.console.rule(style="dim")
        self.console.print(f"[cyan]Loaded {len(variants_data)} variants for judging[/cyan]\n")

        # Display variant summary
        for variant_num in sorted(variants_data.keys()):
            chapters = variants_data[variant_num]
            chapter_count = len(chapters)

            # Get variant config label
            from ..generation.variants import VARIANT_CONFIGS
            config = next((c for c in VARIANT_CONFIGS if c['variant'] == variant_num), None)
            label = config['label'] if config else f"Temperature {config['temperature']}" if config else ""

            self.console.print(f"  • Variant {variant_num} ({label}): {chapter_count} chapters")

        self.console.print()

        # Judge and finalize
        try:
            winner = await judging_coordinator.judge_and_finalize(
                foundation=foundation,
                variants_data=variants_data
            )

            # Update chapter-beats combined (premise + taxonomy + treatment + foundation + beats)
            try:
                self.project.write_combined_markdown(target='chapter-beats', include_prose=False)
            except Exception:
                pass

            # Success - commit changes
            self._commit(f"Finalize chapters: selected Variant {winner}")

            self.console.print(f"[green]✓ Chapter finalization complete[/green]")
            self.console.print(f"\n[yellow]→ Next step: /generate prose (generate full prose from finalized chapters)[/yellow]")

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Finalization cancelled by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Finalization error: {self._escape_markup(e)}[/red]")
            raise

    async def _generate_premise(self, user_input: str = ""):
        """Generate story premise with enhanced genre and taxonomy support."""
        # Ensure git repo exists
        self._ensure_git_repo()

        genre = None
        concept = ""
        length_scope = None

        # NEW FLOW: Interactive questions if no input provided
        if not user_input.strip():
            # 1. Ask for concept
            self.console.print("\n[cyan]Story Concept:[/cyan]")
            try:
                concept = input("> ").strip()
                if not concept:
                    self.console.print("[yellow]Cancelled[/yellow]")
                    return
            except (KeyboardInterrupt, EOFError):
                self.console.print("[yellow]Cancelled[/yellow]")
                return

            # 2. Ask for genre (with auto-detect option)
            genre = await self._select_genre_interactive(allow_auto_detect=True)
            if not genre:
                return  # User cancelled

            # Handle auto-detect
            if genre == 'auto-detect':
                self.console.print("\n[dim]Detecting genre from concept...[/dim]")
                generator = PremiseGenerator(self.client, self.project, model=self.settings.active_model)
                genre = await generator.detect_genre(concept)
                self.console.print(f"[cyan]→ Detected genre: {genre}[/cyan]")

            # 3. Ask for story length
            length_scope = await self._select_length_interactive()
            if not length_scope:
                return  # User cancelled

        else:
            # OLD FLOW: Parse command-line input (backwards compatible)
            parts = user_input.strip().split(None, 1)

            if parts:
                # Check if first part is a genre
                normalized = self.taxonomy_loader.normalize_genre(parts[0])
                if normalized != 'general' or parts[0].lower() in ['custom', 'general']:
                    genre = parts[0]
                    concept = parts[1] if len(parts) > 1 else ""
                else:
                    # First part is not a genre, treat all as concept
                    concept = user_input

            # If no genre specified, auto-detect or ask
            if not genre:
                if concept:
                    # Auto-detect genre from concept
                    self.console.print("[dim]Detecting genre from concept...[/dim]")
                    generator = PremiseGenerator(self.client, self.project, model=self.settings.active_model)
                    genre = await generator.detect_genre(concept)
                    self.console.print(f"[cyan]→ Detected genre: {genre}[/cyan]\n")
                else:
                    # Interactive selection
                    genre = await self._select_genre_interactive()
                    if not genre:
                        return  # User cancelled

        # Clean up downstream content before generation
        from ..generation.cull import CullManager
        culler = CullManager(self.project)

        self.console.print("[dim]Cleaning up existing premise, treatment, chapters, and prose...[/dim]")
        culler.cull_premise()  # Deletes premise/, treatment/, chapter-beats/, chapter-beats-variants/, and chapters/

        # Analyze the input to see if it's already a treatment
        analysis = PremiseAnalyzer.analyze(concept)

        if analysis['is_treatment']:
            self.console.print(f"[yellow]Detected full treatment ({analysis['word_count']} words)[/yellow]")
            self.console.print("[cyan]Preserving your treatment and generating parameters...[/cyan]")

            # Save the treatment as the premise (will be merged with taxonomy selections)
            self.project.save_premise_metadata({
                'premise': analysis['text'],
                'genre': genre or self.project.metadata.genre
            })

            # Generate only taxonomy selections
            generator = PremiseGenerator(self.client, self.project, model=self.settings.active_model)
            result = await generator.generate_taxonomy_only(
                treatment=analysis['text'],
                genre=genre or self.project.metadata.genre
            )

            if result:
                self.console.print("[green]✓  Treatment preserved with generated parameters[/green]")
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
            length_display = f" ({length_scope.replace('_', ' ')})" if length_scope else ""
            self.console.print(f"[cyan]Generating {genre or 'general'} premise{length_display}...[/cyan]\n")

            generator = PremiseGenerator(self.client, self.project, model=self.settings.active_model)
            result = await generator.generate(
                user_input=concept if concept else None,
                genre=genre or self.project.metadata.genre,
                premise_history=self.premise_history,
                length_scope=length_scope  # Pass the selected length
            )

            if result and 'premise' in result:
                # For premise, we need to print since JSON completion doesn't show during streaming
                self.console.print(result['premise'])
                self.console.print()  # Blank line

                # Print all metadata fields except taxonomy (selections)
                if 'protagonist' in result:
                    self.console.print(f"[dim]Protagonist: {result['protagonist']}[/dim]")
                if 'antagonist' in result:
                    self.console.print(f"[dim]Antagonist: {result['antagonist']}[/dim]")
                if 'stakes' in result:
                    self.console.print(f"[dim]Stakes: {result['stakes']}[/dim]")
                if 'hook' in result:
                    self.console.print(f"[dim]Hook: {result['hook']}[/dim]")
                if 'themes' in result:
                    self.console.print(f"[dim]Themes: {', '.join(result['themes'])}[/dim]")
                if 'unique_elements' in result:
                    self.console.print(f"[dim]Unique Elements: {', '.join(result['unique_elements'])}[/dim]")
                if 'original_concept' in result:
                    self.console.print(f"[dim]Original Concept: {result['original_concept']}[/dim]")

                self.console.print()  # Blank line
                self.console.rule(style="dim")
                self.console.print("[green]✓  Premise generated[/green]")
                self.console.print("[dim]Saved to premise_metadata.json[/dim]")

                # Git commit
                self._commit(f"Generate premise: {genre or 'general'}")

                # Add to history
                self.premise_history.add(
                    result['premise'],
                    genre or 'general',
                    result.get('selections', {})
                )
            else:
                self.console.print("[red]Failed to generate premise[/red]")

    async def _generate_premises_batch(self, args: str = ""):
        """Generate multiple premise options and let user select one."""
        # Ensure git repo exists
        self._ensure_git_repo()

        # Parse arguments: count [genre] [concept]
        parts = args.strip().split(None, 2)

        # Extract count
        try:
            count = int(parts[0]) if parts else 5
        except ValueError:
            self.console.print("[red]Invalid count. Usage: /generate premises <count> [genre] [concept][/red]")
            return

        if count < 1 or count > 30:
            self.console.print("[yellow]Count must be between 1 and 30[/yellow]")
            return

        # Parse genre and concept from remaining args
        remaining = " ".join(parts[1:]) if len(parts) > 1 else ""
        genre = None
        concept = ""

        if remaining:
            # Check if first part is a genre
            remaining_parts = remaining.split(None, 1)
            normalized = self.taxonomy_loader.normalize_genre(remaining_parts[0])
            if normalized != 'general' or remaining_parts[0].lower() in ['custom', 'general']:
                genre = remaining_parts[0]
                concept = remaining_parts[1] if len(remaining_parts) > 1 else ""
            else:
                # First part is not a genre, treat all as concept
                concept = remaining

        # If no genre specified and we have a concept, auto-detect
        if not genre and concept:
            self.console.print("[dim]Detecting genre from concept...[/dim]")
            generator = PremiseGenerator(self.client, self.project, model=self.settings.active_model)
            genre = await generator.detect_genre(concept)
            self.console.print(f"[cyan]→ Detected genre: {genre}[/cyan]\n")
        elif not genre:
            # Interactive selection
            genre = await self._select_genre_interactive()
            if not genre:
                return  # User cancelled

        # Generate batch
        self.console.rule(style="dim")
        self.console.print(f"[cyan]Generating {count} {genre or 'general'} premise options...[/cyan]\n")

        generator = PremiseGenerator(self.client, self.project, model=self.settings.active_model)
        try:
            premises = await generator.generate_batch(
                count=count,
                user_input=concept if concept else None,
                genre=genre
            )

            if not premises:
                self.console.print("[red]Failed to generate premises[/red]")
                return

            actual_count = len(premises)

            # Save all candidates to file
            from datetime import datetime, timezone
            candidates_data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "genre": genre or "general",
                "concept": concept,
                "count": count,
                "actual_count": actual_count,
                "selected": None,
                "premises": premises
            }

            # Ensure premise directory exists
            self.project.premise_dir.mkdir(exist_ok=True)
            with open(self.project.premises_file, 'w') as f:
                json.dump(candidates_data, f, indent=2)

            # Display premises in numbered list
            self.console.rule(style="dim")
            self.console.print("[bold]Generated Premises:[/bold]\n")

            for i, p in enumerate(premises, 1):
                premise_text = p.get('premise', '')
                hook = p.get('hook', 'N/A')

                self.console.print(f"  [cyan]{i}[/cyan]. {premise_text}")
                self.console.print(f"     [dim]Hook: {hook}[/dim]\n")

            self.console.rule(style="dim")

            # Get user selection
            try:
                self.console.print(f"\n[bold]Select premise[/bold] (1-{actual_count}) or [dim]Enter to cancel[/dim]: ", end="")

                import sys
                selection = input().strip()

                if not selection:
                    self.console.print("[yellow]Selection cancelled[/yellow]")
                    return

                selected_num = int(selection)
                if selected_num < 1 or selected_num > actual_count:
                    self.console.print(f"[red]Invalid selection. Must be between 1 and {actual_count}[/red]")
                    return

            except (ValueError, KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]Selection cancelled[/yellow]")
                return

            # Get the selected premise
            selected_premise = premises[selected_num - 1]

            # Update candidates file with selection
            candidates_data['selected'] = selected_num
            # Ensure premise directory exists
            self.project.premise_dir.mkdir(exist_ok=True)
            with open(self.project.premises_file, 'w') as f:
                json.dump(candidates_data, f, indent=2)

            # Save selected premise with metadata
            self.project.save_premise_metadata(selected_premise)

            # No combined.md at premise stage (combined is folder-specific)

            # Display selected premise
            self.console.print(f"\n[green]✓ Premise #{selected_num} selected[/green]\n")
            self.console.print(selected_premise['premise'])
            self.console.print()

            # Print all metadata fields except taxonomy (selections)
            if 'protagonist' in selected_premise:
                self.console.print(f"[dim]Protagonist: {selected_premise['protagonist']}[/dim]")
            if 'antagonist' in selected_premise:
                self.console.print(f"[dim]Antagonist: {selected_premise['antagonist']}[/dim]")
            if 'stakes' in selected_premise:
                self.console.print(f"[dim]Stakes: {selected_premise['stakes']}[/dim]")
            if 'hook' in selected_premise:
                self.console.print(f"[dim]Hook: {selected_premise['hook']}[/dim]")
            if 'themes' in selected_premise:
                self.console.print(f"[dim]Themes: {', '.join(selected_premise['themes'])}[/dim]")
            if 'unique_elements' in selected_premise:
                self.console.print(f"[dim]Unique Elements: {', '.join(selected_premise['unique_elements'])}[/dim]")
            if 'original_concept' in selected_premise:
                self.console.print(f"[dim]Original Concept: {selected_premise['original_concept']}[/dim]")

            self.console.print()
            self.console.rule(style="dim")
            self.console.print(f"[green]✓ Premise generated and saved[/green]")
            self.console.print(f"[dim]Selected premise saved to premise_metadata.json[/dim]")
            self.console.print(f"[dim]All {actual_count} candidates saved to premises_candidates.json[/dim]")

            # Git commit
            self._commit(f"Generate premise (selected #{selected_num} of {actual_count}): {genre or 'general'}")

            # Add to history
            self.premise_history.add(
                selected_premise['premise'],
                genre or 'general',
                selected_premise.get('selections', {})
            )

        except Exception as e:
            self.console.print(f"[red]Failed to generate premises: {self._escape_markup(e)}[/red]")

    async def _confirm(self, message: str) -> bool:
        """Ask user for yes/no confirmation."""
        try:
            response = input(f"{message} (y/N): ").strip().lower()
            return response in ['y', 'yes']
        except (KeyboardInterrupt, EOFError):
            return False

    async def _select_genre_interactive(self, allow_auto_detect: bool = False):
        """Interactive genre selection."""
        genres = self.taxonomy_loader.get_available_genres()

        self.console.print("\n[cyan]Select a genre:[/cyan]")

        offset = 0
        if allow_auto_detect:
            self.console.print(f"  {1:2}. Auto-detect from concept")
            offset = 1

        for i, genre in enumerate(genres, 1 + offset):
            display_name = genre.replace('-', ' ').title()
            self.console.print(f"  {i:2}. {display_name}")

        custom_idx = len(genres) + 1 + offset
        self.console.print(f"  {custom_idx:2}. Custom")

        try:
            choice = input("\nSelect (1-{}) or Enter to cancel: ".format(custom_idx))
            if not choice:
                return None

            idx = int(choice) - 1

            if allow_auto_detect and idx == 0:
                return 'auto-detect'

            # Adjust for auto-detect offset
            if allow_auto_detect:
                idx -= 1

            if 0 <= idx < len(genres):
                return genres[idx]
            elif idx == len(genres):
                return 'custom'
            else:
                self.console.print("[red]Invalid selection[/red]")
                return None

        except (ValueError, KeyboardInterrupt):
            return None

    async def _select_length_interactive(self):
        """Interactive story length selection."""
        # Length options from base taxonomy
        length_options = [
            ('flash_fiction', 'Flash Fiction', '500-1,500 words, ~5 min read'),
            ('short_story', 'Short Story', '1,500-7,500 words, ~15-30 min read'),
            ('novelette', 'Novelette', '7,500-17,500 words, ~45-90 min read'),
            ('novella', 'Novella', '17,500-40,000 words, ~2-4 hours'),
            ('novel', 'Novel', '40,000-120,000 words, ~6-12 hours'),
            ('epic', 'Epic', '120,000+ words, ~12+ hours'),
        ]

        self.console.print("\n[cyan]Select story length:[/cyan]")
        for i, (key, name, desc) in enumerate(length_options, 1):
            self.console.print(f"  {i}. {name:20} [dim]({desc})[/dim]")

        try:
            choice = input(f"\nSelect (1-{len(length_options)}) or Enter to cancel: ")
            if not choice:
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(length_options):
                return length_options[idx][0]  # Return the key
            else:
                self.console.print("[red]Invalid selection[/red]")
                return None

        except (ValueError, KeyboardInterrupt):
            return None

    async def _generate_treatment(self, options: str = ""):
        """Generate story treatment."""
        # Ensure git repo exists
        self._ensure_git_repo()

        # Check for premise
        if not self.project.get_premise():
            self.console.print("[yellow]No premise found. Generating premise first...[/yellow]")
            await self._generate_premise()

        # Clean up downstream content before generation
        from ..generation.cull import CullManager
        culler = CullManager(self.project)

        self.console.print("[dim]Cleaning up existing treatment, chapters, and prose...[/dim]")
        culler.cull_treatment()  # Deletes treatment/, chapter-beats/, chapter-beats-variants/, and chapters/

        # Parse word count if provided
        target_words = 2500
        if options:
            try:
                target_words = int(options)
            except ValueError:
                pass

        # Print divider line before generation
        self.console.rule(style="dim")

        # Generate treatment
        self.console.print(f"[cyan]Generating treatment ({target_words} words)...[/cyan]\n")
        generator = TreatmentGenerator(self.client, self.project, model=self.settings.active_model)
        result = await generator.generate(target_words=target_words)
        commit_prefix = "Generate treatment"

        if result:
            word_count = len(result.split())
            self.console.print()  # Blank line
            self.console.rule(style="dim")  # Divider after content
            self.console.print(f"[green]✓  Treatment generated: {word_count} words[/green]")
            self.console.print("[dim]Saved to treatment.md[/dim]")

            # Write treatment folder combined
            try:
                self.project.write_combined_markdown(target='treatment', include_prose=False)
            except Exception:
                pass

            # Git commit
            self._commit(f"{commit_prefix}: {word_count} words")
        else:
            self.console.print("[red]Failed to generate treatment[/red]")

    async def _generate_chapters(self, options: str = ""):
        """
        Generate chapter outline variants using multi-variant generation.

        Creates 4 variants with different temperatures (0.65, 0.70, 0.75, 0.80)
        saved to chapter-beats-variants/ for judging with /finalize chapters.
        """
        # Ensure git repo exists
        self._ensure_git_repo()

        # Check for treatment
        if not self.project.get_treatment():
            self.console.print("[yellow]No treatment found. Generate treatment first with /generate treatment[/yellow]")
            return

        # Clean up downstream content before generation
        from ..generation.cull import CullManager
        culler = CullManager(self.project)

        self.console.print("[dim]Cleaning up existing chapters and prose...[/dim]")
        culler.cull_chapters()  # Deletes chapter-beats/, chapter-beats-variants/, and chapters/ (prose)

        # Parse options (chapter count or word count) and flags
        chapter_count = None
        total_words = None  # Let generator calculate smart default
        auto_plan = False

        if options:
            parts = options.split()
            for part in parts:
                if part in ("--auto", "-a"):
                    auto_plan = True
                elif part.isdigit():
                    num = int(part)
                    if num < 50:  # Assume it's chapter count
                        chapter_count = num
                    else:  # Assume it's word count
                        total_words = num

        self.console.rule(style="dim")

        # Create chapter generator for foundation
        from ..generation.chapters import ChapterGenerator
        from ..generation.variants import VariantManager
        from ..generation.lod_context import LODContextBuilder

        generator = ChapterGenerator(self.client, self.project, model=self.settings.active_model)

        # Build context for foundation generation
        context_builder = LODContextBuilder()
        context = context_builder.build_context(
            project=self.project,
            context_level='treatment',
            include_downstream=False
        )

        if 'premise' not in context:
            self.console.print("[yellow]No premise found. Generate premise first with /generate premise[/yellow]")
            return

        if 'treatment' not in context:
            self.console.print("[yellow]No treatment found. Generate treatment first with /generate treatment[/yellow]")
            return

        # Get taxonomy and genre for smart defaults
        taxonomy_data = self.project.get_taxonomy() or {}
        premise_metadata = context.get('premise', {}).get('metadata', {})
        genre = premise_metadata.get('genre') or self.project.metadata.genre if self.project.metadata else None

        # Extract pacing
        pacing_value = taxonomy_data.get('pacing', 'moderate')
        if isinstance(pacing_value, list) and pacing_value:
            pacing = pacing_value[0]
        else:
            pacing = pacing_value if isinstance(pacing_value, str) else 'moderate'

        # Extract length_scope
        length_scope_value = taxonomy_data.get('length_scope')
        if isinstance(length_scope_value, list) and length_scope_value:
            length_scope = length_scope_value[0]
        else:
            length_scope = length_scope_value if isinstance(length_scope_value, str) else None

        # Calculate structure if needed
        if total_words is None:
            from ..generation.depth_calculator import DepthCalculator
            total_words = DepthCalculator.get_default_word_count(length_scope or 'novel', genre or 'general')

        # Baseline structure for defaults (also used for act weights)
        from ..generation.depth_calculator import DepthCalculator
        structure = DepthCalculator.calculate_structure(total_words, pacing, length_scope)
        baseline_count = structure['chapter_count']
        if chapter_count is None:
            chapter_count = baseline_count

        # Generate foundation (ONCE for all variants)
        self.console.print(f"[cyan][1/2] Generating foundation (metadata + characters + world)...[/cyan]\n")

        original_concept = premise_metadata.get('original_concept', '')
        unique_elements = premise_metadata.get('unique_elements', [])

        context_markdown = context_builder.build_markdown_context(
            project=self.project,
            context_level='treatment'
        )

        foundation = await generator._generate_foundation(
            context_markdown=context_markdown,
            taxonomy_data=taxonomy_data,
            total_words=total_words,
            chapter_count=chapter_count,
            original_concept=original_concept,
            unique_elements=unique_elements,
            feedback=None,
            genre=genre
        )

        self.console.print(f"[green]✓ Foundation complete[/green]\n")

        # Parse markdown to dict for validation and variant generation
        from ..utils.markdown_extractors import MarkdownExtractor
        foundation = MarkdownExtractor.extract_foundation(foundation)

        # Validate foundation fidelity before generating variants
        validation_loop_count = 0
        max_validation_iterations = 3

        while validation_loop_count < max_validation_iterations:
            self.console.print(f"[dim]Validating foundation fidelity...[/dim]")

            treatment_text = context.get('treatment', {}).get('text', '')
            is_valid, critical_issues = await generator._validate_foundation_fidelity(
                foundation_data=foundation,
                treatment_text=treatment_text
            )

            if not is_valid and critical_issues:
                # Show validation issues
                self.console.print(f"\n[bold yellow]{'='*70}[/bold yellow]")
                self.console.print(f"[bold yellow]⚠️  FOUNDATION VALIDATION ISSUES[/bold yellow]")
                self.console.print(f"[bold yellow]{'='*70}[/bold yellow]\n")

                for i, issue in enumerate(critical_issues, 1):
                    issue_type = issue.get('type', 'unknown').replace('_', ' ').title()
                    element = issue.get('element', 'Unknown')
                    reasoning = issue.get('reasoning', 'No details')
                    recommendation = issue.get('recommendation', '')
                    severity = issue.get('severity', 'medium')

                    severity_color = "red" if severity == "critical" else "yellow"

                    self.console.print(f"[cyan]{i}.[/cyan] [{severity_color}]{issue_type}[/{severity_color}]")
                    self.console.print(f"   Element: {element}")
                    self.console.print(f"   Problem: {reasoning}")
                    if recommendation:
                        self.console.print(f"   Fix: {recommendation}")
                    self.console.print()

                # Prompt user for action
                self.console.print(f"[bold cyan]What would you like to do?[/bold cyan]")
                self.console.print(f"  [cyan]1.[/cyan] Continue anyway (ignore issues)")
                self.console.print(f"  [cyan]2.[/cyan] Iterate on selected issues (regenerate foundation)")
                self.console.print(f"  [cyan]3.[/cyan] Abort generation")

                try:
                    choice = input("\nEnter choice (1-3): ").strip()
                except (KeyboardInterrupt, EOFError):
                    self.console.print(f"\n[yellow]Generation cancelled by user[/yellow]")
                    return

                if choice == "1":
                    # Continue anyway
                    self.console.print(f"\n[yellow]⚠️  Continuing with foundation issues...[/yellow]\n")
                    break  # Exit validation loop

                elif choice == "2":
                    # Iterate - let user select which issues to address
                    selected_issues = generator._select_validation_issues(
                        issues=critical_issues,
                        context="foundation"
                    )

                    if not selected_issues:
                        self.console.print(f"[yellow]No issues selected, continuing anyway...[/yellow]\n")
                        break

                    # Format selected issues for iteration prompt
                    formatted_issues = generator._format_validation_issues(selected_issues)

                    # Build iteration feedback
                    iteration_feedback = f"""FOUNDATION VALIDATION ISSUES TO FIX:

{formatted_issues}

INSTRUCTIONS:
Regenerate the foundation addressing the issues above.
- Fix the contradictions and inconsistencies
- Ensure alignment with treatment
- Maintain the overall structure and quality"""

                    # Regenerate foundation with validation feedback
                    self.console.print(f"\n[cyan]Regenerating foundation to address {len(selected_issues)} issue(s)...[/cyan]\n")

                    foundation = await generator._generate_foundation(
                        context_yaml=context_yaml,
                        taxonomy_data=taxonomy_data,
                        total_words=total_words,
                        chapter_count=chapter_count,
                        original_concept=original_concept,
                        unique_elements=unique_elements,
                        feedback=iteration_feedback,
                        genre=genre
                    )

                    self.console.print(f"[green]✓ Foundation regenerated[/green]\n")

                    # Parse markdown to dict for next validation iteration
                    foundation = MarkdownExtractor.extract_foundation(foundation)

                    # Increment loop counter and continue validation
                    validation_loop_count += 1

                    if validation_loop_count >= max_validation_iterations:
                        self.console.print(f"[yellow]⚠️  Max validation iterations ({max_validation_iterations}) reached.[/yellow]")
                        self.console.print(f"[yellow]Continuing with current foundation...[/yellow]\n")
                        break

                elif choice == "3":
                    # Abort
                    self.console.print(f"\n[red]Generation aborted due to foundation validation issues[/red]")
                    return

                else:
                    self.console.print(f"\n[yellow]Invalid choice, aborting[/yellow]")
                    return

            else:
                # Validation passed
                self.console.print(f"[green]✓[/green] Foundation validation passed\n")
                break  # Exit validation loop

        # Generate 4 variants in parallel
        self.console.print(f"[cyan][2/2] Generating 4 chapter outline variants in parallel...[/cyan]\n")

        variant_manager = VariantManager(generator, self.project)

        try:
            # Compute act weights from baseline_count for guidance (Act I/II/III)
            # Use 25/50/25 if baseline is too small
            if baseline_count and baseline_count >= 4:
                act1 = max(1, int(baseline_count * 0.25))
                act3 = max(1, int(baseline_count * 0.25))
                act2 = max(1, baseline_count - act1 - act3)
                act_weights = [round(act1 / baseline_count, 2), round(act2 / baseline_count, 2), round(act3 / baseline_count, 2)]
            else:
                act_weights = [0.25, 0.50, 0.25]

            successful_variants = await variant_manager.generate_variants(
                context=context,
                foundation=foundation,
                total_words=total_words,
                chapter_count=None if auto_plan else chapter_count,
                genre=genre or 'general',
                pacing=pacing,
                auto_plan=auto_plan,
                act_weights=act_weights
            )

            if successful_variants:
                self.console.print()  # Blank line
                self.console.rule(style="dim")
                self.console.print(f"[green]✓  Generated {len(successful_variants)} variants[/green]")
                self.console.print(f"[dim]Variants saved to chapter-beats-variants/ directory[/dim]")
                # Write combined variants context file
                try:
                    combined_variants = variant_manager.write_variants_combined_markdown()
                    self.console.print(f"[dim]Combined variants: {combined_variants}[/dim]")
                except Exception:
                    pass
                self.console.print(f"\n[yellow]→ Next step: /finalize chapters (judge variants and select winner)[/yellow]")

                # Git commit
                self._commit(f"Generate {len(successful_variants)} chapter outline variants")
            else:
                self.console.print("[red]Failed to generate chapter variants[/red]")

        except Exception as e:
            self.console.print(f"[red]Variant generation failed: {self._escape_markup(e)}[/red]")
            from ..utils.logging import get_logger
            logger = get_logger()
            if logger:
                logger.error(f"Variant generation error: {e}")

    async def _generate_prose(self, options: str = ""):
        """Generate prose for chapters with full sequential context."""
        # Ensure git repo exists
        self._ensure_git_repo()

        # Check for chapter outlines using new architecture
        chapters_data = self.project.get_chapters_yaml()
        if not chapters_data or not chapters_data.get('chapters'):
            self.console.print("[yellow]No chapter outlines found. Generate chapters first with /generate chapters[/yellow]")
            return

        # Parse options: chapter number or "all"
        if not options:
            self.console.print("[yellow]Usage: /generate prose <chapter_number|all>[/yellow]")
            self.console.print("[dim]  Examples:[/dim]")
            self.console.print("[dim]    /generate prose 1       - Generate chapter 1 with full context[/dim]")
            self.console.print("[dim]    /generate prose all     - Generate all chapters sequentially[/dim]")
            return

        # Parse target
        parts = options.split()

        if not parts:
            self.console.print("[yellow]Must specify chapter number or 'all'[/yellow]")
            return

        target = parts[0]

        generator = ProseGenerator(self.client, self.project, model=self.settings.active_model)

        if target.lower() == "all":
            # Clean up existing prose before generating all chapters
            from ..generation.cull import CullManager
            culler = CullManager(self.project)

            self.console.print("[dim]Cleaning up existing prose...[/dim]")
            culler.cull_prose()  # Delete all chapter prose files

            # Generate all chapters sequentially
            self.console.print("[cyan]Generating all chapters sequentially with full context...[/cyan]")

            try:
                results = await generator.generate_all_chapters()

                if results:
                    # Git commit
                    self._commit(f"Generate prose for {len(results)} chapters (sequential)")

                    self.console.print(f"\n[green]✅  Successfully generated {len(results)} chapters[/green]")
                    total_words = sum(len(p.split()) for p in results.values())
                    self.console.print(f"[dim]Total word count: {total_words:,}[/dim]")
                else:
                    self.console.print("[red]No chapters were generated[/red]")

            except Exception as e:
                self.console.print(f"[red]Error generating chapters: {self._escape_markup(e)}[/red]")

        else:
            # Generate single chapter
            try:
                chapter_num = int(target)

                # Clean up existing prose file for this chapter if it exists
                chapter_prose_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
                if chapter_prose_file.exists():
                    self.console.print(f"[dim]Removing existing chapter {chapter_num} prose...[/dim]")
                    chapter_prose_file.unlink()

                # Show token analysis first
                token_calc = await generator.calculate_prose_context_tokens(chapter_num)

                self.console.rule(style="dim")

                # Generate prose
                self.console.print(f"[cyan]Generating prose for chapter {chapter_num}...[/cyan]")
                self.console.print(f"[dim]Mode: Sequential (Full Context)[/dim]")
                self.console.print(f"[dim]Context tokens: {token_calc['total_context_tokens']:,}[/dim]")
                self.console.print(f"[dim]Response tokens: {token_calc['response_tokens']:,}[/dim]")
                self.console.print(f"[dim]Total needed: {token_calc['total_needed']:,}[/dim]")
                self.console.print()

                result = await generator.generate_chapter(chapter_number=chapter_num)
                commit_suffix = "(sequential)"

                if result:
                    word_count = len(result.split())
                    self.console.print()  # Blank line
                    self.console.rule(style="dim")
                    self.console.print(f"[green]✓  Chapter {chapter_num} generated: {word_count} words[/green]")
                    self.console.print(f"[dim]Saved to chapters/chapter-{chapter_num:02d}.md[/dim]")

                    # Git commit
                    self._commit(f"Generate prose for chapter {chapter_num} {commit_suffix}")
                else:
                    self.console.print("[red]Failed to generate prose[/red]")

            except ValueError:
                self.console.print("[red]Invalid chapter number[/red]")
            except Exception as e:
                self.console.print(f"[red]Error: {self._escape_markup(e)}[/red]")

    async def _generate_short_story_prose(self, options: str = ""):
        """Generate complete short-form story prose."""
        from ..generation import ShortStoryGenerator

        # Ensure git repo exists
        self._ensure_git_repo()

        # Check for treatment
        if not self.project.get_treatment():
            self.console.print("[yellow]No treatment found. Generate treatment first with /generate treatment[/yellow]")
            return

        # Check if there's already a story
        if self.project.get_story():
            self.console.print("[yellow]⚠  story.md already exists[/yellow]")
            response = input("Regenerate? This will overwrite existing prose [y/N]: ")
            if response.lower() != 'y':
                self.console.print("[dim]Cancelled[/dim]")
                return

        # Get target word count for display
        target_words = self.project.get_target_words()
        if target_words:
            if target_words < 1500:
                story_type = "flash fiction"
            elif target_words < 7500:
                story_type = "short story"
            else:
                story_type = "novelette"
            self.console.print(f"[cyan]Generating {story_type} (~{target_words:,} words target)...[/cyan]")
        else:
            self.console.print("[cyan]Generating short story...[/cyan]")

        try:
            generator = ShortStoryGenerator(self.client, self.project, model=self.settings.active_model)
            result = await generator.generate()

            if result:
                word_count = len(result.split())

                # Git commit
                self._commit(f"Generate short story prose: {word_count:,} words")

                self.console.print(f"[green]✅  Short story generated successfully[/green]")
                self.console.print(f"[dim]Saved to story.md[/dim]")
            else:
                self.console.print("[red]Failed to generate story[/red]")

        except Exception as e:
            self.console.print(f"[red]Error: {self._escape_markup(e)}[/red]")

    def _parse_chapter_spec(self, spec: str) -> list:
        """
        Parse chapter specification string into list of chapter numbers.

        Examples:
            "1,2" → [1, 2]
            "3-10" → [3, 4, 5, 6, 7, 8, 9, 10]
            "1,3,5-7" → [1, 3, 5, 6, 7]

        Args:
            spec: Chapter specification string

        Returns:
            List of chapter numbers (sorted, deduplicated)
        """
        chapters = set()

        # Split by comma
        parts = spec.split(',')

        for part in parts:
            part = part.strip()

            # Check if it's a range (e.g., "3-10")
            if '-' in part:
                try:
                    start, end = part.split('-')
                    start_num = int(start.strip())
                    end_num = int(end.strip())

                    if start_num < 1 or end_num < 1:
                        raise ValueError(f"Chapter numbers must be positive (got {start_num}-{end_num})")

                    if start_num > end_num:
                        raise ValueError(f"Invalid range: {start_num}-{end_num} (start > end)")

                    chapters.update(range(start_num, end_num + 1))
                except ValueError as e:
                    raise ValueError(f"Invalid chapter range '{part}': {e}")
            else:
                # Single chapter number
                try:
                    chapter_num = int(part)
                    if chapter_num < 1:
                        raise ValueError(f"Chapter numbers must be positive (got {chapter_num})")
                    chapters.add(chapter_num)
                except ValueError:
                    raise ValueError(f"Invalid chapter number '{part}'")

        return sorted(list(chapters))

    async def _generate_marketing(self, options: str = ""):
        """Generate KDP marketing metadata (description, keywords, categories, etc.)."""
        from ..generation.kdp_metadata import KDPMetadataGenerator

        # Check if book is ready for marketing
        if not self.project.has_required_metadata():
            self.console.print("[red]Missing required metadata (title and author).[/red]")
            self.console.print("Set with: [cyan]/metadata title \"Your Title\"[/cyan]")
            self.console.print("          [cyan]/metadata author \"Your Name\"[/cyan]")
            return

        # Check if content exists
        if not self.project.get_premise():
            self.console.print("[yellow]⚠ No premise found. Generate content first with /generate premise[/yellow]")
            return

        self.console.print("[cyan]Generating KDP marketing metadata...[/cyan]\n")

        # Parse options - only description and keywords
        parts = options.strip().split() if options else []
        generate_all = not parts or 'all' in parts
        generate_description = generate_all or 'description' in parts
        generate_keywords = generate_all or 'keywords' in parts

        # Create generator
        generator = KDPMetadataGenerator(
            self.client,
            self.project,
            model=self.settings.active_model
        )

        metadata = {}

        try:
            # Generate book description
            if generate_description:
                with self.console.status("[yellow]Writing book description (100-150 words)...[/yellow]"):
                    description = await generator.generate_description()
                    metadata['description'] = description

                self.console.print("[green]✓[/green] [bold]Book Description:[/bold]")
                self.console.print(description)
                self.console.print(f"[dim]Length: {len(description)} characters[/dim]\n")

            # Generate keywords
            if generate_keywords:
                with self.console.status("[yellow]Researching optimal keywords...[/yellow]"):
                    keywords = await generator.generate_keywords()
                    metadata['keywords'] = keywords

                self.console.print("[green]✓[/green] [bold]Keywords (7 boxes):[/bold]")
                for i, keyword in enumerate(keywords, 1):
                    self.console.print(f"  {i}. {keyword}")
                self.console.print()

            # Save to publishing-metadata.md
            # Ensure exports directory exists
            self.project.exports_dir.mkdir(exist_ok=True)
            output_path = self.project.publishing_metadata_file

            if generate_all:
                with self.console.status("[yellow]Saving publishing-metadata.md...[/yellow]"):
                    generator.save_metadata_file(metadata, output_path)

                self.console.print(f"[green]✓ Saved to:[/green] [cyan]{output_path}[/cyan]")
                self.console.print(f"[dim]File size: {output_path.stat().st_size / 1024:.1f} KB[/dim]\n")

            # Commit the generated metadata
            components = []
            if generate_description:
                components.append("description")
            if generate_keywords:
                components.append("keywords")

            if components:
                component_str = ", ".join(components)
                self._commit(f"Generate marketing metadata: {component_str}")

            self.console.print("[green]✅ Marketing metadata generation complete![/green]")
            self.console.print("\n[dim]Next steps:[/dim]")
            self.console.print("  1. Review and edit publishing-metadata.md")
            self.console.print("  2. Export your book: /export rtf")
            self.console.print("  3. Upload to Amazon KDP with this metadata")

        except Exception as e:
            self.console.print(f"[red]✗ Marketing generation failed: {self._escape_markup(e)}[/red]")
            self.logger.exception("Marketing metadata generation error")

    async def _generate_dedication(self, options: str = ""):
        """Generate or regenerate book dedication to family."""
        if not self.settings.active_model:
            self.console.print("[red]No model selected. Use /model first.[/red]")
            return

        # Check if treatment exists (recommended for better tone matching)
        treatment = self.project.get_treatment()
        if not treatment:
            self.console.print("[yellow]⚠  No treatment found. Dedication will use basic genre info.[/yellow]")
            self.console.print("[dim]For better results, generate treatment first: /generate treatment[/dim]\n")

        # Check if dedication already exists
        existing = self.project.get_dedication()
        if existing:
            self.console.print("[yellow]Dedication already exists:[/yellow]")
            self.console.print(f"\n[italic]{existing}[/italic]\n")

            try:
                confirm = input("Overwrite? (y/n): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    self.console.print("[yellow]Cancelled[/yellow]")
                    return
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]Cancelled[/yellow]")
                return

            self.console.print()

        # Generate
        self.console.print("[cyan]Generating heartfelt family dedication...[/cyan]\n")

        try:
            from ..export.dedication_generator import DedicationGenerator
            generator = DedicationGenerator(self.client, self.project, self.settings.active_model)

            # Use treatment for context, show generation to user
            dedication = await generator.generate_dedication(use_treatment=True, display=True)

            # Save
            self.project.save_dedication(dedication)

            # Display result
            self.console.print("\n[green]✓ Dedication generated:[/green]\n")
            self.console.print(f"[bold]{dedication}[/bold]\n")

            # Commit
            action = "Regenerate" if existing else "Generate"
            self._commit(f"{action} book dedication")

            self.console.print(f"[dim]Saved to: {self.project.dedication_file}[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error: {self._escape_markup(str(e))}[/red]")
            self.logger.exception("Dedication generation error")

    async def cull_content(self, args: str):
        """Delete generated content at various LOD levels."""
        if not self.project:
            self._print("[yellow]⚠  No project loaded[/yellow]")
            return

        if not args:
            self._print("[yellow]Usage: /cull <target>[/yellow]")
            self._print("[dim]Delete generated content and cascade to downstream content[/dim]")
            self._print()
            self._print("[dim]Targets:[/dim]")
            self._print("  [bold]/cull prose[/bold]       - Delete all prose files (chapters/*.md)")
            self._print("  [bold]/cull chapters[/bold]    - Delete chapter-beats/ (foundation + all chapters) + prose")
            self._print("  [bold]/cull treatment[/bold]   - Delete treatment/ + chapters + prose")
            self._print("  [bold]/cull premise[/bold]     - Delete premise/ + all downstream")
            self._print("  [bold]/cull debug[/bold]       - Delete all .agentic/ files (logs, debug, history)")
            return

        target = args.strip().lower()
        valid_targets = ['prose', 'chapters', 'treatment', 'premise', 'debug']

        if target not in valid_targets:
            self._print(f"[red]Invalid target:[/red] {target}")
            self._print(f"[dim]Valid targets: {', '.join(valid_targets)}[/dim]")
            return

        # Confirm deletion
        from rich.prompt import Confirm
        if target == 'debug':
            confirmed = Confirm.ask(f"Delete all debug files in .agentic/ directory?")
        else:
            confirmed = Confirm.ask(f"Delete {target} and all downstream content?")

        if not confirmed:
            self._print("[dim]Cancelled[/dim]")
            return

        # Import and use CullManager
        from ..generation.cull import CullManager

        self._ensure_git_repo()

        cull_manager = CullManager(self.project)

        try:
            # Perform culling based on target
            if target == 'prose':
                result = cull_manager.cull_prose()
            elif target == 'chapters':
                result = cull_manager.cull_chapters()
            elif target == 'treatment':
                result = cull_manager.cull_treatment()
            elif target == 'premise':
                result = cull_manager.cull_premise()
            elif target == 'debug':
                result = cull_manager.cull_debug()

            # Show results
            if result['deleted_files']:
                self._print(f"\n[green]✓[/green] Deleted {result['count']} file(s):")
                for file in result['deleted_files']:
                    self._print(f"  [dim]- {file}[/dim]")
            else:
                self._print(f"[dim]No files to delete[/dim]")

            # Commit changes (skip for debug - those files are .gitignored)
            if result['deleted_files'] and target != 'debug':
                self._commit(f"Cull {target}")
                self._print(f"\n[green]✓ Changes committed[/green]")

        except Exception as e:
            self._print(f"[red]✗ Error:[/red] {str(e)}")
            if self.session_logger:
                self.session_logger.log_error(e, "Cull failed")

    async def manage_metadata(self, args: str):
        """
        Set or view book metadata.

        Usage:
            /metadata                    # View all metadata
            /metadata title "Book Title" # Set title
            /metadata author "Author"    # Set author
            /metadata copyright 2025     # Set copyright year
        """
        if not self.project:
            self.console.print("[red]No project open. Use /open <project> first.[/red]")
            return

        args = args.strip()

        if not args:
            # Display all metadata
            self._display_book_metadata()
            return

        # Parse key-value
        parts = args.split(None, 1)
        key = parts[0].lower()

        if len(parts) < 2:
            # Show single key
            self._display_single_metadata(key)
            return

        value = parts[1].strip().strip('"\'')

        # Set metadata
        self._set_metadata(key, value)

    def _display_book_metadata(self):
        """Display all book metadata in a table."""
        metadata = self.project.get_book_metadata()

        table = Table(title="Book Metadata", show_header=True)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="yellow")

        fields = [
            ('title', 'Title'),
            ('author', 'Author'),
            ('copyright_year', 'Copyright Year')
        ]

        for key, label in fields:
            value = metadata.get(key, '')
            if value is None or value == '':
                value = '[dim]Not set[/dim]'
            table.add_row(label, str(value))

        self.console.print(table)

        # Warn if required fields missing
        if not self.project.has_required_metadata():
            self.console.print("\n[yellow]⚠ Required fields missing: title and author[/yellow]")
            self.console.print("Set with: [cyan]/metadata title \"Your Title\"[/cyan]")
            self.console.print("          [cyan]/metadata author \"Your Name\"[/cyan]")

    def _display_single_metadata(self, key: str):
        """Display single metadata field."""
        valid_keys = ['title', 'author', 'copyright']

        if key == 'copyright':
            key = 'copyright_year'

        if key not in valid_keys and key != 'copyright_year':
            self.console.print(f"[red]Unknown metadata key: {key}[/red]")
            self.console.print(f"Valid keys: {', '.join(valid_keys)}")
            return

        value = self.project.get_book_metadata(key, '')
        label = key.replace('_', ' ').title()

        if value:
            self.console.print(f"{label}: [yellow]{value}[/yellow]")
        else:
            self.console.print(f"{label}: [dim]Not set[/dim]")

    def _set_metadata(self, key: str, value: str):
        """Set metadata value with validation."""
        # Normalize key
        if key == 'copyright':
            key = 'copyright_year'

        valid_keys = ['title', 'author', 'copyright_year']

        if key not in valid_keys:
            self.console.print(f"[red]Unknown metadata key: {key}[/red]")
            self.console.print(f"Valid keys: title, author, copyright")
            return

        # Validate copyright year
        if key == 'copyright_year':
            try:
                year = int(value)
                if year < 1900 or year > 2100:
                    self.console.print("[red]Copyright year must be between 1900 and 2100[/red]")
                    return
                value = year
            except ValueError:
                self.console.print("[red]Copyright year must be a number (e.g., 2025)[/red]")
                return

        # Set value
        self.project.set_book_metadata(key, value)

        label = key.replace('_', ' ').title()
        self.console.print(f"[green]✓[/green] {label} set to: [yellow]{value}[/yellow]")

        # Auto-create frontmatter if this is first metadata
        if not self.project.frontmatter_file.exists():
            self.project.init_default_frontmatter()
            self.console.print("[dim]Created default frontmatter template[/dim]")

        # Commit metadata change
        self._commit(f"Set {key}: {value}")

    async def export_story(self, args: str):
        """
        Export book to various formats.

        Usage:
            /export rtf [filename]       # Export to RTF format
            /export markdown [filename]  # Export to combined markdown
        """
        if not self.project:
            self.console.print("[red]No project open. Use /open <project> first.[/red]")
            return

        parts = args.strip().split(None, 1)

        if not parts:
            self.console.print("[yellow]Usage: /export <format> [filename][/yellow]")
            self.console.print("Formats: rtf, markdown")
            return

        format_type = parts[0].lower()
        custom_path = parts[1] if len(parts) > 1 else None

        # Check required metadata
        if not self.project.has_required_metadata():
            self.console.print("[red]Missing required metadata (title and author).[/red]")
            self.console.print("Set with: [cyan]/metadata title \"Your Title\"[/cyan]")
            self.console.print("          [cyan]/metadata author \"Your Name\"[/cyan]")
            return

        try:
            if format_type == 'rtf':
                await self._export_rtf(custom_path)
            elif format_type == 'markdown' or format_type == 'md':
                await self._export_markdown(custom_path)
            else:
                self.console.print(f"[red]Unknown export format: {format_type}[/red]")
                self.console.print("Supported formats: rtf, markdown")

        except Exception as e:
            self.console.print(f"[red]Export failed: {str(e)}[/red]")
            self.logger.exception("Export error")

    async def _export_rtf(self, custom_path: Optional[str] = None):
        """Export to RTF format."""
        from ..export.rtf_exporter import RTFExporter

        exporter = RTFExporter(self.project, self.client, self.settings.active_model)

        # Determine output path
        if custom_path:
            output_path = Path(custom_path)
            if not output_path.is_absolute():
                output_path = self.project.path / output_path
        else:
            output_path = None  # Use default

        # Export
        with self.console.status("[yellow]Generating RTF...[/yellow]"):
            result_path = await exporter.export(output_path)

        self.console.print(f"[green]✓[/green] Exported to: [cyan]{result_path}[/cyan]")

        # Show file info
        size_kb = result_path.stat().st_size / 1024
        self.console.print(f"  File size: {size_kb:.1f} KB")

        # Count chapters
        chapters = len(list(self.project.list_chapters()))
        self.console.print(f"  Chapters: {chapters}")

        # Commit the export
        self._commit(f"Export to RTF: {result_path.name}")

    async def _export_markdown(self, custom_path: Optional[str] = None):
        """Export to combined markdown."""
        from ..export.md_exporter import MarkdownExporter

        exporter = MarkdownExporter(self.project, self.client, self.settings.active_model)

        # Determine output path
        if custom_path:
            output_path = Path(custom_path)
            if not output_path.is_absolute():
                output_path = self.project.path / output_path
        else:
            output_path = None  # Use default

        # Export
        with self.console.status("[yellow]Combining markdown files...[/yellow]"):
            result_path = await exporter.export(output_path)

        self.console.print(f"[green]✓[/green] Exported to: [cyan]{result_path}[/cyan]")

        # Show file info
        size_kb = result_path.stat().st_size / 1024
        self.console.print(f"  File size: {size_kb:.1f} KB")

        # Count chapters
        chapters = len(list(self.project.list_chapters()))
        self.console.print(f"  Chapters: {chapters}")

        # Commit the export
        self._commit(f"Export to Markdown: {result_path.name}")

    async def analyze_story(self, args: str):
        """Run story analysis."""
        if not self.project:
            self.console.print("[yellow]⚠  No project loaded[/yellow]")
            return

        if not self.client:
            self.console.print("[yellow]⚠  API client not initialized[/yellow]")
            return

        # Parse args: premise / treatment / chapters / chapter N / prose / prose N / all
        # Check for treatment inclusion flags
        args_str = args.strip() if args else ""
        include_treatment = '--include-treatment' in args_str
        exclude_treatment_explicit = '--no-treatment' in args_str

        # Remove flags from args for parsing
        if include_treatment:
            args_str = args_str.replace('--include-treatment', '').strip()
        if exclude_treatment_explicit:
            args_str = args_str.replace('--no-treatment', '').strip()

        parts = args_str.split() if args_str else []

        if not parts:
            content_type = "all"
            target_id = None
        elif parts[0] in ['premise', 'treatment', 'chapters']:
            content_type = parts[0]
            target_id = None
        elif parts[0] == 'chapter' and len(parts) > 1:
            content_type = 'chapter'
            target_id = parts[1]
        elif parts[0] == 'prose' and len(parts) > 1:
            content_type = 'prose'
            target_id = parts[1]
        elif parts[0] == 'prose':
            # Default to analyzing all prose chapters
            content_type = 'prose'
            target_id = None  # None = analyze all prose
        else:
            self.console.print("[red]Invalid analysis target[/red]")
            self.console.print("Usage: /analyze [premise|treatment|chapters|chapter N|prose|prose N|all] [--include-treatment|--no-treatment]")
            return

        # Determine treatment exclusion:
        # For 'chapters' and 'prose', default is to EXCLUDE treatment (post-iteration use case)
        # User can override with --include-treatment
        # For 'premise', treatment is never used (premise is first LOD level)
        if content_type in ['chapters', 'prose']:
            exclude_treatment = not include_treatment  # Default True, override with --include-treatment
        else:
            # For 'treatment' and other content types, default is to include treatment
            # (though premise doesn't actually use treatment in its analysis)
            exclude_treatment = exclude_treatment_explicit  # Default False, explicit --no-treatment needed

        try:
            # Initialize coordinator
            coordinator = AnalysisCoordinator(
                client=self.client,
                project=self.project,
                model=self.settings.active_model
            )

            # Show progress
            content_desc = content_type
            if target_id:
                content_desc += f" {target_id}"
            elif content_type == 'prose':
                content_desc = "prose (all chapters)"

            if exclude_treatment:
                content_desc += " (excluding treatment)"

            self.console.print(f"\n[bold cyan]📊 Analyzing {content_desc}...[/bold cyan]")
            self.console.print(f"   ⏳ Reading and evaluating...\n")

            # Ensure git repo exists
            self._ensure_git_repo()

            # Run analysis
            result = await coordinator.analyze(content_type, target_id, exclude_treatment=exclude_treatment)

            # Display results
            self._display_analysis_results(result)

            # Git commit
            if result.get('success', True):
                content_desc = result.get('content_type', content_type)
                if result.get('target_id'):
                    content_desc += f" {result['target_id']}"
                if exclude_treatment:
                    content_desc += " (no treatment)"
                self._commit(f"Analyze {content_desc}")

        except Exception as e:
            self.console.print(f"\n[red]✗ Analysis failed:[/red] {str(e)}")
            if self.session_logger:
                self.session_logger.log_error(e, "Analysis failed")

    def _display_analysis_results(self, result: Dict[str, Any]):
        """Display analysis results in simplified format."""
        self.console.print()
        self.console.rule(style="cyan")

        # Header
        content_desc = result['content_type'].title()
        if result.get('target_id'):
            content_desc += f" {result['target_id']}"
        elif result['content_type'] == 'prose':
            content_desc = "Prose (All Chapters)"

        self.console.print(f"\n[bold]📊 Analysis: {content_desc}[/bold]\n")

        # Overall grade & score (use aggregated fields if present)
        overall_grade = result.get('overall_grade')
        overall_score = result.get('overall_score')
        if overall_grade or overall_score is not None:
            if overall_grade:
                self.console.print(f"[bold green]Grade:[/bold green] {overall_grade}")
            if overall_score is not None:
                self.console.print(f"[bold green]Score:[/bold green] {overall_score:.1f}/10\n")

        # Summary (unified analyzer packs grade + justification + assessment)
        summary = result.get('summary')
        if summary:
            summary_parts = summary.split('\n')
            if len(summary_parts) >= 3:
                # Show justification + assessment (skip duplicating grade)
                justification = summary_parts[1]
                assessment = '\n'.join(summary_parts[3:])  # Skip empty line at index 2
                if justification:
                    self.console.print(f"[dim]{justification}[/dim]\n")
                if assessment:
                    self.console.print(f"{assessment}\n")
            else:
                self.console.print(f"{summary}\n")

        # Feedback by dimension (show all dimensions if present)
        dimension_results = result.get('dimension_results', [])

        # Build a set of already-present issues to avoid duplicating "priority" content
        def _issue_key(d: dict) -> tuple:
            return (
                d.get('category', ''),
                d.get('severity', ''),
                d.get('location', ''),
                d.get('description', ''),
                d.get('suggestion', ''),
            )

        seen_issue_keys = set()
        for dim_scan in dimension_results:
            for iss in dim_scan.get('issues', []):
                seen_issue_keys.add(_issue_key(iss))

        for dim in dimension_results:
            dim_name = dim.get('dimension', 'Analysis')
            # Issues - grouped by severity
            issues = dim.get('issues', [])
            if issues:
                self.console.print(f"[bold]📝 Feedback — {dim_name}:[/bold]\n")

                # Group by severity
                issues_by_severity = {
                    'CRITICAL': [],
                    'HIGH': [],
                    'MEDIUM': [],
                    'LOW': []
                }
                for issue in issues:
                    sev = issue.get('severity', 'MEDIUM').upper()
                    issues_by_severity.get(sev, issues_by_severity['MEDIUM']).append(issue)

                # Display grouped by severity
                severity_colors = {
                    'CRITICAL': 'red',
                    'HIGH': 'yellow',
                    'MEDIUM': 'cyan',
                    'LOW': 'blue'
                }
                severity_emoji = {
                    'CRITICAL': '🔴',
                    'HIGH': '🟠',
                    'MEDIUM': '🟡',
                    'LOW': '🔵'
                }

                for sev_level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                    sev_issues = issues_by_severity[sev_level]
                    if not sev_issues:
                        continue

                    color = severity_colors[sev_level]
                    self.console.print(f"[bold {color}]{severity_emoji[sev_level]} {sev_level}[/bold {color}]")

                    for issue in sev_issues:
                        loc = issue.get('location', 'Overall')
                        # Remove "General:" prefix from location
                        if loc == "General":
                            loc = "Overall"

                        cat = issue.get('category', '')
                        # Remove "General:" prefix from category
                        if cat.startswith("General:"):
                            cat = cat.replace("General:", "").strip()

                        desc = issue.get('description', '')
                        impact = issue.get('impact', '')
                        sugg = issue.get('suggestion', '')

                        # Format: Category (Location)
                        if cat and loc:
                            self.console.print(f"  [bold]{cat}[/bold] [dim]({loc})[/dim]")
                        elif cat:
                            self.console.print(f"  [bold]{cat}[/bold]")

                        if desc:
                            self.console.print(f"    {desc}")
                        if impact:
                            self.console.print(f"    [dim]Impact:[/dim] {impact}")
                        if sugg:
                            self.console.print(f"    [green]→ Fix:[/green] {sugg}")
                        self.console.print()

                self.console.print()

        # Priority issues (only if truly unique vs dimension issues)
        priority = result.get('priority_issues', [])
        unique_priority = []
        for p in priority:
            if _issue_key(p) not in seen_issue_keys:
                unique_priority.append(p)

        if unique_priority:
            self.console.print("[bold]⚠️ Priority Issues:[/bold]")
            for issue in unique_priority:
                sev = issue.get('severity', 'MEDIUM')
                loc = issue.get('location', 'General')
                desc = issue.get('description', '')
                sugg = issue.get('suggestion', '')
                self.console.print(f"  • [{sev}] {loc}: {desc}")
                if sugg:
                    self.console.print(f"    ↳ Suggestion: {sugg}")
            self.console.print()

            # Strengths
            strengths = dim.get('strengths', [])
            if strengths:
                self.console.print(f"[bold green]✓ Strengths — {dim_name}:[/bold green]")
                for strength in strengths:
                    desc = strength.get('description', '')
                    loc = strength.get('location')
                    self.console.print(f"  • {desc}{f' ({loc})' if loc else ''}")
                self.console.print()

        # Next steps (from notes of first dimension)
        if dimension_results:
            notes = dimension_results[0].get('notes', [])
            if notes:
                for note in notes:
                    if note.startswith('Next steps:'):
                        next_steps = note.replace('Next steps: ', '')
                        self.console.print(f"[bold cyan]🎯 Next Steps:[/bold cyan]")
                        self.console.print(f"  {next_steps}\n")

        # Severity breakdown (aggregated)
        if 'total_issues' in result:
            total = result.get('total_issues', 0)
            crit = result.get('critical_issues', 0)
            high = result.get('high_issues', 0)
            if total:
                self.console.print(f"[dim]Issues: total={total}, critical={crit}, high={high}[/dim]\n")

        # Report saved
        self.console.rule(style="cyan")
        self.console.print(f"\n[green]Full report saved:[/green] {result['report_path']}")
        self.console.print()

    async def copyedit_story(self, args: str):
        """
        Copy edit chapter prose with full accumulated context.

        Edits chapters sequentially, auto-applying all changes.
        Creates timestamped backup before starting.

        Usage:
            /copyedit           # Edit all chapters
            /copyedit 3         # Edit only chapter 3
            /copyedit 5-8       # Edit chapters 5, 6, 7, 8
            /copyedit 1,3,5-7   # Edit chapters 1, 3, 5, 6, 7
        """
        if not self.project:
            self.console.print("[red]No project open. Use /open <project> first.[/red]")
            return

        # Check if we have prose files (copyedit operates on prose, not chapters.yaml)
        prose_files = self.project.list_chapters()
        if not prose_files:
            self.console.print("[red]No prose files found. Generate prose first with /generate prose[/red]")
            return

        # Check if we have a model
        if not self.settings.active_model:
            self.console.print("[red]No model selected. Use /model <model-name> first.[/red]")
            return

        # Parse chapter range if provided
        chapter_filter = None
        if args.strip():
            try:
                chapter_filter = self._parse_chapter_range(args.strip())
                self.console.print(f"\n[cyan]Copy Editing Chapters: {', '.join(map(str, chapter_filter))}[/cyan]")
            except ValueError as e:
                self.console.print(f"[red]Invalid range: {e}[/red]")
                self.console.print("[yellow]Examples: /copyedit 3  or  /copyedit 5-8  or  /copyedit 1,3,5-7[/yellow]")
                return
        else:
            chapter_count = len(prose_files)
            self.console.print(f"\n[cyan]Copy Editing Pass[/cyan]")
            self.console.print(f"Editing {chapter_count} chapter prose files with {self.settings.active_model}")

        self.console.print(f"[dim]Backup will be created automatically[/dim]\n")

        try:
            # Create copy editor
            from ..generation.copy_editor import CopyEditor
            copy_editor = CopyEditor(self.client, self.project, self.settings.active_model)

            # Run copy editing pass (always auto-apply, no per-chapter prompts)
            result = await copy_editor.copy_edit_all_chapters(
                show_preview=False,  # Never show preview prompt
                auto_apply=True,     # Always auto-apply all chapters
                chapter_filter=chapter_filter  # Optional chapter filter
            )

            # Show results
            self.console.print(f"\n[green]✓ Copy editing complete![/green]")
            self.console.print(f"Edited: {result['chapters_edited']} chapters")
            if result.get('chapters_skipped', 0) > 0:
                self.console.print(f"Skipped: {result['chapters_skipped']} chapters")
            self.console.print(f"Backup: {Path(result['backup_dir']).relative_to(self.project.path)}")

            # Commit the changes
            if chapter_filter:
                chapter_desc = ', '.join(map(str, chapter_filter))
                self._commit(f"Copy edit chapters {chapter_desc}")
            else:
                self._commit(f"Copy editing pass complete ({result['chapters_edited']} chapters)")

        except Exception as e:
            self.console.print(f"[red]Copy editing failed: {str(e)}[/red]")
            self.logger.exception("Copy editing error")

    def _parse_chapter_range(self, range_str: str) -> List[int]:
        """
        Parse chapter range string into list of chapter numbers.

        Supports:
            "3" → [3]
            "5-8" → [5, 6, 7, 8]
            "1,3,5-7" → [1, 3, 5, 6, 7]

        Args:
            range_str: Range string to parse

        Returns:
            List of chapter numbers

        Raises:
            ValueError: If range format is invalid
        """
        chapters = []

        # Split by comma first
        parts = range_str.split(',')

        for part in parts:
            part = part.strip()

            # Check if it's a range (5-8)
            if '-' in part:
                try:
                    start, end = part.split('-', 1)
                    start_num = int(start.strip())
                    end_num = int(end.strip())

                    if start_num > end_num:
                        raise ValueError(f"Invalid range '{part}': start must be <= end")

                    chapters.extend(range(start_num, end_num + 1))
                except ValueError as e:
                    if "invalid literal" in str(e):
                        raise ValueError(f"Invalid range '{part}': must be numbers")
                    raise
            else:
                # Single chapter number
                try:
                    chapters.append(int(part))
                except ValueError:
                    raise ValueError(f"Invalid chapter number '{part}': must be a number")

        if not chapters:
            raise ValueError("No chapters specified")

        # Remove duplicates and sort
        chapters = sorted(set(chapters))

        return chapters

    async def _generate_combined(self, options: str = ""):
        """Backfill folder-level combined.md for current context.

        Usage:
            /generate combined [treatment|beats|chapters] [variants] [prose]

        - Writes treatment/combined.md (premise, taxonomy, treatment)
        - Writes chapter-beats/combined.md (premise, taxonomy, treatment, foundation, beats)
        - Writes chapters/combined.md (premise, taxonomy, treatment, foundation, beats, prose when 'prose')
        - If 'variants' is passed and chapter-beats-variants/ exists, writes chapter-beats-variants/combined.md
        If no specific target is passed, auto-detects the most advanced stage available.
        """
        if not self.project:
            self.console.print("[yellow]No project loaded. Use /new or /open first.[/yellow]")
            return

        tokens = set(options.split()) if options else set()
        include_variants = 'variants' in tokens
        include_prose = 'prose' in tokens

        # Determine target
        target = None
        if 'treatment' in tokens:
            target = 'treatment'
        elif 'beats' in tokens:
            target = 'chapter-beats'
        elif 'chapters' in tokens:
            target = 'chapters'
        else:
            # Auto-detect most advanced stage
            if self.project.chapters_dir.exists() and list(self.project.chapters_dir.glob('chapter-*.md')):
                target = 'chapters'
            elif self.project.chapter_beats_dir.exists() and (
                (self.project.chapter_beats_dir / 'foundation.md').exists() or
                list(self.project.chapter_beats_dir.glob('chapter-*.md'))
            ):
                target = 'chapter-beats'
            elif self.project.treatment_file.exists():
                target = 'treatment'

        if not target:
            self.console.print("[yellow]Nothing to backfill yet (no treatment/beats/chapters found).[/yellow]")
            return

        # Write combined per detected/selected target
        try:
            dest = self.project.write_combined_markdown(target=target, include_prose=(include_prose and target=='chapters'))
            self.console.print(f"[green]✓[/green] Combined written: {dest}")
        except Exception as e:
            self.console.print(f"[yellow]Failed to write {target}/combined.md: {self._escape_markup(e)}[/yellow]")

        # Variants combined.md
        if include_variants:
            try:
                from ..generation.variants import VariantManager
                from ..generation.chapters import ChapterGenerator
                generator = ChapterGenerator(self.client, self.project, model=self.settings.active_model)
                variant_manager = VariantManager(generator, self.project)
                v_combined = variant_manager.write_variants_combined_markdown()
                self.console.print(f"[green]✓[/green] Variants combined: {v_combined}")
            except Exception as e:
                self.console.print(f"[yellow]Failed to write variants combined.md: {self._escape_markup(e)}[/yellow]")

        # Commit
        self._commit(f"Write combined context file: {target}")

    def split_combined(self, args: str):
        """
        Split combined.md back into individual files.

        Reverses the combine operation by parsing combined.md and writing
        foundation.md and chapter-*.md files.

        Usage:
            /split chapters    # Split chapter-beats/combined.md → foundation.md + chapter-*.md
            /split prose       # Split chapters/combined.md → chapter-*.md
        """
        if not self.project:
            self.console.print("[red]No project open. Use /open <project> first.[/red]")
            return

        if not args:
            self.console.print("[yellow]Usage: /split <target>[/yellow]")
            self.console.print("[dim]Valid targets: chapters, prose[/dim]")
            return

        target = args.strip().lower()

        if target not in ['chapters', 'prose']:
            self.console.print(f"[red]Invalid target: {target}[/red]")
            self.console.print("[dim]Valid targets: chapters, prose[/dim]")
            return

        try:
            # Perform split
            files_written, chapters_written, files_deleted = self.project.split_combined_markdown(target)

            # Success message
            if target == 'chapters':
                self.console.print(f"[green]✓[/green] Split {target}/combined.md:")
                self.console.print(f"  • foundation.md")
                self.console.print(f"  • {chapters_written} chapter files")
            else:
                self.console.print(f"[green]✓[/green] Split {target}/combined.md:")
                self.console.print(f"  • {chapters_written} chapter files")

            if files_deleted > 0:
                self.console.print(f"[dim]  • Removed {files_deleted} old chapter file(s)[/dim]")
            self.console.print(f"\n[dim]Total files written: {files_written}[/dim]")

            # Commit
            self._commit(f"Split {target}/combined.md into individual files")

        except FileNotFoundError as e:
            self.console.print(f"[red]File not found: {self._escape_markup(e)}[/red]")
            self.console.print(f"[dim]Generate combined.md first with: /combined {target}[/dim]")

        except ValueError as e:
            self.console.print(f"[red]Parse error: {self._escape_markup(e)}[/red]")
            self.console.print("[dim]Check that combined.md has the expected format[/dim]")

        except Exception as e:
            self.console.print(f"[red]Split failed: {self._escape_markup(e)}[/red]")

    def git_command(self, args: str):
        """Run git command on shared repository."""
        if not self.git:
            self.console.print("[yellow]Git not initialized[/yellow]")
            return

        if not args:
            # Show help and status
            self._print("[bold]Git Commands:[/bold]")
            self._print("[dim]All commands operate on the shared books/ repository[/dim]")
            self._print()
            self._print("  /git status          - Show working tree status")
            self._print("  /git log [N]         - Show last N commits (default: 10)")
            self._print("  /git diff            - Show uncommitted changes")
            self._print("  /git commit [msg]    - Commit with project name prefix")
            self._print("  /git rollback [N]    - Roll back N commits")
            self._print("  /git branch [name]   - Create or list branches")
            self._print()
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
                self.console.print("[green]✓  All changes staged[/green]")

            elif command == "commit":
                # Check if there are changes to commit
                status = self.git.status()
                if not status:
                    self.console.print("[green]No changes to commit[/green]")
                    return

                # Get message or use default
                if len(parts) > 1:
                    message = parts[1]
                else:
                    message = "Manual changes (external to AgenticAuthor)"

                # Use _commit to add project name prefix
                self._commit(message)

                # Show actual commit message (with prefix)
                if self.project:
                    actual_message = f"[{self.project.name}] {message}"
                else:
                    actual_message = message
                self.console.print(f"[green]✓  Committed:[/green] {actual_message}")

            elif command == "rollback":
                steps = 1
                if len(parts) > 1:
                    try:
                        steps = int(parts[1])
                    except ValueError:
                        pass

                self.git.rollback(steps=steps)
                self.console.print(f"[green]✓  Rolled back {steps} commit(s)[/green]")

            elif command == "branch":
                if len(parts) > 1:
                    branch_name = parts[1]
                    self.git.create_branch(branch_name)
                    self.console.print(f"[green]✓  Created branch: {branch_name}[/green]")
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
            self.console.print(f"[red]Git error: {self._escape_markup(e)}[/red]")

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
            # Fall back to latest log in .agentic/logs directory
            logs_dir = Path(".agentic/logs")
            if logs_dir.exists():
                # Look for both session logs and agentic logs
                log_files = sorted(
                    list(logs_dir.glob("session_*.jsonl")) + list(logs_dir.glob("agentic_*.log")),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True
                )
                log_file = log_files[0] if log_files else None
            else:
                log_file = None

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
            self.console.print(f"[red]Error reading log: {self._escape_markup(e)}[/red]")

    async def iterate_command(self, args: str = ""):
        """Change iteration target or show current target."""
        if not self.project:
            self._print("[yellow]No project open. Use /open or /new first.[/yellow]")
            return

        if not args:
            # Auto-detect most advanced LOD level if no target set
            if not self.iteration_target:
                auto_target = self._detect_iteration_target()
                if auto_target:
                    self.iteration_target = auto_target
                    self._print(f"[green]✓[/green] Auto-detected iteration target: [bold]{auto_target}[/bold]")
                    self._print("[dim]Any text input will now iterate on this target[/dim]")
                    return
                else:
                    self._print("[yellow]No content found to iterate on[/yellow]")
                    self._print("[dim]Generate content first, then use /iterate[/dim]")
                    return

            # Show current target
            self._print(f"[cyan]Current iteration target:[/cyan] [bold]{self.iteration_target}[/bold]")
            self._print("[dim]Any text input will iterate on this target[/dim]")
            self._print("[dim]Use /iterate <target> to change target[/dim]")
            return

        # Set new target
        target = args.strip().lower()
        valid_targets = ['premise', 'treatment', 'chapters', 'prose']

        if target not in valid_targets:
            self._print(f"[red]Invalid target: {target}[/red]")
            self._print(f"[dim]Valid targets: {', '.join(valid_targets)}[/dim]")
            return

        # Verify target exists
        from ..generation.iteration import Iterator
        try:
            iterator = Iterator(self.client, self.project, self.settings.active_model, self.console)
            if not iterator._target_exists(target):
                self._print(f"[yellow]No {target} found in project[/yellow]")
                self._print(f"[dim]Generate {target} first with /generate {target}[/dim]")
                return
        except Exception as e:
            self._print(f"[red]Error checking target: {self._escape_markup(e)}[/red]")
            return

        # Set target
        self.iteration_target = target
        self._print(f"[green]✓[/green] Iteration target set to [bold]{target}[/bold]")
        self._print("[dim]Any text input will now iterate on this target[/dim]")

    async def improve_content(self, args: str):
        """Auto-improve content via LLM analysis and incorporation."""
        if not self.project:
            self._print("[red]No project loaded. Use /open <name>[/red]")
            return

        # Parse target
        target = args.strip().lower()
        if not target:
            self._print("[yellow]Usage: /improve [premise|treatment|chapters][/yellow]")
            return

        if target not in ['premise', 'treatment', 'chapters']:
            self._print(f"[red]Invalid target: {target}[/red]")
            self._print("[dim]Valid targets: premise, treatment, chapters[/dim]")
            return

        # Get model
        model = self.settings.active_model
        if not model:
            self._print("[red]No model selected. Use /model first[/red]")
            return

        # Run improvement workflow
        from ..generation.improvement import Improver
        improver = Improver(self.client, self.project, model, self.console)

        try:
            await improver.improve(target)
        except Exception as e:
            self._print(f"[red]Error during improvement: {self._escape_markup(str(e))}[/red]")
            import traceback
            from ..utils.logging import get_logger
            logger = get_logger()
            if logger:
                logger.error(f"Improvement failed: {e}")
                logger.error(traceback.format_exc())

    def _detect_iteration_target(self) -> Optional[str]:
        """
        Auto-detect the most advanced LOD level that exists.

        Priority: prose > chapters > treatment > premise

        Returns:
            Target name or None if no content exists
        """
        if not self.project:
            return None

        # Check in order from most advanced to least advanced
        if self.project.chapters_dir.exists() and list(self.project.list_chapters()):
            return 'prose'

        if self.project.chapter_beats_dir.exists() and list(self.project.list_chapter_beats()):
            return 'chapters'

        if self.project.treatment_file.exists():
            return 'treatment'

        if self.project.get_premise():
            return 'premise'

        return None

    async def handle_iteration_feedback(self, feedback: str):
        """Handle natural language iteration feedback."""
        if not self.project:
            self._print("[yellow]No project open. Use /open or /new first.[/yellow]")
            return

        if not self.iteration_target:
            # Auto-detect target
            auto_target = self._detect_iteration_target()
            if auto_target:
                self.iteration_target = auto_target
                self._print(f"[green]✓[/green] Auto-detected iteration target: [bold]{auto_target}[/bold]")
            else:
                self._print("[yellow]No content found to iterate on[/yellow]")
                self._print("[dim]Generate content first, then provide feedback[/dim]")
                return

        if not feedback.strip():
            self._print("[yellow]Empty feedback - please provide iteration instructions[/yellow]")
            return

        # Import Iterator
        from ..generation.iteration import Iterator

        try:
            # Create iterator
            iterator = Iterator(
                client=self.client,
                project=self.project,
                model=self.settings.active_model,
                console=self.console
            )

            # Run iteration
            self._print(f"\n[bold cyan]Iterating on {self.iteration_target}...[/bold cyan]")
            success = await iterator.iterate(
                target=self.iteration_target,
                feedback=feedback
            )

            if success:
                self._print(f"\n[green]✓[/green] Iteration complete")
                self._print(f"[dim]Iteration target remains: {self.iteration_target}[/dim]")
                self._print("[dim]Continue providing feedback or use /iterate <target> to change target[/dim]")
            else:
                self._print(f"\n[yellow]Iteration cancelled or rejected[/yellow]")

        except Exception as e:
            self._print(f"[red]Iteration failed: {self._escape_markup(e)}[/red]")
            self.logger.exception("Iteration failed")
            if self.session_logger:
                self.session_logger.log_error(e, "Iteration failed")
