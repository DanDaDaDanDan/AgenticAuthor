"""Interactive REPL interface using prompt_toolkit."""
import asyncio
import re
import importlib
import sys
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
from rich import print as rprint

from ..config import get_settings
from ..api import OpenRouterClient
from ..models import Project, Story
from ..storage.git_manager import GitManager
from .command_completer import SlashCommandCompleter, create_command_descriptions
from .auto_suggest import SlashCommandAutoSuggest
from ..generation import PremiseGenerator, TreatmentGenerator, ChapterGenerator, ProseGenerator
from ..generation.taxonomies import TaxonomyLoader, PremiseAnalyzer, PremiseHistory
from ..generation.iteration import IterationCoordinator
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
        self.story: Optional[Story] = None
        self.git: Optional[GitManager] = None
        self.running = False
        self.iteration_target: Optional[str] = None  # Track what to iterate on

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
            'iterate': self.iterate_content,
            'cull': self.cull_content,
            'analyze': self.analyze_story,
            'metadata': self.manage_metadata,
            'export': self.export_story,
            'copyedit': self.copyedit_story,
            'git': self.git_command,
            'config': self.show_config,
            'clear': self.clear_screen,
            'logs': self.show_logs,
            'multimodel': self.multimodel_command,
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
            'multimodel': '#f59e0b bold',  # Orange/amber for multi-model indicator
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
            mouse_support=True,
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

            # Restore iteration target if set
            if self.project.metadata and self.project.metadata.iteration_target:
                self.iteration_target = self.project.metadata.iteration_target
                self._print(f"[dim]Loaded project:[/dim] [bold]{self.project.name}[/bold]")
                self._print(f"[dim]Iteration target:[/dim] [cyan]{self.iteration_target}[/cyan]")
            else:
                self._print(f"[dim]Loaded project:[/dim] [bold]{self.project.name}[/bold]")

        except Exception as e:
            self._print(f"[bold red]Error loading project:[/bold red] {e}")
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
                self._print(f"[dim]⚠  Warning:[/dim] Failed to fetch models: {e}")
                self._print("[dim]Model autocomplete will not be available[/dim]")
                self._cached_model_ids = []

        except Exception as e:
            self._print(f"[bold red]Failed to initialize API client:[/bold red] {e}")
            self._print("[dim]Please check your OPENROUTER_API_KEY[/dim]")
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
                self._print(f"[bold red]Error:[/bold red] {e}")

        # Cleanup
        if self.client:
            await self.client.close()

    def _build_prompt(self) -> HTML:
        """Build the prompt string."""
        # Add multi-model indicator if enabled
        indicator = ""
        if self.settings.multi_model_mode:
            indicator = '<multimodel>(MULTI-MODEL)</multimodel> '
        return HTML(f'{indicator}<prompt>></prompt> ')

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
            # Natural language feedback - send to iteration system
            if not self.project:
                msg = "No project loaded. Use /new or /open first."
                if self.session_logger:
                    self.session_logger.log(msg, "WARNING")
                self._print(f"[dim]⚠  {msg}[/dim]")
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
        if not self.project:
            self._print("[yellow]⚠  No project loaded[/yellow]")
            return

        if not self.client:
            self._print("[yellow]⚠  API client not initialized[/yellow]")
            return

        # Ensure git repo exists
        self._ensure_git_repo()

        # Special handling for taxonomy iteration
        if self.iteration_target == 'taxonomy':
            await self._process_taxonomy_feedback(feedback)
            return

        try:
            # Initialize iteration coordinator
            coordinator = IterationCoordinator(
                client=self.client,
                project=self.project,
                model=self.settings.active_model,
                default_target=self.iteration_target,  # Pass the iteration target
                settings=self.settings  # Pass settings for multi-model mode
            )

            # Show processing header
            target_info = f" → {self.iteration_target}" if self.iteration_target else ""
            self.console.rule(f"[bold cyan]Iteration{target_info}[/bold cyan]", style="cyan")
            self._print()

            # Process feedback
            result = await coordinator.process_feedback(
                feedback=feedback,
                auto_commit=True,
                show_preview=False
            )

            # Display results
            if result['success']:
                self._display_iteration_success(result)

                # Commit changes BEFORE LOD sync (if there were any)
                if result.get('changes'):
                    intent = result.get('intent', {})
                    scale = result.get('scale', 'patch')

                    # Generate commit message
                    action = intent.get('action', 'update').replace('_', ' ')
                    target = intent.get('target_type', 'content')
                    if intent.get('target_id'):
                        target = f"{target} {intent['target_id']}"

                    if scale == "patch":
                        message = f"Iterate {target}: {action}"
                    else:
                        message = f"Regenerate {target}: {action}"

                    self._commit(message)

            elif result.get('needs_clarification'):
                self._display_clarification_request(result)
            else:
                error_msg = result.get('error', 'Unknown error')
                self._print(f"\n[red]✗ Error:[/red] {error_msg}")
                # Log error to main log file for debugging
                if self.session_logger:
                    self.session_logger.log(f"Iteration error: {error_msg}", "ERROR")

        except Exception as e:
            self._print(f"\n[red]✗ Error processing feedback:[/red] {str(e)}")
            if self.session_logger:
                self.session_logger.log_error(e, "Iteration failed")

    def _display_iteration_success(self, result: Dict[str, Any]):
        """Display successful iteration results."""
        intent = result.get('intent', {})
        scale = result.get('scale', 'unknown')
        changes = result.get('changes', [])

        # Show intent summary
        action = intent.get('action', 'unknown').replace('_', ' ')
        target = intent.get('target_type', 'content')
        if intent.get('target_id'):
            target = f"{target} {intent['target_id']}"

        self._print(f"[green]✓ Intent understood:[/green] {action} ({target})")
        self._print(f"[dim]  Confidence: {intent.get('confidence', 0):.0%} | Scale: {scale}[/dim]")
        self._print()

        # Show changes
        if changes:
            for change in changes:
                change_type = change.get('type', 'unknown')

                if change_type == 'patch':
                    # New unified context format
                    updated_files = change.get('updated_files', [])
                    deleted_files = change.get('deleted_files', [])

                    # Show updated files
                    if updated_files:
                        for file in updated_files:
                            self._print(f"[green]✓ Updated:[/green] [cyan]{file}[/cyan]")

                    # Show deleted files (culled downstream)
                    if deleted_files:
                        self._print(f"[dim]✗ Culled downstream:[/dim]")
                        for file in deleted_files:
                            self._print(f"  [dim]- {file}[/dim]")

                    # Show chapter count if applicable
                    if 'chapter_count' in change:
                        chapter_count = change.get('chapter_count', 0)
                        self._print(f"[dim]  ({chapter_count} chapters)[/dim]")

                elif change_type == 'regenerate':
                    # Old format (still used by some generators)
                    file_path = change.get('file', 'unknown')
                    # Check if this is chapters (has 'count' field) or prose (has 'word_count')
                    if 'count' in change:
                        chapter_count = change.get('count', 0)
                        self._print(f"[green]✓ Regenerated:[/green] [cyan]{file_path}[/cyan] ({chapter_count} chapters)")
                    else:
                        word_count = change.get('word_count', 0)
                        self._print(f"[green]✓ Regenerated:[/green] [cyan]{file_path}[/cyan] ({word_count:,} words)")

        # Show commit info
        commit = result.get('commit')
        if commit:
            self._print()
            self._print(f"[green]✓ Committed:[/green] {commit.get('message', 'unknown')}")

        # Closing rule
        self._print()
        self.console.rule(style="dim")

    async def _process_taxonomy_feedback(self, feedback: str):
        """Process feedback for taxonomy iteration."""
        from ..generation.premise import PremiseGenerator
        from .taxonomy_editor import run_taxonomy_editor
        from ..generation.taxonomies import TaxonomyLoader
        import json

        # Load current premise and taxonomy
        premise = self.project.get_premise()
        if not premise:
            self._print("[red]No premise found.[/red] Generate a premise first with /generate premise")
            return

        premise_metadata_file = self.project.premise_metadata_file
        if not premise_metadata_file.exists():
            self._print("[red]No taxonomy metadata found.[/red]")
            self._print("[dim]Generate a new premise with taxonomy: /generate premise[/dim]")
            return

        with open(premise_metadata_file) as f:
            current_taxonomy = json.load(f)

        # If no feedback provided, launch interactive editor
        if not feedback or feedback.strip() == "":
            # Get genre from project
            genre = self.project.metadata.genre if self.project.metadata else 'general'

            # Load taxonomy and options
            taxonomy_loader = TaxonomyLoader()
            taxonomy = taxonomy_loader.load_merged_taxonomy(genre)
            category_options = taxonomy_loader.get_category_options(taxonomy)

            # Run interactive editor
            try:
                updated_taxonomy = run_taxonomy_editor(
                    taxonomy=taxonomy,
                    current_selections=current_taxonomy,
                    category_options=category_options
                )

                if updated_taxonomy is None:
                    self._print("\n[yellow]Taxonomy editing cancelled[/yellow]")
                    return

                # Check what changed
                changes = []
                for category, new_values in updated_taxonomy.items():
                    old_values = current_taxonomy.get(category, [])
                    if new_values != old_values:
                        changes.append(f"Changed {category.replace('_', ' ')}: {old_values} → {new_values}")

                if not changes:
                    self._print("\n[yellow]No changes made[/yellow]")
                    return

                # Ask if should regenerate premise
                self._print("\n[cyan]Changes made:[/cyan]")
                for change in changes:
                    self._print(f"  • {change}")
                self._print()

                regenerate = await self._confirm("Regenerate premise with new taxonomy?")

                if regenerate:
                    # Regenerate premise
                    generator = PremiseGenerator(self.client, self.project, model=self.settings.active_model)

                    self._print("[cyan]Regenerating premise...[/cyan]")
                    self._print()

                    regen_result = await generator.regenerate_with_taxonomy(
                        user_input=premise,
                        taxonomy_selections=updated_taxonomy,
                        genre=genre
                    )

                    if regen_result and 'premise' in regen_result:
                        # Save new premise with metadata
                        self.project.save_premise_metadata(regen_result)

                        self._print("[green]✓ Premise regenerated[/green]")
                        self._print()
                        self._print(f"[bold]{regen_result['premise']}[/bold]")

                        # Git commit
                    self._commit("Update taxonomy and regenerate premise")
                    self._print("\n[green]✓ Committed to git[/green]")

                else:
                    # Just update taxonomy
                    with open(premise_metadata_file, 'w') as f:
                        json.dump(updated_taxonomy, f, indent=2)

                    self._print("[green]✓ Taxonomy updated[/green]")

                    # Git commit
                    self._commit("Update taxonomy selections")
                    self._print("[green]✓ Committed to git[/green]")

                return

            except Exception as e:
                self._print(f"\n[red]Error in interactive editor:[/red] {str(e)}")
                return

        # Show header
        self.console.rule("[bold cyan]Taxonomy Iteration[/bold cyan]", style="cyan")
        self._print()

        # Initialize generator
        generator = PremiseGenerator(self.client, self.project, model=self.settings.active_model)

        try:
            # Get taxonomy updates
            result = await generator.iterate_taxonomy(
                current_taxonomy=current_taxonomy,
                feedback=feedback,
                current_premise=premise
            )

            if not result:
                self._print("[red]Failed to process taxonomy changes[/red]")
                return

            # Show what changed
            changes = result.get('changes_made', [])
            if changes:
                self._print("[green]✓ Taxonomy Changes:[/green]")
                for change in changes:
                    self._print(f"  • {change}")
                self._print()

            reasoning = result.get('reasoning', '')
            if reasoning:
                self._print(f"[dim]{reasoning}[/dim]")
                self._print()

            # Get updated taxonomy
            updated_taxonomy = result.get('updated_taxonomy', {})

            # Check if we should regenerate premise
            should_regenerate = result.get('regenerate_premise', False)

            if should_regenerate:
                self._print("[cyan]Regenerating premise with updated taxonomy...[/cyan]")
                self._print()

                # Regenerate premise
                regen_result = await generator.regenerate_with_taxonomy(
                    user_input=premise,
                    taxonomy_selections=updated_taxonomy,
                    genre=self.project.metadata.genre if self.project.metadata else None
                )

                if regen_result and 'premise' in regen_result:
                    # Save new premise with metadata
                    self.project.save_premise_metadata(regen_result)

                    self._print("[green]✓ Premise regenerated with new taxonomy[/green]")
                    self._print()
                    self._print(f"[bold]{regen_result['premise']}[/bold]")
                    self._print()

                    # Git commit
                    self._commit(f"Iterate taxonomy: {feedback[:50]}")
                    self._print("[green]✓ Changes committed to git[/green]")

            else:
                # Just update taxonomy without regenerating
                with open(premise_metadata_file, 'w') as f:
                    json.dump(updated_taxonomy, f, indent=2)

                self._print("[green]✓ Taxonomy updated[/green]")
                self._print("[dim]Premise unchanged - changes don't require regeneration[/dim]")

                # Git commit
                self._commit(f"Update taxonomy: {feedback[:50]}")
                self._print("[green]✓ Changes committed to git[/green]")

            self._print()
            self.console.rule(style="dim")

        except Exception as e:
            self._print(f"[red]✗ Error:[/red] {str(e)}")
            if self.session_logger:
                self.session_logger.log_error(e, "Taxonomy iteration failed")

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

    def _display_clarification_request(self, result: Dict[str, Any]):
        """Display clarification request."""
        clarification = result.get('clarification_needed', {})
        reason = clarification.get('reason', 'Intent unclear')
        suggestions = clarification.get('suggestions', [])

        self._print(f"\n[yellow]⚠  Need more information:[/yellow]")
        self._print(f"   {reason}")

        if suggestions:
            self._print(f"\n[dim]Suggestions:[/dim]")
            for suggestion in suggestions:
                self._print(f"   • {suggestion}")

        self._print()

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

            # Initialize story
            self.story = Story()

            self._print(f"[dim]Created project:[/dim] [bold]{name}[/bold]")
            self._print(f"[dim]Location: {project_dir}[/dim]")

        except Exception as e:
            self._print(f"[bold red]Failed to create project:[/bold red] {e}")

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
                self.story = Story()  # Reset story
                self._print(f"[dim]Switched to:[/dim] [bold]{new_name}[/bold]")

        except FileExistsError as e:
            self._print(f"[bold red]Error:[/bold red] {e}")
        except Exception as e:
            self._print(f"[bold red]Failed to clone project:[/bold red] {e}")

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

            # Show model(s) - check if multi-model mode is active
            if self.settings.multi_model_mode:
                models_display = f"🏆 {', '.join(self.settings.competition_models)} (judged by {self.settings.judge_model})"
                table.add_row("Models", models_display)
            else:
                table.add_row("Model", self.project.metadata.model or self.settings.active_model or "Not set")

            table.add_row("Words", str(self.project.metadata.word_count))
            if not is_short_form:
                table.add_row("Chapters", str(self.project.metadata.chapter_count))
            table.add_row("Status", self.project.metadata.status)

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
            self.console.print("[yellow]Usage: /generate <premise|premises|treatment|chapters|prose|marketing> [options][/yellow]")
            return

        gen_type = parts[0].lower()
        options = parts[1] if len(parts) > 1 else ""

        try:
            if gen_type == "premise":
                await self._generate_premise(options)
            elif gen_type == "premises":
                # Batch premise generation
                await self._generate_premises_batch(options)
            elif gen_type == "concepts":
                # Concept mashup generation
                await self._generate_concept_mashup(options)
            elif gen_type == "treatment":
                await self._generate_treatment(options)
            elif gen_type == "chapters":
                # Check if short-form story
                if self.project.is_short_form():
                    self.console.print("[yellow]⚠  Short stories don't use chapters.yaml[/yellow]")
                    self.console.print("[dim]Use /generate prose to write the complete story[/dim]")
                    # Check if --force flag is present
                    if "--force" in options:
                        self.console.print("[dim]--force flag detected: proceeding with chapter generation[/dim]")
                        await self._generate_chapters(options.replace("--force", "").strip())
                else:
                    await self._generate_chapters(options)
            elif gen_type == "prose":
                # Route based on story type
                if self.project.is_short_form():
                    await self._generate_short_story_prose(options)
                else:
                    await self._generate_prose(options)
            elif gen_type == "marketing":
                await self._generate_marketing(options)
            else:
                self.console.print(f"[red]Unknown generation type: {gen_type}[/red]")
                self.console.print("[dim]Valid types: premise, premises, concepts, treatment, chapters, prose, marketing[/dim]")
        except Exception as e:
            self.console.print(f"[red]Generation failed: {e}[/red]")

    async def _generate_premise(self, user_input: str = ""):
        """Generate story premise with enhanced genre and taxonomy support."""
        # Ensure git repo exists
        self._ensure_git_repo()

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

        # If no genre specified
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
                self.console.print("[green]✓  Premise generated[/green]")
                self.console.print("[dim]Saved to premise.md[/dim]")

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
            with open(self.project.premises_file, 'w') as f:
                json.dump(candidates_data, f, indent=2)

            # Save selected premise with metadata
            self.project.save_premise_metadata(selected_premise)

            # Display selected premise
            self.console.print(f"\n[green]✓ Premise #{selected_num} selected[/green]\n")
            self.console.print(selected_premise['premise'])
            self.console.print()

            # Print metadata
            if 'hook' in selected_premise:
                self.console.print(f"[dim]Hook: {selected_premise['hook']}[/dim]")
            if 'themes' in selected_premise:
                self.console.print(f"[dim]Themes: {', '.join(selected_premise['themes'])}[/dim]")

            self.console.print()
            self.console.rule(style="dim")
            self.console.print(f"[green]✓ Premise generated and saved[/green]")
            self.console.print(f"[dim]Selected premise saved to premise.md[/dim]")
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
            self.console.print(f"[red]Failed to generate premises: {e}[/red]")

    async def _generate_concept_mashup(self, args: str = ""):
        """Generate movie + modifier mashup concepts."""
        from ..generation.concept_mashup import ConceptMashupGenerator

        # Ensure git repo exists
        self._ensure_git_repo()

        # Parse count argument (default 50)
        count = 50
        if args.strip():
            try:
                count = int(args.strip())
                if count < 1 or count > 100:
                    self.console.print("[yellow]Count must be between 1 and 100[/yellow]")
                    return
            except ValueError:
                self.console.print("[red]Invalid count. Usage: /generate concepts [count][/red]")
                return

        try:
            # Generate combinations
            mashup_gen = ConceptMashupGenerator()
            concepts = mashup_gen.generate_combinations(count)

            if not concepts:
                self.console.print("[red]Failed to generate concepts[/red]")
                return

            actual_count = len(concepts)

            # Display header
            self.console.print()
            self.console.rule("[cyan]Concept Mashup Options[/cyan]")
            self.console.print()

            # Display concepts in numbered list
            for concept in concepts:
                # Alternate colors for readability
                if concept['number'] % 2 == 0:
                    self.console.print(f"[dim]{concept['number']:2}.[/dim] {concept['concept']}")
                else:
                    self.console.print(f"[cyan]{concept['number']:2}.[/cyan] [bold]{concept['concept']}[/bold]")

            self.console.print()
            self.console.rule(style="dim")

            # User selection
            try:
                choice = input(f"\nSelect a concept (1-{actual_count}) or press Enter to cancel: ").strip()

                if not choice:
                    self.console.print("[dim]Cancelled[/dim]")
                    return

                selected_num = int(choice)

                if selected_num < 1 or selected_num > actual_count:
                    self.console.print(f"[red]Invalid selection. Must be between 1 and {actual_count}[/red]")
                    return

            except (ValueError, KeyboardInterrupt, EOFError):
                self.console.print("[dim]Cancelled[/dim]")
                return

            # Get the selected concept
            selected_concept = concepts[selected_num - 1]

            # Display selection
            self.console.print()
            self.console.print(f"[green]✓ Selected:[/green] [bold]{selected_concept['concept']}[/bold]")
            self.console.print()

            # Feed into premise generation
            self.console.print("[cyan]Generating premise based on this concept...[/cyan]")
            await self._generate_premise(selected_concept['concept'])

        except FileNotFoundError as e:
            self.console.print(f"[red]Data files not found: {e}[/red]")
            self.console.print("[dim]Expected files: misc/movies.txt, misc/story-modifiers.txt[/dim]")
        except Exception as e:
            self.console.print(f"[red]Failed to generate concept mashup: {e}[/red]")

    async def _confirm(self, message: str) -> bool:
        """Ask user for yes/no confirmation."""
        try:
            response = input(f"{message} (y/N): ").strip().lower()
            return response in ['y', 'yes']
        except (KeyboardInterrupt, EOFError):
            return False

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
        # Ensure git repo exists
        self._ensure_git_repo()

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

        # Check if multi-model mode is enabled
        if self.settings.multi_model_mode:
            self.console.print(f"[cyan]🏆 Generating treatment with multi-model competition ({target_words} words)...[/cyan]\n")
            generator = TreatmentGenerator(self.client, self.project, model=self.settings.active_model)
            result = await generator.generate_with_competition(target_words=target_words)
            commit_prefix = "Generate treatment (multi-model)"
        else:
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

            # Git commit
            self._commit(f"{commit_prefix}: {word_count} words")
        else:
            self.console.print("[red]Failed to generate treatment[/red]")

    async def _generate_chapters(self, options: str = ""):
        """Generate chapter outlines."""
        # Ensure git repo exists
        self._ensure_git_repo()

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

        # Check if multi-model mode is enabled
        generator = ChapterGenerator(self.client, self.project, model=self.settings.active_model)
        if self.settings.multi_model_mode:
            self.console.print(f"[cyan]🏆 Generating chapter outlines with multi-model competition...[/cyan]\n")
            chapters = await generator.generate_with_competition(
                chapter_count=chapter_count,
                total_words=total_words
            )
            commit_prefix = "Generate (multi-model)"
        else:
            self.console.print(f"[cyan]Generating chapter outlines...[/cyan]\n")
            chapters = await generator.generate(
                chapter_count=chapter_count,
                total_words=total_words
            )
            commit_prefix = "Generate"

        if chapters:
            # Show all chapters
            for chapter in chapters:
                self.console.print(f"Chapter {chapter.number}: {chapter.title}")
                self.console.print(f"  [dim]{chapter.summary}[/dim]")

            self.console.print()  # Blank line
            self.console.rule(style="dim")
            self.console.print(f"[green]✓  Generated {len(chapters)} chapter outlines[/green]")
            self.console.print("[dim]Saved to chapters.yaml[/dim]")

            # Git commit
            self._commit(f"{commit_prefix} {len(chapters)} chapter outlines")
        else:
            self.console.print("[red]Failed to generate chapters[/red]")

    async def _generate_prose(self, options: str = ""):
        """Generate prose for chapters with full sequential context."""
        # Ensure git repo exists
        self._ensure_git_repo()

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

        generator = ProseGenerator(self.client, self.project, model=self.settings.active_model)

        if options.lower() == "all":
            # Generate all chapters sequentially
            self.console.print(f"[cyan]Generating all chapters sequentially with full context...[/cyan]")

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
                self.console.print(f"[red]Error generating chapters: {e}[/red]")

        else:
            # Generate single chapter
            try:
                chapter_num = int(options.split()[0])

                # Show token analysis first
                token_calc = await generator.calculate_prose_context_tokens(chapter_num)

                self.console.rule(style="dim")

                # Check if multi-model mode is enabled
                if self.settings.multi_model_mode:
                    self.console.print(f"[cyan]🏆 Generating prose for chapter {chapter_num} with multi-model competition...[/cyan]")
                    self.console.print(f"[dim]Mode: Sequential (Full Context) + Multi-Model[/dim]")
                    self.console.print(f"[dim]Context tokens: {token_calc['total_context_tokens']:,}[/dim]")
                    self.console.print(f"[dim]Response tokens: {token_calc['response_tokens']:,}[/dim]")
                    self.console.print(f"[dim]Total needed: {token_calc['total_needed']:,}[/dim]")
                    self.console.print()

                    result = await generator.generate_chapter_with_competition(chapter_number=chapter_num)
                    commit_suffix = "(sequential, multi-model)"
                else:
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
                self.console.print(f"[red]Error: {e}[/red]")

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
            self.console.print(f"[red]Error: {e}[/red]")

    async def iterate_content(self, args: str):
        """Set iteration target for natural language feedback."""
        if not args:
            # Show current target or clear it
            if self.iteration_target:
                self._print(f"[dim]Current iteration target:[/dim] [cyan]{self.iteration_target}[/cyan]")
                self._print("[dim]Type /iterate to clear target[/dim]")
                self.iteration_target = None

                # Clear from project metadata
                if self.project and self.project.metadata:
                    self.project.metadata.iteration_target = None
                    self.project.save_metadata()
            else:
                self._print("[yellow]Usage: /iterate <target>[/yellow]")
                self._print("[dim]Set what to iterate on (premise, treatment, chapters, prose)[/dim]")
                self._print("[dim]Then just type your feedback naturally[/dim]")
                self._print()
                self._print("[dim]Examples:[/dim]")
                self._print("  [bold]/iterate treatment[/bold]")
                self._print("  [dim]Add more action scenes[/dim]")
                self._print()
                self._print("  [bold]/iterate chapters[/bold]")
                self._print("  [dim]Make chapter 3 more tense[/dim]")
            return

        # Parse target
        target = args.strip().lower()
        valid_targets = ['premise', 'treatment', 'chapters', 'prose', 'taxonomy']

        if target not in valid_targets:
            self._print(f"[red]Invalid target:[/red] {target}")
            self._print(f"[dim]Valid targets: {', '.join(valid_targets)}[/dim]")
            return

        self.iteration_target = target

        # Save to project metadata
        if self.project and self.project.metadata:
            self.project.metadata.iteration_target = target
            self.project.save_metadata()

        self._print(f"[green]✓[/green] Iteration target set to: [cyan]{target}[/cyan]")
        self._print("[dim]Now type your feedback naturally (no / needed)[/dim]")
        self._print()
        self._print("[dim]Examples:[/dim]")
        if target == 'premise':
            self._print("  Add more unique elements")
            self._print("  Make it more genre-specific")
        elif target == 'treatment':
            self._print("  Add more conflict in act 2")
            self._print("  Develop the antagonist's motivation")
        elif target == 'chapters':
            self._print("  Make chapter 3 more tense")
            self._print("  Add a subplot about the protagonist's past")
        elif target == 'prose':
            self._print("  Add more dialogue to chapter 5")
            self._print("  Enhance sensory details in the opening")

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
            output_path = self.project.path / 'publishing-metadata.md'

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
            self.console.print(f"[red]✗ Marketing generation failed: {e}[/red]")
            self.logger.exception("Marketing metadata generation error")

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
            self._print("  [bold]/cull prose[/bold]       - Delete all prose files")
            self._print("  [bold]/cull chapters[/bold]    - Delete chapters.yaml + prose")
            self._print("  [bold]/cull treatment[/bold]   - Delete treatment.md + chapters + prose")
            self._print("  [bold]/cull premise[/bold]     - Delete premise.md + all downstream")
            return

        target = args.strip().lower()
        valid_targets = ['prose', 'chapters', 'treatment', 'premise']

        if target not in valid_targets:
            self._print(f"[red]Invalid target:[/red] {target}")
            self._print(f"[dim]Valid targets: {', '.join(valid_targets)}[/dim]")
            return

        # Confirm deletion
        from rich.prompt import Confirm
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

            # Show results
            if result['deleted_files']:
                self._print(f"\n[green]✓[/green] Deleted {result['count']} file(s):")
                for file in result['deleted_files']:
                    self._print(f"  [dim]- {file}[/dim]")
            else:
                self._print(f"[dim]No files to delete[/dim]")

            # Commit changes
            if result['deleted_files']:
                self._commit(f"Cull {target}")
                self._print(f"\n[green]✓ Changes committed[/green]")

        except Exception as e:
            self._print(f"[red]✗ Error:[/red] {str(e)}")
            if self.session_logger:
                self.session_logger.log_error(e, "Cull failed")

    async def analyze_story(self, args: str):
        """Run story analysis."""
        if not self.project:
            self.console.print("[yellow]⚠  No project loaded[/yellow]")
            return

        if not self.client:
            self.console.print("[yellow]⚠  API client not initialized[/yellow]")
            return

        # Parse args: premise / treatment / chapters / chapter N / prose / prose N / all
        parts = args.strip().split() if args else []

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
            target_id = "1"  # Start with chapter 1
        else:
            self.console.print("[red]Invalid analysis target[/red]")
            self.console.print("Usage: /analyze [premise|treatment|chapters|chapter N|prose|prose N|all]")
            return

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

            self.console.print(f"\n[bold cyan]📊 Analyzing {content_desc}...[/bold cyan]\n")

            # Track progress for each dimension
            dimensions = []
            if content_type in ['premise']:
                dimensions = ['plot', 'theme', 'commercial']
            elif content_type in ['treatment']:
                dimensions = ['plot', 'character', 'worldbuilding', 'theme', 'commercial']
            elif content_type in ['chapters', 'chapter']:
                dimensions = ['plot', 'character', 'worldbuilding', 'theme']
            elif content_type in ['prose']:
                dimensions = ['plot', 'character', 'worldbuilding', 'dialogue', 'prose', 'theme', 'narrative']

            for i, dim in enumerate(dimensions, 1):
                self.console.print(f"   ⏳ {dim.title()}...")

            # Ensure git repo exists
            self._ensure_git_repo()

            # Run analysis
            result = await coordinator.analyze(content_type, target_id)

            # Display results
            self._display_analysis_results(result)

            # Git commit
            if result.get('success', True):
                content_desc = result.get('content_type', content_type)
                if result.get('target_id'):
                    content_desc += f" {result['target_id']}"
                self._commit(f"Analyze {content_desc}")

        except Exception as e:
            self.console.print(f"\n[red]✗ Analysis failed:[/red] {str(e)}")
            if self.session_logger:
                self.session_logger.log_error(e, "Analysis failed")

    def _display_analysis_results(self, result: Dict[str, Any]):
        """Display analysis results."""
        self.console.print()
        self.console.rule(style="cyan")

        # Executive Summary
        content_desc = result['content_type'].title()
        if result.get('target_id'):
            content_desc += f" {result['target_id']}"

        self.console.print(f"\n[bold]📊 Analysis Complete: {content_desc}[/bold]\n")

        self.console.print(f"[bold]Overall Grade:[/bold] {result['overall_grade']}")
        self.console.print(f"[bold]Overall Score:[/bold] {result['overall_score']:.1f}/10\n")

        # Issue Summary
        if result['total_issues'] > 0:
            self.console.print(f"⚠️  [bold]Issues Found:[/bold] {result['total_issues']} total")
            if result['critical_issues'] > 0:
                self.console.print(f"   • Critical: {result['critical_issues']}")
            if result['high_issues'] > 0:
                self.console.print(f"   • High: {result['high_issues']}")
            self.console.print()

        # Dimension Scores
        self.console.print("[bold]Dimension Scores:[/bold]")
        for dim in result['dimension_results']:
            score = dim['score']
            bar = '█' * int(score) + '░' * (10 - int(score))
            self.console.print(f"  {dim['dimension']:25} [{bar}] {score:.1f}/10")
        self.console.print()

        # Top Issues
        if result['priority_issues']:
            self.console.print("[bold]Top Priority Issues:[/bold]")
            for i, issue in enumerate(result['priority_issues'][:3], 1):
                severity_color = {
                    'CRITICAL': 'red',
                    'HIGH': 'yellow',
                    'MEDIUM': 'cyan',
                    'LOW': 'dim'
                }.get(issue['severity'], 'white')

                self.console.print(f"  {i}. [{severity_color}][{issue['severity']}][/{severity_color}] {issue['category']}")
                self.console.print(f"     Location: [dim]{issue['location']}[/dim]")
                self.console.print(f"     Issue: {issue['description']}")
                self.console.print(f"     Fix: [green]{issue['suggestion']}[/green]")
                self.console.print()

        # Highlights
        if result['highlights']:
            self.console.print("[bold]✓ Positive Highlights:[/bold]")
            for strength in result['highlights'][:3]:
                self.console.print(f"  • {strength['description']}")
            self.console.print()

        # Report saved
        self.console.rule(style="cyan")
        self.console.print(f"\n[green]Full report saved:[/green] {result['report_path']}")
        self.console.print()

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

        exporter = RTFExporter(self.project)

        # Determine output path
        if custom_path:
            output_path = Path(custom_path)
            if not output_path.is_absolute():
                output_path = self.project.path / output_path
        else:
            output_path = None  # Use default

        # Export
        with self.console.status("[yellow]Generating RTF...[/yellow]"):
            result_path = exporter.export(output_path)

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

        exporter = MarkdownExporter(self.project)

        # Determine output path
        if custom_path:
            output_path = Path(custom_path)
            if not output_path.is_absolute():
                output_path = self.project.path / output_path
        else:
            output_path = None  # Use default

        # Export
        with self.console.status("[yellow]Combining markdown files...[/yellow]"):
            result_path = exporter.export(output_path)

        self.console.print(f"[green]✓[/green] Exported to: [cyan]{result_path}[/cyan]")

        # Show file info
        size_kb = result_path.stat().st_size / 1024
        self.console.print(f"  File size: {size_kb:.1f} KB")

        # Count chapters
        chapters = len(list(self.project.list_chapters()))
        self.console.print(f"  Chapters: {chapters}")

        # Commit the export
        self._commit(f"Export to Markdown: {result_path.name}")

    async def copyedit_story(self, args: str):
        """
        Copy edit all chapter prose with full accumulated context.

        Usage:
            /copyedit           # Edit all chapters with preview
            /copyedit --auto    # Auto-apply without preview
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

        # Parse arguments
        skip_confirmation = '--auto' in args

        # Confirm before starting (unless --auto flag provided)
        if not skip_confirmation:
            chapter_count = len(prose_files)
            self.console.print(f"\n[yellow]⚠ Copy Editing Pass[/yellow]")
            self.console.print(f"This will edit {chapter_count} chapter prose files.")
            self.console.print(f"Model: {self.settings.active_model}")
            self.console.print(f"A backup will be created before editing.\n")

            response = input("Continue? [y/N]: ").strip().lower()
            if response != 'y':
                self.console.print("[yellow]Cancelled[/yellow]")
                return

        try:
            # Create copy editor
            from ..generation.copy_editor import CopyEditor
            copy_editor = CopyEditor(self.client, self.project, self.settings.active_model)

            # Run copy editing pass (always auto-apply, no per-chapter prompts)
            result = await copy_editor.copy_edit_all_chapters(
                show_preview=False,  # Never show preview prompt
                auto_apply=True      # Always auto-apply all chapters
            )

            # Show results
            self.console.print(f"\n[green]✓ Copy editing complete![/green]")
            self.console.print(f"Edited: {result['chapters_edited']} chapters")
            if result.get('chapters_skipped', 0) > 0:
                self.console.print(f"Skipped: {result['chapters_skipped']} chapters")
            self.console.print(f"Backup: {Path(result['backup_dir']).relative_to(self.project.path)}")

            # Commit the changes
            self._commit(f"Copy editing pass complete ({result['chapters_edited']} chapters)")

        except Exception as e:
            self.console.print(f"[red]Copy editing failed: {str(e)}[/red]")
            self.logger.exception("Copy editing error")

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

    def multimodel_command(self, args: str = ""):
        """Manage multi-model competition mode."""
        args = args.strip()

        if not args:
            # Toggle mode
            self.settings.multi_model_mode = not self.settings.multi_model_mode

            # Save to config
            config_path = Path('config.yaml')
            self.settings.save_config_file(config_path)

            status = "enabled" if self.settings.multi_model_mode else "disabled"
            self.console.print(f"\n[green]✓ Multi-model mode {status}[/green]")

            if self.settings.multi_model_mode:
                self.console.print("\n[yellow]📋 Multi-model mode active:[/yellow]")
                self.console.print(f"  • Competition models: {', '.join(self.settings.competition_models)}")
                self.console.print(f"  • Judge model: {self.settings.judge_model}")
                self.console.print("\n[dim]Use /multimodel config to customize models[/dim]")

            return

        # Parse subcommand
        parts = args.split(None, 1)
        subcmd = parts[0].lower()

        if subcmd == "config":
            # Show current config with options to change
            self.console.print("\n[bold cyan]Multi-Model Configuration[/bold cyan]\n")

            table = Table(show_header=True)
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="yellow")

            table.add_row("Mode", "Enabled" if self.settings.multi_model_mode else "Disabled")
            table.add_row("Competition Models", ", ".join(self.settings.competition_models))
            table.add_row("Judge Model", self.settings.judge_model)

            self.console.print(table)
            self.console.print()

            # Show options
            self.console.print("[bold]Available actions:[/bold]")
            self.console.print("  /multimodel              - Toggle mode on/off")
            self.console.print("  /multimodel add <model>  - Add a competition model")
            self.console.print("  /multimodel remove <model> - Remove a competition model")
            self.console.print("  /multimodel judge <model> - Set judge model")
            self.console.print("  /multimodel reset        - Reset to defaults")

        elif subcmd == "add":
            if len(parts) < 2:
                self.console.print("[red]Usage: /multimodel add <model-id>[/red]")
                return

            model_id = parts[1].strip()
            if model_id not in self.settings.competition_models:
                self.settings.competition_models.append(model_id)
                config_path = Path('config.yaml')
                self.settings.save_config_file(config_path)
                self.console.print(f"[green]✓ Added {model_id} to competition models[/green]")
            else:
                self.console.print(f"[yellow]{model_id} is already in competition models[/yellow]")

        elif subcmd == "remove":
            if len(parts) < 2:
                self.console.print("[red]Usage: /multimodel remove <model-id>[/red]")
                return

            model_id = parts[1].strip()
            if model_id in self.settings.competition_models:
                if len(self.settings.competition_models) <= 2:
                    self.console.print("[red]Cannot remove - need at least 2 competition models[/red]")
                    return

                self.settings.competition_models.remove(model_id)
                config_path = Path('config.yaml')
                self.settings.save_config_file(config_path)
                self.console.print(f"[green]✓ Removed {model_id} from competition models[/green]")
            else:
                self.console.print(f"[yellow]{model_id} is not in competition models[/yellow]")

        elif subcmd == "judge":
            if len(parts) < 2:
                self.console.print("[red]Usage: /multimodel judge <model-id>[/red]")
                return

            model_id = parts[1].strip()
            self.settings.judge_model = model_id
            config_path = Path('config.yaml')
            self.settings.save_config_file(config_path)
            self.console.print(f"[green]✓ Set judge model to {model_id}[/green]")

        elif subcmd == "reset":
            from ..config.constants import DEFAULT_COMPETITION_MODELS, DEFAULT_JUDGE_MODEL
            self.settings.competition_models = DEFAULT_COMPETITION_MODELS.copy()
            self.settings.judge_model = DEFAULT_JUDGE_MODEL
            config_path = Path('config.yaml')
            self.settings.save_config_file(config_path)
            self.console.print("[green]✓ Reset to default configuration[/green]")

        else:
            self.console.print(f"[red]Unknown subcommand: {subcmd}[/red]")
            self.console.print("[dim]Use /multimodel config for help[/dim]")

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
            self.console.print(f"[red]Error reading log: {e}[/red]")