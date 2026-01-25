"""Application constants and defaults."""
from pathlib import Path

# API Configuration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "x-ai/grok-4-fast"

# Directory Structure
DEFAULT_BOOKS_DIR = Path("./books")
DEFAULT_TAXONOMIES_DIR = Path("./taxonomies")
DEFAULT_CACHE_DIR = Path("./.cache")

# Directory Names
PROJECT_FILE = "project.yaml"
PREMISE_DIR = "premise"
TREATMENT_DIR = "treatment"
CHAPTERS_DIR = "chapters"
ANALYSIS_DIR = "analysis"
EXPORTS_DIR = "exports"

# File Names
STRUCTURE_PLAN_FILE = "structure-plan.md"

# Git Configuration
DEFAULT_COMMIT_AUTHOR = "AgenticAuthor"
DEFAULT_COMMIT_EMAIL = "agentic@localhost"

# Generation Parameters
DEFAULT_TEMPERATURES = {
    'premise': 0.9,      # Higher for creativity
    'treatment': 0.7,    # Balanced
    'chapters': 0.6,     # More structured
    'prose': 0.8,        # Creative prose
    'polish': 0.3,       # Low for consistency
    'iteration': 0.5,    # Moderate for edits
    'analysis': 0.3,     # Low for accuracy
    'intent': 0.1        # Very low for intent checking
}

# Intent Checking
INTENT_CONFIDENCE_THRESHOLD = 0.8  # Execute if confidence >= this
INTENT_LOW_CONFIDENCE_THRESHOLD = 0.5  # Below this, definitely ask

# Analysis Types
ANALYSIS_TYPES = [
    'commercial',
    'plot',
    'characters',
    'elements',
    'world_building'
]

# Supported Export Formats
EXPORT_FORMATS = ['txt', 'md', 'html', 'epub', 'pdf']

# Progress Messages
PROGRESS_MESSAGES = {
    'premise': 'Generating story premise...',
    'treatment': 'Creating story treatment...',
    'chapters': 'Outlining chapters...',
    'prose': 'Writing prose for chapter {chapter}...',
    'iteration': 'Processing feedback...',
    'analysis': 'Analyzing {analysis_type}...',
    'export': 'Exporting to {format}...'
}