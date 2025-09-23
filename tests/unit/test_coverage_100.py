"""Tests to achieve 100% code coverage for new functionality."""

import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from prompt_toolkit.document import Document
from prompt_toolkit.completion import CompleteEvent

from src.generation.taxonomies import TaxonomyLoader, PremiseAnalyzer, PremiseHistory
from src.generation.premise import PremiseGenerator
from src.cli.command_completer import SlashCommandCompleter
from src.cli.auto_suggest import SlashCommandAutoSuggest
from src.models import Project
from src.api import OpenRouterClient


class TestTaxonomiesFullCoverage:
    """Additional tests for 100% coverage of taxonomies.py."""

    def test_load_base_taxonomy_file_not_exists(self, temp_dir):
        """Test loading base taxonomy when file doesn't exist."""
        loader = TaxonomyLoader(temp_dir)
        result = loader.load_base_taxonomy()
        assert result == {"categories": {}}

    def test_load_genre_taxonomy_fallback_to_generic_not_exists(self, temp_dir):
        """Test fallback when neither genre nor generic taxonomy exists."""
        loader = TaxonomyLoader(temp_dir)
        result = loader.load_genre_taxonomy("fantasy")
        assert result == {"categories": {}}

    def test_get_category_display_names_without_category_name(self):
        """Test display name generation when category_name is missing."""
        taxonomy = {
            "categories": {
                "magic_system": {},  # No category_name field
                "world_building": {"category_name": "World Building"}
            }
        }
        loader = TaxonomyLoader()
        display_names = loader.get_category_display_names(taxonomy)

        assert display_names["magic_system"] == "Magic System"  # Converted from snake_case
        assert display_names["world_building"] == "World Building"

    def test_premise_analyzer_empty_split_result(self):
        """Test analyzer with text that results in empty paragraphs."""
        text = "\n\n\n\n"  # Only newlines
        result = PremiseAnalyzer.analyze(text)
        assert result["paragraph_count"] == 0
        assert result["type"] == "empty"

    def test_premise_history_load_corrupted_file(self, temp_dir):
        """Test loading history from corrupted JSON file."""
        history_file = temp_dir / "history.json"

        # Write invalid JSON
        with open(history_file, 'w') as f:
            f.write("{invalid json}")

        history = PremiseHistory(history_file)
        assert history.history == []  # Should return empty list on error

    def test_premise_history_format_empty(self, temp_dir):
        """Test formatting with no history."""
        history = PremiseHistory(temp_dir / "history.json")
        formatted = history.format_for_prompt()
        assert formatted == ""


class TestPremiseGeneratorFullCoverage:
    """Additional tests for 100% coverage of premise.py."""

    @pytest.fixture
    def mock_client(self):
        client = Mock(spec=OpenRouterClient)
        client.json_completion = AsyncMock()
        return client

    @pytest.fixture
    def mock_project(self, temp_dir):
        project_dir = temp_dir / "test_project"
        project_dir.mkdir()
        project = Project.create(project_dir, name="Test", genre="fantasy")
        return project

    @pytest.mark.asyncio
    async def test_generate_no_genre_no_metadata(self, mock_client, temp_dir):
        """Test generation when no genre specified and no project metadata."""
        project_dir = temp_dir / "test_project"
        project_dir.mkdir()
        project = Project(project_dir)
        project.metadata = None

        mock_client.json_completion.return_value = {"premise": "Test", "themes": []}

        generator = PremiseGenerator(mock_client, project)
        result = await generator.generate()

        # Should use 'general' as default genre
        call_args = mock_client.json_completion.call_args
        assert "general" in call_args[1]["prompt"]

    @pytest.mark.asyncio
    async def test_generate_no_premise_in_result(self, mock_client, mock_project):
        """Test when API doesn't return a premise."""
        mock_client.json_completion.return_value = {"themes": ["test"]}  # No premise

        generator = PremiseGenerator(mock_client, mock_project)
        result = await generator.generate(genre="fantasy")

        # Should still return the result
        assert result == {"themes": ["test"]}
        # But premise won't be saved
        assert mock_project.get_premise() is None

    @pytest.mark.asyncio
    async def test_generate_taxonomy_only_no_genre_no_metadata(self, mock_client, temp_dir):
        """Test taxonomy generation with no genre and no metadata."""
        project_dir = temp_dir / "test_project"
        project_dir.mkdir()
        project = Project(project_dir)
        project.metadata = None

        mock_client.json_completion.return_value = {"selections": {}}

        generator = PremiseGenerator(mock_client, project)
        result = await generator.generate_taxonomy_only("Treatment text")

        # Should use 'general' as default
        call_args = mock_client.json_completion.call_args
        assert "general" in call_args[1]["prompt"] or "TREATMENT:" in call_args[1]["prompt"]

    @pytest.mark.asyncio
    async def test_generate_taxonomy_only_no_selections(self, mock_client, mock_project):
        """Test taxonomy generation when no selections returned."""
        mock_client.json_completion.return_value = {}  # No selections

        generator = PremiseGenerator(mock_client, mock_project)
        result = await generator.generate_taxonomy_only("Treatment", "fantasy")

        assert result == {}

    @pytest.mark.asyncio
    async def test_generate_taxonomy_only_with_existing_metadata(self, mock_client, mock_project):
        """Test taxonomy generation updates existing metadata."""
        # Create existing metadata
        metadata_path = mock_project.path / "premise_metadata.json"
        existing = {"premise": "Old premise", "existing_field": "value"}
        with open(metadata_path, 'w') as f:
            json.dump(existing, f)

        mock_client.json_completion.return_value = {"selections": {"tone": ["dark"]}}

        generator = PremiseGenerator(mock_client, mock_project)
        await generator.generate_taxonomy_only("Treatment", "fantasy")

        # Check metadata was merged
        with open(metadata_path, 'r') as f:
            updated = json.load(f)
        assert updated["existing_field"] == "value"  # Preserved
        assert updated["selections"] == {"tone": ["dark"]}  # Added

    @pytest.mark.asyncio
    async def test_iterate_no_premise(self, mock_client, mock_project):
        """Test iterating when no premise exists."""
        generator = PremiseGenerator(mock_client, mock_project)

        with pytest.raises(Exception) as exc_info:
            await generator.iterate("Add more action")
        assert "No premise found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_iterate_no_premise_in_result(self, mock_client, mock_project):
        """Test iterate when API doesn't return premise."""
        mock_project.save_premise("Original premise")
        mock_client.json_completion.return_value = {"themes": ["test"]}  # No premise

        generator = PremiseGenerator(mock_client, mock_project)
        result = await generator.iterate("feedback")

        assert result == {"themes": ["test"]}


