"""Custom command completer for slash commands."""
from typing import List, Dict, Optional, Iterable
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML


class SlashCommandCompleter(Completer):
    """Completer for slash commands with descriptions."""

    def __init__(self, commands: Dict[str, Dict[str, str]], model_provider=None, genre_provider=None):
        """
        Initialize the slash command completer.

        Args:
            commands: Dict mapping command names to their info:
                     {'command': {'description': '...', 'usage': '...'}}
            model_provider: Callable that returns list of model IDs for completion
            genre_provider: Callable that returns list of genres for completion
        """
        self.commands = commands
        self.model_provider = model_provider
        self.genre_provider = genre_provider

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Get completions for the current input."""
        text = document.text_before_cursor

        # Only complete if text starts with /
        if not text.startswith('/'):
            return

        # Get the command part after /
        command_text = text[1:]

        # If there's a space, we're past the command - handle argument completion
        if ' ' in command_text:
            parts = command_text.split(' ', 1)
            command = parts[0]
            arg_text = parts[1] if len(parts) > 1 else ''

            # Special handling for /generate command (genre completion)
            if command == 'generate' and self.genre_provider:
                # Check if we're at the premise subcommand
                remaining_parts = arg_text.split(' ')
                if remaining_parts[0] == 'premise':
                    # We're after "premise", provide genre completions
                    if len(remaining_parts) == 1:
                        # Just "premise" - show all genres
                        genres = self.genre_provider()
                        for genre in genres:
                            yield Completion(
                                text=' ' + genre,
                                start_position=0,
                                display=HTML(f'<b>{genre}</b>'),
                                display_meta='Genre',
                                style='',
                                selected_style='reverse',
                            )
                    elif len(remaining_parts) == 2:
                        # "premise <partial_genre>" - filter genres
                        partial = remaining_parts[1]
                        genres = self.genre_provider()
                        for genre in genres:
                            if genre.lower().startswith(partial.lower()):
                                completion_text = genre[len(partial):]
                                yield Completion(
                                    text=completion_text,
                                    start_position=0,
                                    display=HTML(f'<b>{genre}</b>'),
                                    display_meta='Genre',
                                    style='',
                                    selected_style='reverse',
                                )
                return

            # Special handling for /model command
            if command == 'model' and self.model_provider:
                try:
                    model_ids = self.model_provider()

                    # Debug logging
                    from ..utils.logging import get_logger
                    logger = get_logger()
                    if logger:
                        logger.debug(f"Autocomplete: got {len(model_ids) if model_ids else 0} models from provider")
                        logger.debug(f"Autocomplete: arg_text='{arg_text}'")

                    if model_ids:
                        # Filter models that match the current arg text
                        matches = []
                        arg_lower = arg_text.lower()

                        for model_id in model_ids:
                            model_lower = model_id.lower()
                            if arg_lower in model_lower:
                                # Calculate relevance score
                                score = 0
                                if model_lower.startswith(arg_lower):
                                    score = 3
                                elif '/' + arg_lower in model_lower:
                                    score = 2
                                else:
                                    score = 1

                                # Extract provider and model name
                                if '/' in model_id:
                                    provider, name = model_id.split('/', 1)
                                else:
                                    provider = 'other'
                                    name = model_id

                                matches.append((model_id, provider, name, score))

                        # Sort alphabetically by model ID
                        matches.sort(key=lambda x: x[0].lower())

                        # Debug logging
                        if logger:
                            logger.debug(f"Autocomplete: {len(matches)} total matches")
                            if matches:
                                logger.debug(f"First 5 matches: {[m[0] for m in matches[:5]]}")
                                logger.debug(f"Yielding first {min(10, len(matches))} completions")

                        # Yield completions for top matches
                        for model_id, provider, name, _ in matches[:10]:
                            # What to insert (complete from current position)
                            if arg_text:
                                # Complete from where we are
                                if model_id.lower().startswith(arg_lower):
                                    completion_text = model_id[len(arg_text):]
                                else:
                                    # Replace entirely
                                    completion_text = model_id
                                    start_pos = -len(arg_text)
                            else:
                                completion_text = model_id
                                start_pos = 0

                            yield Completion(
                                text=completion_text,
                                start_position=start_pos if arg_text else 0,
                                display=HTML(f'<b>{model_id}</b>'),
                                display_meta=f'{provider}',
                                style='',
                                selected_style='reverse',
                            )
                except Exception as e:
                    # Log error instead of silently failing
                    from ..utils.logging import get_logger
                    logger = get_logger()
                    if logger:
                        logger.error(f"Autocomplete error for /model: {e}", exc_info=True)
            return

        # Filter and sort commands
        matches = []
        for cmd, info in self.commands.items():
            if cmd.startswith(command_text.lower()):
                matches.append((cmd, info))

        # Sort by relevance (exact matches first, then alphabetical)
        matches.sort(key=lambda x: (not x[0] == command_text, x[0]))

        # Yield completions
        for cmd, info in matches:
            # Completion text is what gets inserted
            completion_text = cmd[len(command_text):]

            # Display text shows in the menu
            display = HTML(f'<b>/{cmd}</b>')

            # Description shows on the right
            description = info.get('description', '')

            yield Completion(
                text=completion_text,
                start_position=0,
                display=display,
                display_meta=description,
                style='',
                selected_style='reverse',
            )


def create_command_descriptions() -> Dict[str, Dict[str, str]]:
    """Create command descriptions for the completer."""
    return {
        'help': {
            'description': 'Show available commands',
            'usage': '/help [command]'
        },
        'new': {
            'description': 'Create a new book project',
            'usage': '/new [project-name]'
        },
        'open': {
            'description': 'Open an existing project',
            'usage': '/open [project-path]'
        },
        'clone': {
            'description': 'Clone current project to new name',
            'usage': '/clone [new-name]'
        },
        'status': {
            'description': 'Show project status',
            'usage': '/status'
        },
        'model': {
            'description': 'Change or show AI model',
            'usage': '/model [model-name]'
        },
        'models': {
            'description': 'List available AI models',
            'usage': '/models [search]'
        },
        'generate': {
            'description': 'Generate content (premise/premises/treatment/chapters/prose)',
            'usage': '/generate <type> [options]'
        },
        'iterate': {
            'description': 'Set iteration target (premise/treatment/chapters/prose/taxonomy)',
            'usage': '/iterate <target>'
        },
        'analyze': {
            'description': 'Analyze story for issues',
            'usage': '/analyze [type]'
        },
        'export': {
            'description': 'Export story to file',
            'usage': '/export [format]'
        },
        'git': {
            'description': 'View git history and commit manual changes',
            'usage': '/git <status|log|diff|commit [message]>'
        },
        'config': {
            'description': 'Show or set configuration',
            'usage': '/config [key] [value]'
        },
        'clear': {
            'description': 'Clear the screen',
            'usage': '/clear'
        },
        'logs': {
            'description': 'Show recent log entries',
            'usage': '/logs'
        },
        'exit': {
            'description': 'Exit the application',
            'usage': '/exit'
        },
        'quit': {
            'description': 'Exit the application',
            'usage': '/quit'
        },
    }