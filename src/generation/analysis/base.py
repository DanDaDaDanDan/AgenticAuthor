"""Base classes and utilities for story analysis."""

import json
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field
from jinja2 import Template

from ...api import OpenRouterClient


class Severity(str, Enum):
    """Issue severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class Issue:
    """Represents an analysis issue."""
    category: str  # e.g., "PLOT HOLE", "CHARACTER INCONSISTENCY"
    severity: Severity
    location: str  # e.g., "Chapter 3, Act II opening"
    description: str  # What's wrong
    impact: str  # How this affects the story
    suggestion: str  # How to fix it
    confidence: int = 100  # Confidence percentage (0-100)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'category': self.category,
            'severity': self.severity.value,
            'location': self.location,
            'description': self.description,
            'impact': self.impact,
            'suggestion': self.suggestion,
            'confidence': self.confidence
        }


@dataclass
class Strength:
    """Represents a story strength."""
    category: str  # What aspect is strong
    description: str  # Specific positive element
    location: Optional[str] = None  # Where this appears

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'category': self.category,
            'description': self.description,
            'location': self.location
        }


@dataclass
class Recommendation:
    """Represents a recommendation for reaching A+ grade."""
    description: str  # Specific actionable step
    confidence: int  # Confidence percentage (0-100)
    rationale: str  # Why this would help

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'description': self.description,
            'confidence': self.confidence,
            'rationale': self.rationale
        }


@dataclass
class PathToAPlus:
    """Represents path to A+ grade analysis."""
    current_assessment: str  # Why current grade was given
    recommendations: List[Recommendation] = field(default_factory=list)
    unable_to_determine: bool = False  # True if no clear path
    reasoning: Optional[str] = None  # Explanation if unable to determine

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'current_assessment': self.current_assessment,
            'recommendations': [r.to_dict() for r in self.recommendations],
            'unable_to_determine': self.unable_to_determine,
            'reasoning': self.reasoning
        }


@dataclass
class AnalysisResult:
    """Result from a single analyzer."""
    dimension: str  # e.g., "Plot & Structure"
    score: float  # 0-10
    summary: str  # Brief overview
    issues: List[Issue] = field(default_factory=list)
    strengths: List[Strength] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)  # Additional observations
    path_to_a_plus: Optional[PathToAPlus] = None  # Path to A+ grade

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'dimension': self.dimension,
            'score': self.score,
            'summary': self.summary,
            'issues': [i.to_dict() for i in self.issues],
            'strengths': [s.to_dict() for s in self.strengths],
            'notes': self.notes
        }
        if self.path_to_a_plus:
            result['path_to_a_plus'] = self.path_to_a_plus.to_dict()
        return result


class BaseAnalyzer:
    """Base class for all analyzers."""

    def __init__(self, client: OpenRouterClient, model: str):
        """
        Initialize analyzer.

        Args:
            client: OpenRouter API client
            model: Model to use for analysis (required)
        """
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")
        self.client = client
        self.model = model

    async def analyze(
        self,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        Analyze content along this analyzer's dimension.

        Args:
            content: The content to analyze
            content_type: Type of content (premise, treatment, chapter, prose)
            context: Additional context (premise, taxonomy, etc.)

        Returns:
            AnalysisResult with findings
        """
        raise NotImplementedError("Subclasses must implement analyze()")

    async def _call_llm(
        self,
        prompt: str,
        temperature: float = 0.3,
        reserve_tokens: int = 1000
    ) -> str:
        """
        Call LLM with prompt.

        Args:
            prompt: Prompt to send
            temperature: Sampling temperature
            reserve_tokens: Minimum tokens to reserve for response (dynamic calculation)

        Returns:
            LLM response content
        """
        messages = [
            {"role": "system", "content": "You are an expert story analyst and editor. Provide detailed, actionable feedback. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        response = await self.client.streaming_completion(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=False,
            display=False,
            reserve_tokens=reserve_tokens  # Dynamic calculation based on model capacity
        )

        return response.get('content', '').strip()

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling common issues."""
        # Remove markdown code blocks if present
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        # Try to parse JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # Try to find JSON object in text
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                try:
                    return json.loads(content[start:end+1])
                except:
                    pass
            raise ValueError(f"Failed to parse JSON from response: {str(e)}\nContent: {content[:500]}")

    def _truncate_content(self, content: str, max_words: int = 5000) -> str:
        """
        Truncate long content for prompt, keeping beginning and end.

        Args:
            content: Content to truncate
            max_words: Maximum words to keep

        Returns:
            Truncated content
        """
        words = content.split()

        if len(words) <= max_words:
            return content

        # Keep first 70% and last 30%
        keep_start = int(max_words * 0.7)
        keep_end = max_words - keep_start

        truncated = (
            ' '.join(words[:keep_start]) +
            '\n\n[... content truncated ...]\n\n' +
            ' '.join(words[-keep_end:])
        )

        return truncated

    def _create_analysis_prompt(
        self,
        template_str: str,
        content: str,
        content_type: str,
        context: Optional[Dict[str, Any]] = None,
        max_content_words: int = 5000
    ) -> str:
        """
        Create analysis prompt from template.

        Args:
            template_str: Jinja2 template string
            content: Content to analyze
            content_type: Type of content
            context: Additional context
            max_content_words: Max words of content to include

        Returns:
            Rendered prompt
        """
        # Truncate content if needed
        content_for_prompt = self._truncate_content(content, max_content_words)

        # Build context dict
        ctx = context or {}
        ctx.update({
            'content': content_for_prompt,
            'content_type': content_type,
            'word_count': len(content.split())
        })

        # Render template
        template = Template(template_str)
        return template.render(**ctx)