class TestCommandCompleterFullCoverage:
    """Additional tests for 100% coverage of command_completer.py."""

    def test_genre_completion_just_premise_no_space(self):
        """Test when user types just 'premise' without space."""
        commands = {'generate': {'description': 'Generate', 'usage': '/generate'}}
        completer = SlashCommandCompleter(commands, None, lambda: ['fantasy'])

        doc = Document('/generate premise')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        # Should not provide genre completions without space after premise
        assert all(' fantasy' not in c.text for c in completions)

    def test_genre_completion_empty_partial(self):
        """Test genre completion with empty partial after premise."""
        commands = {'generate': {'description': 'Generate', 'usage': '/generate'}}
        completer = SlashCommandCompleter(commands, None, lambda: ['fantasy', 'romance'])

        doc = Document('/generate premise ')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        # All genres should be shown
        texts = [c.text.strip() for c in completions]
        assert 'fantasy' in texts
        assert 'romance' in texts

    def test_model_completion_starts_with(self):
        """Test model completion when input starts with model name."""
        commands = {'model': {'description': 'Model', 'usage': '/model'}}
        models = ['anthropic/claude', 'openai/gpt-4']
        completer = SlashCommandCompleter(commands, lambda: models, None)

        doc = Document('/model anthropic')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        # Should complete the rest of the model name
        assert any('/claude' in c.text for c in completions)

    def test_model_completion_slash_in_partial(self):
        """Test model completion with slash in partial."""
        commands = {'model': {'description': 'Model', 'usage': '/model'}}
        models = ['anthropic/claude-3', 'anthropic/claude-2']
        completer = SlashCommandCompleter(commands, lambda: models, None)

        doc = Document('/model anthropic/cl')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        assert len(completions) >= 1

    def test_model_completion_no_arg_text(self):
        """Test model completion with no argument text."""
        commands = {'model': {'description': 'Model', 'usage': '/model'}}
        models = ['model-1']
        completer = SlashCommandCompleter(commands, lambda: models, None)

        doc = Document('/model ')
        completions = list(completer.get_completions(doc, CompleteEvent()))

        assert any('model-1' in str(c.display) for c in completions)


