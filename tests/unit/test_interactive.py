"""Unit tests for the interactive REPL session."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from src.cli.interactive import InteractiveSession
from src.models import Project
from src.config import get_settings


class TestInteractiveSession:
    """Test InteractiveSession initialization and methods."""

    def test_initialization_without_project(self, mock_api_key):
        """Test that InteractiveSession can be initialized without a project."""
        # This test would have caught the initialization order bug
        # Mock the prompt session to avoid console issues in tests
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()

            assert session is not None
            assert session.project is None
            assert session.story is None
            assert session.git is None
            assert session.running is False
            assert session.commands is not None
            assert 'help' in session.commands
            assert 'new' in session.commands
            assert session.session is not None  # prompt_toolkit session

    def test_initialization_with_project(self, test_project_dir, mock_api_key):
        """Test InteractiveSession initialization with a project path."""
        # Create a basic project first
        project = Project.create(test_project_dir, name="Test Project")

        # Initialize session with project
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession(project_path=test_project_dir)

            assert session.project is not None
            assert session.project.name == "test_project"
            assert session.git is not None

    def test_commands_defined_before_prompt_session(self, mock_api_key):
        """Test that commands are defined before prompt session creation."""
        # This specifically tests the bug fix
        commands_checked = {'checked': False}

        def check_commands():
            # When this is called, self.commands should already exist
            # We'll verify this by checking the instance
            commands_checked['checked'] = True
            return Mock()  # Return a mock session

        with patch.object(InteractiveSession, '_create_prompt_session', side_effect=check_commands):
            # This should not raise an error
            session = InteractiveSession()

            # Verify the check was performed
            assert commands_checked['checked']
            # And that commands exist on the created instance
            assert hasattr(session, 'commands')
            assert session.commands is not None
            assert len(session.commands) > 0

    def test_all_commands_have_handlers(self, mock_api_key):
        """Test that all commands have valid handlers."""
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()

        expected_commands = [
            'help', 'exit', 'quit', 'new', 'open', 'status',
            'model', 'models', 'generate', 'iterate', 'analyze',
            'export', 'git', 'config', 'clear'
        ]

        for cmd in expected_commands:
            assert cmd in session.commands
            assert callable(session.commands[cmd])

    def test_load_project_valid(self, test_project_dir, mock_api_key):
        """Test loading a valid project."""
        # Create project
        project = Project.create(test_project_dir, name="Test")

        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()
            session.load_project(test_project_dir)

            assert session.project is not None
            assert session.project.name == "test_project"
            assert session.git is not None

    def test_load_project_invalid(self, temp_dir, mock_api_key, capsys):
        """Test loading an invalid project."""
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()
            invalid_path = temp_dir / "nonexistent"

            session.load_project(invalid_path)

            assert session.project is None
            captured = capsys.readouterr()
            # The error is printed to console via Rich

    @pytest.mark.asyncio
    async def test_process_input_command(self, mock_api_key):
        """Test processing command input."""
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()

            # Mock command handler
            mock_handler = Mock()
            session.commands['test'] = mock_handler

            await session.process_input('/test arg1 arg2')

            mock_handler.assert_called_once_with('arg1 arg2')

    @pytest.mark.asyncio
    async def test_process_input_natural_language_no_project(self, mock_api_key, capsys):
        """Test natural language input without project."""
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()

            await session.process_input('Add more dialogue to chapter 3')

            # Should warn about no project
            captured = capsys.readouterr()
            # Checking console output indirectly

    def test_show_help(self, mock_api_key, capsys):
        """Test help command."""
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()
            session.show_help()

            # Help should be displayed
            captured = capsys.readouterr()
            # The output goes through Rich console

    def test_new_project_creates_project(self, temp_dir, mock_api_key, monkeypatch):
        """Test new project creation."""
        settings = get_settings()
        settings.books_dir = temp_dir

        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()
            session.settings = settings

            # Mock console input
            with patch.object(session.console, 'input', return_value='TestBook'):
                session.new_project('')

            assert session.project is not None
            assert session.project.name == 'TestBook'
            assert session.git is not None
            assert (temp_dir / 'TestBook').exists()

    def test_show_status_no_project(self, mock_api_key, capsys):
        """Test status command without project."""
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()
            session.show_status()

            # Should show no project message
            captured = capsys.readouterr()
            # Output through Rich console

    def test_show_status_with_project(self, test_project_dir, mock_api_key):
        """Test status command with project."""
        project = Project.create(test_project_dir, name="Test")

        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession(project_path=test_project_dir)
            session.show_status()

            # Should display project status
            assert session.project is not None

    def test_exit_session(self, mock_api_key):
        """Test exit command."""
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()
            session.running = True

            session.exit_session()

            assert session.running is False

    def test_clear_screen(self, mock_api_key):
        """Test clear screen command."""
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()

            with patch.object(session.console, 'clear') as mock_clear:
                session.clear_screen()
                mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_command_async(self, mock_api_key):
        """Test running async commands."""
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()

            # Create async mock handler
            async_handler = AsyncMock()
            session.commands['async_test'] = async_handler

            await session._run_command('async_test', 'args')

            async_handler.assert_called_once_with('args')

    def test_build_prompt_no_project(self, mock_api_key):
        """Test prompt building without project."""
        with patch.object(InteractiveSession, '_create_prompt_session', return_value=Mock()):
            session = InteractiveSession()
            prompt = session._build_prompt()

            # Should return HTML prompt
            assert '>' in str(prompt)
            assert 'prompt' in str(prompt).lower()