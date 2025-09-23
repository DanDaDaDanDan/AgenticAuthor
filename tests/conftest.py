"""Pytest configuration and fixtures."""
import os
import shutil
import tempfile
from pathlib import Path
import pytest
from typing import Generator
from dotenv import load_dotenv

# Load .env file if it exists
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Only set dummy key if no real key exists (for unit tests)
if 'OPENROUTER_API_KEY' not in os.environ:
    os.environ['OPENROUTER_API_KEY'] = 'sk-or-test-key-123456789'


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_project_dir(temp_dir: Path) -> Path:
    """Create a test project directory."""
    project_dir = temp_dir / "test_project"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def mock_api_key(monkeypatch):
    """Set a mock API key for testing."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key-123456789")
    return "sk-or-test-key-123456789"