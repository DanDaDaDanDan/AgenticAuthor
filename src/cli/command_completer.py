"""Custom command completer for slash commands."""
from typing import List, Dict, Optional, Iterable
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML


class SlashCommandCompleter(Completer):
    """Completer for slash commands with descriptions."""

    def __init__(self, commands: Dict[str, Dict[str, str]]):
        """
        Initialize the slash command completer.

        Args:
            commands: Dict mapping command names to their info:
                     {'command': {'description': '...', 'usage': '...'}}
        """
        self.commands = commands

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

        # If there's a space, we're past the command
        if ' ' in command_text:
            # Could add argument completion here later
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
            'description': 'Generate content (premise/treatment/chapters/prose)',
            'usage': '/generate <type> [options]'
        },
        'iterate': {
            'description': 'Iterate on existing content',
            'usage': '/iterate <feedback>'
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
            'description': 'Run git commands',
            'usage': '/git <command>'
        },
        'config': {
            'description': 'Show or set configuration',
            'usage': '/config [key] [value]'
        },
        'clear': {
            'description': 'Clear the screen',
            'usage': '/clear'
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