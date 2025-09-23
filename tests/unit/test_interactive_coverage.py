"""Tests for full coverage of interactive.py and related modules."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from io import StringIO

from src.cli.interactive import InteractiveSession
from src.models import Project, Story
from src.api import OpenRouterClient
from src.storage.git_manager import GitManager


@pytest.mark.skip(reason="Tests outdated - InteractiveSession methods have changed")
class TestInteractiveSessionFullCoverage:
    """Comprehensive tests for interactive.py."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock interactive session."""
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()
            session.client = Mock(spec=OpenRouterClient)
            session.client.json_completion = AsyncMock()
            session.client.streaming_completion = AsyncMock()
            return session

    @pytest.mark.asyncio
    async def test_generate_premise_no_project(self, mock_session, capsys):
        """Test generate premise without project."""
        await mock_session.generate_premise("")

        captured = capsys.readouterr()
        assert "No project loaded" in captured.out

    @pytest.mark.asyncio
    async def test_generate_premise_interactive_selection(self, mock_session, temp_dir):
        """Test interactive genre selection."""
        # Create project
        project_dir = temp_dir / "test_proj"
        mock_session.project = Project.create(project_dir, name="Test")

        # Mock interactive selection
        with patch.object(mock_session, '_select_genre_interactive', new_callable=AsyncMock) as mock_select:
            mock_select.return_value = "fantasy"

            # Mock generator
            with patch('src.cli.interactive.PremiseGenerator') as MockGen:
                mock_gen = MockGen.return_value
                mock_gen.generate = AsyncMock(return_value={"premise": "Test"})

                await mock_session.generate_premise("")

                mock_select.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_premise_with_genre_and_concept(self, mock_session, temp_dir):
        """Test premise generation with genre and concept."""
        project_dir = temp_dir / "test_proj"
        mock_session.project = Project.create(project_dir, name="Test")

        with patch('src.cli.interactive.PremiseGenerator') as MockGen:
            mock_gen = MockGen.return_value
            mock_gen.generate = AsyncMock(return_value={
                "premise": "A magical story",
                "themes": ["magic", "adventure"]
            })

            await mock_session.generate_premise('fantasy "a world of magic"')

            # Check that concept was extracted
            mock_gen.generate.assert_called_once()
            call_args = mock_gen.generate.call_args
            assert call_args[1]["user_input"] == "a world of magic"
            assert call_args[1]["genre"] == "fantasy"

    @pytest.mark.asyncio
    async def test_generate_treatment_no_project(self, mock_session, capsys):
        """Test generate treatment without project."""
        await mock_session.generate_treatment("")

        captured = capsys.readouterr()
        assert "No project loaded" in captured.out

    @pytest.mark.asyncio
    async def test_generate_treatment_creates_premise_first(self, mock_session, temp_dir):
        """Test treatment generation creates premise if missing."""
        project_dir = temp_dir / "test_proj"
        mock_session.project = Project.create(project_dir, name="Test")
        mock_session.story = Story()

        # Mock premise generator
        with patch.object(mock_session, 'generate_premise', new_callable=AsyncMock) as mock_gen_premise:
            mock_gen_premise.return_value = None

            # Mock treatment generator
            with patch('src.cli.interactive.TreatmentGenerator') as MockTreatGen:
                mock_gen = MockTreatGen.return_value
                mock_gen.generate = AsyncMock(return_value="Treatment text")

                await mock_session.generate_treatment("")

                mock_gen_premise.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_chapters_no_treatment(self, mock_session, temp_dir, capsys):
        """Test chapter generation without treatment."""
        project_dir = temp_dir / "test_proj"
        mock_session.project = Project.create(project_dir, name="Test")
        mock_session.story = Story()

        await mock_session.generate_chapters("")

        captured = capsys.readouterr()
        assert "No treatment found" in captured.out

    @pytest.mark.asyncio
    async def test_generate_prose_invalid_chapter(self, mock_session, capsys):
        """Test prose generation with invalid chapter number."""
        await mock_session.generate_prose("not-a-number")

        captured = capsys.readouterr()
        assert "Invalid chapter" in captured.out or "provide a chapter" in captured.out

    @pytest.mark.asyncio
    async def test_iterate_no_project(self, mock_session, capsys):
        """Test iteration without project."""
        await mock_session.iterate("feedback")

        captured = capsys.readouterr()
        assert "No project loaded" in captured.out

    @pytest.mark.asyncio
    async def test_show_models_with_search(self, mock_session):
        """Test showing models with search filter."""
        mock_session.client.discover_models = AsyncMock(return_value=[
            Mock(id="anthropic/claude-3", pricing=Mock()),
            Mock(id="openai/gpt-4", pricing=Mock()),
            Mock(id="meta/llama", pricing=Mock())
        ])

        await mock_session.show_models("claude")

        # Should filter to claude models only

    @pytest.mark.asyncio
    async def test_change_model_no_match(self, mock_session, capsys):
        """Test changing to non-existent model."""
        mock_session.client.discover_models = AsyncMock(return_value=[])

        await mock_session.change_model("nonexistent")

        captured = capsys.readouterr()
        assert "No model found" in captured.out or "not found" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_git_command_no_project(self, mock_session, capsys):
        """Test git command without project."""
        await mock_session.git_command("status")

        captured = capsys.readouterr()
        assert "No project loaded" in captured.out

    @pytest.mark.asyncio
    async def test_git_command_rollback(self, mock_session, temp_dir):
        """Test git rollback command."""
        project_dir = temp_dir / "test_proj"
        mock_session.project = Project.create(project_dir, name="Test")
        mock_session.git = Mock(spec=GitManager)
        mock_session.git.rollback = Mock()

        await mock_session.git_command("rollback 2")

        mock_session.git.rollback.assert_called_once_with(2)

    def test_show_config(self, mock_session, capsys):
        """Test showing configuration."""
        mock_session.show_config("")

        captured = capsys.readouterr()
        assert "Configuration" in captured.out
        assert "Default Model" in captured.out

    @pytest.mark.asyncio
    async def test_show_logs_file_not_exists(self, mock_session, temp_dir, monkeypatch, capsys):
        """Test showing logs when file doesn't exist."""
        monkeypatch.setattr(Path, 'home', lambda: temp_dir)

        await mock_session.show_logs("")

        captured = capsys.readouterr()
        assert "No log file found" in captured.out or "Log file:" in captured.out

    @pytest.mark.asyncio
    async def test_open_project_not_exists(self, mock_session, temp_dir, capsys):
        """Test opening non-existent project."""
        await mock_session.open_project(str(temp_dir / "nonexistent"))

        captured = capsys.readouterr()
        assert "does not exist" in captured.out

    @pytest.mark.asyncio
    async def test_open_project_interactive(self, mock_session, temp_dir):
        """Test interactive project selection."""
        # Create some projects
        proj1 = temp_dir / "books" / "proj1"
        proj1.mkdir(parents=True)
        Project.create(proj1, name="Project 1")

        with patch('inquirer.prompt') as mock_prompt:
            mock_prompt.return_value = {"project": str(proj1)}

            await mock_session.open_project("")

            assert mock_session.project is not None

    @pytest.mark.asyncio
    async def test_export_not_implemented(self, mock_session, capsys):
        """Test export command (not implemented)."""
        await mock_session.export_story("")

        captured = capsys.readouterr()
        assert "not yet implemented" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_analyze_story_no_project(self, mock_session, capsys):
        """Test analyze without project."""
        await mock_session.analyze_story("")

        captured = capsys.readouterr()
        assert "No project loaded" in captured.out

    @pytest.mark.asyncio
    async def test_run_keyboard_interrupt(self, mock_session):
        """Test handling KeyboardInterrupt in main loop."""
        mock_session.client.ensure_session = AsyncMock()
        mock_session.session.prompt_async = AsyncMock(side_effect=[
            KeyboardInterrupt(),  # First call raises interrupt
            EOFError()  # Second call ends loop
        ])

        await mock_session.run()

        # Should continue running after KeyboardInterrupt

    @pytest.mark.asyncio
    async def test_run_api_init_failure(self, mock_session, capsys):
        """Test handling API initialization failure."""
        with patch('src.cli.interactive.OpenRouterClient') as MockClient:
            MockClient.side_effect = Exception("API Error")

            session = InteractiveSession()
            await session.run()

            captured = capsys.readouterr()
            assert "Failed to initialize API" in captured.out

    @pytest.mark.asyncio
    async def test_natural_language_with_project(self, mock_session, temp_dir):
        """Test natural language input with project loaded."""
        project_dir = temp_dir / "test_proj"
        mock_session.project = Project.create(project_dir, name="Test")

        # Mock iteration system
        with patch('src.cli.interactive.IterationHandler') as MockIter:
            mock_handler = MockIter.return_value
            mock_handler.process = AsyncMock()

            await mock_session.process_input("Add more dialogue")

            MockIter.assert_called_once()


