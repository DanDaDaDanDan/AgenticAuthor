"""Generation system for AgenticAuthor."""

from .premise import PremiseGenerator
from .treatment import TreatmentGenerator
from .chapters import ChapterGenerator
from .prose import ProseGenerator
from .short_story import ShortStoryGenerator
from .concept_mashup import ConceptMashupGenerator
from .copy_editor import CopyEditor
from .iteration import IterationCoordinator, IntentAnalyzer, ScaleDetector, DiffGenerator
from .analysis import AnalysisCoordinator

__all__ = [
    'PremiseGenerator',
    'TreatmentGenerator',
    'ChapterGenerator',
    'ProseGenerator',
    'ShortStoryGenerator',
    'ConceptMashupGenerator',
    'CopyEditor',
    'IterationCoordinator',
    'IntentAnalyzer',
    'ScaleDetector',
    'DiffGenerator',
    'AnalysisCoordinator',
]