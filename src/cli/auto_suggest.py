"""Custom auto-suggest for slash commands only."""

from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.document import Document
from prompt_toolkit.history import History


class SlashCommandAutoSuggest(AutoSuggest):
    """Auto-suggest that only suggests slash commands from history."""

    def __init__(self, history: History):
        """Initialize with a history object."""
        self.history = history

    def get_suggestion(self, buffer, document: Document) -> Suggestion | None:
        """Get suggestion only for slash commands."""
        text = document.text

        # Only suggest if text starts with /
        if not text.startswith('/'):
            return None

        # Search history for matching commands
        history_strings = self.history.get_strings()

        # Look for matches (most recent first)
        for history_string in reversed(list(history_strings)):
            if history_string.startswith(text) and history_string != text:
                # Only suggest slash commands
                if history_string.startswith('/'):
                    return Suggestion(history_string[len(text):])

        return None