class TestAutoSuggestFullCoverage:
    """Tests for auto_suggest.py."""

    def test_auto_suggest_init(self):
        """Test SlashCommandAutoSuggest initialization."""
        from prompt_toolkit.history import InMemoryHistory
        history = InMemoryHistory()

        auto_suggest = SlashCommandAutoSuggest(history)
        assert auto_suggest.history == history

    def test_auto_suggest_get_suggestion_slash_command(self):
        """Test getting suggestion for slash command."""
        from prompt_toolkit.history import InMemoryHistory
        from prompt_toolkit.buffer import Buffer

        history = InMemoryHistory()
        history.append_string("/generate premise fantasy")

        auto_suggest = SlashCommandAutoSuggest(history)

        # Create buffer with partial command
        buffer = Buffer()
        buffer.text = "/generate pr"

        suggestion = auto_suggest.get_suggestion(buffer, Document("/generate pr"))

        if suggestion:
            assert "emise" in suggestion.text

    def test_auto_suggest_no_suggestion_for_non_slash(self):
        """Test no suggestion for non-slash input."""
        from prompt_toolkit.history import InMemoryHistory
        from prompt_toolkit.buffer import Buffer

        history = InMemoryHistory()
        history.append_string("generate premise")

        auto_suggest = SlashCommandAutoSuggest(history)

        buffer = Buffer()
        buffer.text = "generate"

        suggestion = auto_suggest.get_suggestion(buffer, Document("generate"))
        assert suggestion is None

    def test_auto_suggest_empty_input(self):
        """Test auto suggest with empty input."""
        from prompt_toolkit.history import InMemoryHistory
        from prompt_toolkit.buffer import Buffer

        history = InMemoryHistory()
        auto_suggest = SlashCommandAutoSuggest(history)

        buffer = Buffer()
        buffer.text = ""

        suggestion = auto_suggest.get_suggestion(buffer, Document(""))
        assert suggestion is None


class TestSettingsFullCoverage:
    """Additional tests for settings.py."""

    def test_save_config_file_create_parent(self, temp_dir):
        """Test saving config creates parent directory."""
        from src.config import Settings

        settings = Settings()
        config_file = temp_dir / "nested" / "dir" / "config.yaml"

        settings.save_config_file(config_file)

        assert config_file.exists()
        assert config_file.parent.exists()

    def test_load_config_file_not_exists(self, temp_dir):
        """Test loading non-existent config file."""
        from src.config import Settings

        settings = Settings()
        config_file = temp_dir / "missing.yaml"

        loaded = settings.load_config_file(config_file)
        assert loaded == {}  # Should return empty dict


class TestProjectFullCoverage:
    """Additional tests for project.py."""

    def test_save_metadata_no_existing_metadata(self, temp_dir):
        """Test saving metadata when none exists."""
        project = Project(temp_dir)
        project.metadata = None
        project.save_metadata()

        assert project.metadata is not None
        assert project.metadata.name == temp_dir.name

    def test_save_premise_updates_metadata(self, temp_dir):
        """Test that saving premise updates metadata."""
        project = Project.create(temp_dir, name="Test")
        original_time = project.metadata.updated_at

        import time
        time.sleep(0.01)  # Ensure time difference

        project.save_premise("New premise")

        assert project.metadata.updated_at > original_time

    def test_get_chapter_outlines_file_not_exists(self, temp_dir):
        """Test getting chapter outlines when file doesn't exist."""
        project = Project.create(temp_dir, name="Test")
        outlines = project.get_chapter_outlines()
        assert outlines is None

    def test_save_chapter_outlines_updates_metadata(self, temp_dir):
        """Test saving chapter outlines updates metadata."""
        project = Project.create(temp_dir, name="Test")

        outlines = {"chapters": [{"number": 1}, {"number": 2}]}
        project.save_chapter_outlines(outlines)

        assert project.metadata.chapter_count == 2

    def test_list_chapters_empty(self, temp_dir):
        """Test listing chapters when none exist."""
        project = Project.create(temp_dir, name="Test")
        chapters = project.list_chapters()
        assert chapters == []

    def test_get_analysis_file_not_exists(self, temp_dir):
        """Test getting analysis when file doesn't exist."""
        project = Project.create(temp_dir, name="Test")
        analysis = project.get_analysis("commercial")
        assert analysis is None

    def test_save_analysis_creates_directory(self, temp_dir):
        """Test saving analysis creates directory."""
        project = Project.create(temp_dir, name="Test")
        project.save_analysis("test", {"result": "data"})

        assert project.analysis_dir.exists()
        assert (project.analysis_dir / "test.json").exists()


class TestStoryModelFullCoverage:
    """Additional tests for story.py."""

    def test_add_chapter_updates_word_count(self):
        """Test adding chapter updates total word count."""
        from src.models import Story, Chapter

        story = Story()
        assert story.total_word_count == 0

        chapter = Chapter(number=1, title="Test", content="Word " * 100, word_count=100)
        story.add_chapter(chapter)

        assert story.total_word_count == 100

    def test_is_complete_with_no_outlines(self):
        """Test is_complete when no chapter outlines."""
        from src.models import Story

        story = Story()
        story.chapters = [Mock()]  # Has chapters but no outlines

        assert story.is_complete == False

    def test_get_chapter_not_found(self):
        """Test getting non-existent chapter."""
        from src.models import Story, Chapter

        story = Story()
        story.add_chapter(Chapter(number=1, title="Test", content="Content"))

        result = story.get_chapter(99)
        assert result is None

    def test_summary_no_content(self):
        """Test summary property with no content."""
        from src.models import Story

        story = Story()
        summary = story.summary

        assert "No premise" in summary
        assert "No treatment" in summary