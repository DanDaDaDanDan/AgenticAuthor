"""Main CLI entry point using Typer."""
import sys
import asyncio
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich import print as rprint

from ..config import get_settings, Settings
from .interactive import InteractiveSession


app = typer.Typer(
    name="agentic",
    help="AgenticAuthor - AI-powered iterative book generation",
    add_completion=True,
    rich_markup_mode="rich",
)

console = Console()


@app.command(name="repl", help="Start interactive REPL session")
def repl(
    project: Optional[str] = typer.Argument(
        None,
        help="Project name or path to open"
    )
):
    """Start interactive REPL session."""
    try:
        # Resolve project path if provided
        project_path = None
        if project:
            settings = get_settings()
            # Check if it's a project name in books directory
            potential_path = settings.books_dir / project
            if potential_path.exists():
                project_path = potential_path
            else:
                # Try as direct path
                direct_path = Path(project).expanduser().resolve()
                if direct_path.exists():
                    project_path = direct_path
                else:
                    console.print(f"[red]Project not found: {project}[/red]")
                    raise typer.Exit(1)

        # Create and run session
        session = InteractiveSession(project_path)
        asyncio.run(session.run())

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command(help="Create a new book project")
def new(
    name: str = typer.Argument(..., help="Project name"),
    genre: Optional[str] = typer.Option(
        None,
        "--genre", "-g",
        help="Story genre (e.g., fantasy, scifi, romance)"
    ),
    author: Optional[str] = typer.Option(
        None,
        "--author", "-a",
        help="Author name"
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive", "-i/-n",
        help="Start interactive session after creation"
    )
):
    """Create a new book project."""
    try:
        settings = get_settings()
        from ..models import Project

        # Create project directory
        project_dir = settings.books_dir / name
        if project_dir.exists():
            console.print(f"[red]Project '{name}' already exists[/red]")
            raise typer.Exit(1)

        # Create project
        console.print(f"[cyan]Creating project: {name}[/cyan]")
        project = Project.create(
            project_dir,
            name=name,
            genre=genre,
            author=author,
            model=settings.active_model
        )

        # Initialize git
        from ..storage import GitManager
        git = GitManager(project.path)
        git.init()
        git.commit("Initial project creation")

        console.print(f"[green]✓ Created project: {name}[/green]")
        console.print(f"[dim]Location: {project_dir}[/dim]")

        # Start interactive session if requested
        if interactive:
            console.print("\n[cyan]Starting interactive session...[/cyan]")
            session = InteractiveSession(project_dir)
            asyncio.run(session.run())

    except Exception as e:
        console.print(f"[red]Error creating project: {e}[/red]")
        raise typer.Exit(1)