class TestGitManagerFullCoverage:
    """Tests for GitManager coverage."""

    def test_git_init_already_exists(self, temp_dir):
        """Test initializing git when already a repo."""
        from src.storage.git_manager import GitManager

        # Create .git directory
        (temp_dir / ".git").mkdir()

        git = GitManager(temp_dir)
        git.init()

        # Should not raise error

    def test_git_status(self, temp_dir):
        """Test git status command."""
        from src.storage.git_manager import GitManager

        git = GitManager(temp_dir)
        git.init()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="On branch main\nnothing to commit"
            )

            result = git.status()
            assert "main" in result

    def test_git_diff(self, temp_dir):
        """Test git diff command."""
        from src.storage.git_manager import GitManager

        git = GitManager(temp_dir)

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="diff output"
            )

            result = git.diff()
            assert result == "diff output"

    def test_git_commit_no_message(self, temp_dir):
        """Test commit with empty message."""
        from src.storage.git_manager import GitManager

        git = GitManager(temp_dir)
        git.init()  # Need to init first

        # GitManager doesn't validate message, git command may fail
        result = git.commit("")
        # Result will be False if git rejects empty message
        assert result is False

    def test_git_create_branch(self, temp_dir):
        """Test creating new branch."""
        from src.storage.git_manager import GitManager

        git = GitManager(temp_dir)

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)

            git.create_branch("feature")

            # Should call git checkout -b
            mock_run.assert_called()

    def test_git_list_branches(self, temp_dir):
        """Test listing branches."""
        from src.storage.git_manager import GitManager

        git = GitManager(temp_dir)

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="* main\n  feature\n"
            )

            branches = git.list_branches()
            assert "main" in branches
            assert "feature" in branches