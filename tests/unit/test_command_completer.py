"""Tests for command completion and genre autocomplete."""

import pytest
from prompt_toolkit.document import Document
from prompt_toolkit.completion import CompleteEvent

from src.cli.command_completer import SlashCommandCompleter, create_command_descriptions


class TestSlashCommandCompleter:
    """Test command completion functionality."""

    @pytest.fixture
    def completer(self):
        """Create a command completer with test commands."""
        commands = {
            'help': {'description': 'Show help', 'usage': '/help'},
            'generate': {'description': 'Generate content', 'usage': '/generate <type>'},
            'model': {'description': 'Change model', 'usage': '/model <name>'},
        }

        def model_provider():
            return ['anthropic/claude-3-opus', 'openai/gpt-4', 'meta-llama/llama-2']

        def genre_provider():
            return ['fantasy', 'romance', 'mystery', 'science-fiction']

        return SlashCommandCompleter(commands, model_provider, genre_provider)

    def test_complete_slash_commands(self, completer):
        """Test basic slash command completion."""
        doc = Document('/he')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        assert len(completions) == 1
        assert completions[0].text == 'lp'
        # Check display contains help
        display_text = str(completions[0].display)
        assert 'help' in display_text.lower()

    def test_complete_multiple_matches(self, completer):
        """Test completion with multiple matches."""
        doc = Document('/')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        # Should return all commands
        assert len(completions) >= 3
        command_names = [c.text for c in completions]
        assert 'help' in command_names
        assert 'generate' in command_names
        assert 'model' in command_names

    def test_no_completion_without_slash(self, completer):
        """Test that completion doesn't trigger without slash."""
        doc = Document('help')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        assert len(completions) == 0

    def test_model_completion(self, completer):
        """Test model ID completion."""
        doc = Document('/model claude')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        assert len(completions) >= 1
        # Should find Claude model
        assert any('claude' in str(c.display).lower() for c in completions)

    def test_model_completion_fuzzy(self, completer):
        """Test fuzzy model matching."""
        doc = Document('/model gpt')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        assert len(completions) >= 1
        # Should find GPT model
        assert any('gpt' in str(c.display).lower() for c in completions)

    def test_genre_completion_after_premise(self, completer):
        """Test genre completion for /generate premise."""
        doc = Document('/generate premise ')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        assert len(completions) == 4
        genre_names = [c.text.strip() for c in completions]
        assert 'fantasy' in genre_names
        assert 'romance' in genre_names
        assert 'mystery' in genre_names
        assert 'science-fiction' in genre_names

    def test_genre_completion_partial(self, completer):
        """Test partial genre name completion."""
        doc = Document('/generate premise fan')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        assert len(completions) >= 1
        # Should complete to 'fantasy'
        assert completions[0].text == 'tasy'

    def test_genre_completion_case_insensitive(self, completer):
        """Test case-insensitive genre completion."""
        doc = Document('/generate premise ROM')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        assert len(completions) >= 1
        # Should find romance
        assert any('romance' in str(c.display).lower() for c in completions)

    def test_command_descriptions(self):
        """Test creating command descriptions."""
        descriptions = create_command_descriptions()

        assert 'help' in descriptions
        assert 'generate' in descriptions
        assert 'model' in descriptions
        assert 'new' in descriptions

        # Check structure
        assert 'description' in descriptions['help']
        assert 'usage' in descriptions['help']

    def test_no_completion_after_complete_command(self, completer):
        """Test no completion after a complete command with args."""
        doc = Document('/help something')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        # Should not provide completions for help arguments
        assert len(completions) == 0

    def test_model_provider_failure(self, completer):
        """Test graceful handling when model provider fails."""
        def failing_provider():
            raise Exception("Provider failed")

        completer.model_provider = failing_provider

        doc = Document('/model ')
        # Should not raise, just return no completions
        completions = list(completer.get_completions(doc, CompleteEvent()))
        assert completions == []

    def test_genre_provider_none(self):
        """Test completer without genre provider."""
        commands = {'generate': {'description': 'Generate', 'usage': '/generate'}}
        completer = SlashCommandCompleter(commands, None, None)

        doc = Document('/generate premise ')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        # Should return empty when no genre provider
        assert len(completions) == 0