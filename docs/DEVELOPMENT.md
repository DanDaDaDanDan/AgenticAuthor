# Development Guide

## Setup

### Prerequisites
- Python 3.11 or higher
- Git
- OpenRouter API key

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd AgenticAuthor
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install in development mode:
```bash
pip install -e ".[dev]"
```

4. Set up environment:
```bash
cp .env.example .env
# Edit .env and add your OpenRouter API key
```

## Development Workflow

### Running the Application

```bash
# Start REPL (main interface)
agentic

# With specific project
agentic my-book

# Create new project
agentic new fantasy-novel

# List projects
agentic list
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage (HTML report in tests/htmlcov/)
pytest --cov=src --cov-report=term-missing --cov-report=html

# Run coverage with convenience script
python tests/run_coverage.py

# View coverage report
python -m webbrowser tests/htmlcov/index.html

# Run specific test file
pytest tests/unit/test_models.py

# Run specific test
pytest tests/unit/test_models.py::TestProject::test_create_project

# Run with verbose output
pytest -v

# Run async tests
pytest -k async
```

**Note:** Coverage reports are generated in `tests/htmlcov/` to keep the project root clean.

### Code Quality

```bash
# Format code with black
black src/ tests/

# Lint with ruff
ruff src/ tests/

# Type checking with mypy
mypy src/
```

## Code Style

### Python Style
- Follow PEP 8
- Use type hints for all functions
- Docstrings for all public methods
- Line length: 100 characters

### Imports
```python
# Standard library
import os
from pathlib import Path

# Third party
import pytest
from pydantic import BaseModel

# Local
from src.models import Project
from src.api import OpenRouterClient
```

### Async/Await
```python
async def process_content(self, text: str) -> str:
    """Process content with API.

    Args:
        text: Input text to process

    Returns:
        Processed text
    """
    async with self.client as session:
        result = await session.completion(text)
        return result
```

### Error Handling
```python
try:
    result = await api_call()
except aiohttp.ClientError as e:
    console.print(f"[red]API Error: {e}[/red]")
    raise
except ValueError as e:
    console.print(f"[yellow]Invalid input: {e}[/yellow]")
    return None
```

## Project Structure

### Adding New Features

1. **New Command**: Add to `src/cli/interactive.py`
```python
# In __init__, add to self.commands
self.commands = {
    # ...
    'mycommand': self.my_command,
}

# Add command handler
def my_command(self, args: str = ""):
    """Handle my command."""
    # Implementation
```

2. **New Generator**: Create in `src/generation/`
```python
# src/generation/my_generator.py
from src.api import OpenRouterClient

class MyGenerator:
    async def generate(self, context: str) -> str:
        # Implementation
```

3. **New Model**: Add to `src/models/`
```python
# src/models/my_model.py
from pydantic import BaseModel

class MyModel(BaseModel):
    field: str
    # Implementation
```

## Testing Guidelines

### Test Structure
```python
class TestFeature:
    """Test feature functionality."""

    def test_basic_case(self):
        """Test the basic use case."""
        # Arrange
        data = create_test_data()

        # Act
        result = process(data)

        # Assert
        assert result.success

    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test async operations."""
        result = await async_function()
        assert result is not None
```

### Fixtures
```python
@pytest.fixture
def test_project(tmp_path):
    """Create a test project."""
    project = Project.create(
        tmp_path / "test",
        name="Test"
    )
    return project
```

### Mocking
```python
from unittest.mock import Mock, patch

def test_with_mock():
    with patch('src.api.OpenRouterClient') as mock_client:
        mock_client.completion.return_value = "Test response"
        # Test code
```

## Common Tasks

### Adding a Slash Command

1. Update `src/cli/command_completer.py`:
```python
def create_command_descriptions():
    return {
        # ...
        'mycommand': {
            'description': 'Does something',
            'usage': '/mycommand [args]'
        }
    }
```

2. Add handler in `src/cli/interactive.py`
3. Update help text
4. Add tests

### Adding Generation Type

1. Create generator in `src/generation/`
2. Add temperature setting in `constants.py`
3. Add to `/generate` command handler
4. Create tests

### Updating Documentation

When making changes, update:
1. `docs/IMPLEMENTATION_STATUS.md` - Mark features complete
2. `docs/API_REFERENCE.md` - Add new APIs/commands
3. `docs/ARCHITECTURE.md` - Update if design changes
4. `README.md` - Update if user-facing changes

## Debugging

### Enable Verbose Logging
```python
# In .env
VERBOSE=true
```

### Debug REPL Issues
```python
# Test without prompt_toolkit
from src.cli.interactive import InteractiveSession
from unittest.mock import Mock

session = InteractiveSession()
session.session = Mock()  # Mock prompt session
# Debug session methods
```

### Debug API Calls
```python
# Enable request logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Release Process

1. Update version in `pyproject.toml`
2. Update `IMPLEMENTATION_STATUS.md` with changes
3. Run full test suite
4. Create git tag: `git tag v1.0.0`
5. Push tags: `git push --tags`

## Troubleshooting

### Common Issues

**Import Errors**
- Ensure package installed: `pip install -e .`
- Check Python version: `python --version`

**API Key Issues**
- Verify format: Must start with `sk-or-`
- Check .env file location
- Ensure .env not committed to git

**Terminal Issues**
- On Windows, use Windows Terminal or ConEmu
- For tests, mock prompt_toolkit components

**Git Issues**
- Ensure git installed: `git --version`
- Check git config: `git config --list`

## Resources

- [OpenRouter API Docs](https://openrouter.ai/docs)
- [prompt_toolkit Documentation](https://python-prompt-toolkit.readthedocs.io/)
- [Rich Documentation](https://rich.readthedocs.io/)
- [Pydantic Documentation](https://pydantic-docs.helpmanual.io/)