@app.command(help="List available projects")
def list():
    """List all available projects."""
    try:
        settings = get_settings()
        from ..models import Project

        projects = []
        for project_dir in settings.books_dir.glob("*"):
            if (project_dir / "project.yaml").exists():
                try:
                    project = Project(project_dir)
                    if project.metadata:
                        projects.append({
                            'name': project.name,
                            'genre': project.metadata.genre or "—",
                            'status': project.metadata.status,
                            'words': project.metadata.word_count,
                            'updated': str(project.metadata.updated_at)[:10]
                        })
                except Exception:
                    continue

        if not projects:
            console.print("[yellow]No projects found[/yellow]")
            console.print(f"[dim]Create one with: agentic new <name>[/dim]")
            return

        # Display as table
        from rich.table import Table
        table = Table(title="Book Projects")
        table.add_column("Name", style="cyan")
        table.add_column("Genre")
        table.add_column("Status")
        table.add_column("Words", justify="right")
        table.add_column("Updated")

        for p in sorted(projects, key=lambda x: x['updated'], reverse=True):
            table.add_row(
                p['name'],
                p['genre'],
                p['status'],
                f"{p['words']:,}" if p['words'] > 0 else "—",
                p['updated']
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing projects: {e}[/red]")
        raise typer.Exit(1)


@app.command(help="Show or set configuration")
def config(
    key: Optional[str] = typer.Argument(None, help="Config key to show/set"),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
    list_all: bool = typer.Option(
        False,
        "--list", "-l",
        help="List all configuration values"
    )
):
    """Show or set configuration values."""
    try:
        settings = get_settings()

        if list_all or not key:
            # Show all config
            from rich.table import Table
            table = Table(title="Configuration")
            table.add_column("Key", style="cyan")
            table.add_column("Value")

            # Add important settings
            config_items = [
                ("api_key", f"{settings.openrouter_api_key[:10]}..."),
                ("default_model", settings.default_model),
                ("books_dir", str(settings.books_dir)),
                ("taxonomies_dir", str(settings.taxonomies_dir)),
                ("auto_commit", str(settings.auto_commit)),
                ("streaming_output", str(settings.streaming_output)),
                ("show_token_usage", str(settings.show_token_usage)),
            ]

            for k, v in config_items:
                table.add_row(k, v)

            console.print(table)

        elif value is None:
            # Show specific key
            if hasattr(settings, key):
                val = getattr(settings, key)
                console.print(f"{key}: {val}")
            else:
                console.print(f"[red]Unknown config key: {key}[/red]")
                raise typer.Exit(1)

        else:
            # Set value
            if hasattr(settings, key):
                # Convert value type
                current = getattr(settings, key)
                if isinstance(current, bool):
                    value = value.lower() in ('true', '1', 'yes', 'on')
                elif isinstance(current, int):
                    value = int(value)
                elif isinstance(current, float):
                    value = float(value)

                setattr(settings, key, value)

                # Save to config file
                config_path = Path("config.yaml")
                settings.save_config_file(config_path)

                console.print(f"[green]✓ Set {key} = {value}[/green]")
            else:
                console.print(f"[red]Unknown config key: {key}[/red]")
                raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command(help="Discover available AI models")
def models(
    search: Optional[str] = typer.Argument(None, help="Search term"),
    free: bool = typer.Option(False, "--free", "-f", help="Show only free models"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of models to show")
):
    """List available AI models from OpenRouter."""
    async def _discover():
        try:
            from ..api import OpenRouterClient

            console.print("[cyan]Fetching available models...[/cyan]")
            client = OpenRouterClient(console=console)

            try:
                models = await client.discover_models()

                # Filter
                if search:
                    search_lower = search.lower()
                    models = [m for m in models if search_lower in m.id.lower() or
                             (m.name and search_lower in m.name.lower())]

                if free:
                    models = [m for m in models if m.is_free]

                if not models:
                    console.print("[yellow]No models found matching criteria[/yellow]")
                    return

                # Sort by price
                models.sort(key=lambda m: m.cost_per_1k_tokens)

                # Display
                from rich.table import Table
                table = Table(title=f"Available Models{' (Free)' if free else ''}")
                table.add_column("Model ID", style="cyan")
                table.add_column("Context", justify="right")
                table.add_column("$/1K Tokens", justify="right")

                for model in models[:limit]:
                    price = f"${model.cost_per_1k_tokens:.4f}"
                    if model.is_free:
                        price = "[green]Free[/green]"

                    table.add_row(
                        model.id,
                        f"{model.context_length:,}",
                        price
                    )

                console.print(table)

                if len(models) > limit:
                    console.print(f"\n[dim]Showing {limit} of {len(models)} models[/dim]")

            finally:
                await client.close()

        except Exception as e:
            console.print(f"[red]Error fetching models: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(_discover())


@app.command(help="Show version information")
def version():
    """Show version information."""
    console.print("[cyan]AgenticAuthor v1.0.0[/cyan]")
    console.print("[dim]AI-powered iterative book generation[/dim]")


# Default command when no subcommand is provided
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version", "-v",
        help="Show version"
    )
):
    """
    AgenticAuthor - AI-powered iterative book generation.

    Run without arguments to start interactive REPL.
    """
    if version:
        console.print("[cyan]AgenticAuthor v1.0.0[/cyan]")
        raise typer.Exit()

    # If no command provided, start REPL immediately
    if ctx.invoked_subcommand is None:
        # Start REPL without project - user can create/open projects from within REPL
        repl(None)


if __name__ == "__main__":
    app()