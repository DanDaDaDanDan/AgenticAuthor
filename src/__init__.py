"""AgenticAuthor - AI-powered iterative book generation."""

__version__ = "1.0.0"
__author__ = "AgenticAuthor"

from .cli import app
from .models import Project, Story
from .api import OpenRouterClient

__all__ = [
    '__version__',
    'app',
    'Project',
    'Story',
    'OpenRouterClient'
]