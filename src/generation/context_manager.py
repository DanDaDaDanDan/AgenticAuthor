"""Context optimization for large book generation."""

from typing import Optional, Dict, Any, List
from pathlib import Path

from ..models import Project
from ..utils.tokens import estimate_tokens


class ContextManager:
    """
    Smart context management for prose generation.

    Behavior:
    - Below 50KB: Full prose context (current behavior, quality-first)
    - Above 50KB: Full prose for last 3 chapters + LLM-generated summaries for earlier chapters

    Summaries are cached in chapter-beats/summaries/chapter-NN-summary.md
    """

    # Threshold in bytes before switching to optimized mode
    CONTEXT_THRESHOLD_BYTES = 50 * 1024  # 50KB

    # Number of recent chapters to keep in full
    RECENT_CHAPTERS_FULL = 3

    def __init__(self, client, project: Project, model: str):
        """
        Initialize context manager.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for summary generation
        """
        self.client = client
        self.project = project
        self.model = model
        self.summaries_dir = project.chapter_beats_dir / "summaries"

    def get_context_size(self) -> int:
        """Calculate total size of all prose chapters in bytes."""
        total_size = 0
        for ch_path in self.project.list_chapters():
            try:
                total_size += ch_path.stat().st_size
            except:
                pass
        return total_size

    def needs_optimization(self) -> bool:
        """Check if context optimization is needed."""
        return self.get_context_size() > self.CONTEXT_THRESHOLD_BYTES

    async def get_optimized_context(self, current_chapter: int) -> Dict[str, Any]:
        """
        Get optimized context for prose generation.

        Args:
            current_chapter: Chapter number being generated

        Returns:
            Dict with:
                - prior_prose: String of prior chapter content (full or summarized)
                - mode: 'full' or 'optimized'
                - tokens_saved: Estimated tokens saved by optimization
        """
        prose_chapters = self.project.list_chapters()
        prior_chapters = [p for p in prose_chapters if self._get_chapter_num(p) < current_chapter]

        if not prior_chapters:
            return {
                'prior_prose': '',
                'mode': 'full',
                'tokens_saved': 0,
            }

        # Check if optimization is needed
        total_size = sum(p.stat().st_size for p in prior_chapters)

        if total_size <= self.CONTEXT_THRESHOLD_BYTES:
            # Full mode - include all prior prose
            prior_prose = self._build_full_context(prior_chapters)
            return {
                'prior_prose': prior_prose,
                'mode': 'full',
                'tokens_saved': 0,
            }

        # Optimized mode
        # Recent chapters (last 3): full prose
        # Earlier chapters: summaries
        prior_chapters_sorted = sorted(prior_chapters, key=self._get_chapter_num)

        recent_threshold = current_chapter - self.RECENT_CHAPTERS_FULL
        earlier_chapters = [p for p in prior_chapters_sorted if self._get_chapter_num(p) < recent_threshold]
        recent_chapters = [p for p in prior_chapters_sorted if self._get_chapter_num(p) >= recent_threshold]

        # Build context
        context_parts = []
        original_tokens = 0
        optimized_tokens = 0

        # Add summaries for earlier chapters
        if earlier_chapters:
            context_parts.append("## Earlier Chapters (Summaries)\n")
            for ch_path in earlier_chapters:
                ch_num = self._get_chapter_num(ch_path)
                full_prose = ch_path.read_text(encoding='utf-8')
                original_tokens += estimate_tokens(full_prose)

                # Get or generate summary
                summary = await self._get_or_generate_summary(ch_num, full_prose)
                optimized_tokens += estimate_tokens(summary)

                context_parts.append(f"\n### Chapter {ch_num} Summary\n{summary}\n")

        # Add full prose for recent chapters
        if recent_chapters:
            context_parts.append("\n## Recent Chapters (Full Prose)\n")
            for ch_path in recent_chapters:
                ch_num = self._get_chapter_num(ch_path)
                full_prose = ch_path.read_text(encoding='utf-8')
                original_tokens += estimate_tokens(full_prose)
                optimized_tokens += estimate_tokens(full_prose)

                context_parts.append(f"\n{full_prose}\n")

        prior_prose = ''.join(context_parts)

        return {
            'prior_prose': prior_prose,
            'mode': 'optimized',
            'tokens_saved': max(0, original_tokens - optimized_tokens),
        }

    def _get_chapter_num(self, path: Path) -> int:
        """Extract chapter number from path."""
        try:
            # chapter-01.md -> 1
            return int(path.stem.split('-')[1])
        except:
            return 0

    def _build_full_context(self, chapters: List[Path]) -> str:
        """Build full prose context from chapter files."""
        parts = []
        for ch_path in sorted(chapters, key=self._get_chapter_num):
            try:
                prose = ch_path.read_text(encoding='utf-8')
                parts.append(prose)
            except:
                pass
        return '\n\n---\n\n'.join(parts)

    async def _get_or_generate_summary(self, chapter_num: int, prose: str) -> str:
        """
        Get cached summary or generate new one.

        Args:
            chapter_num: Chapter number
            prose: Full chapter prose

        Returns:
            Summary text
        """
        # Check cache
        summary_file = self.summaries_dir / f"chapter-{chapter_num:02d}-summary.md"

        if summary_file.exists():
            return summary_file.read_text(encoding='utf-8')

        # Generate new summary
        summary = await self._generate_summary(chapter_num, prose)

        # Cache it
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        summary_file.write_text(summary, encoding='utf-8')

        return summary

    async def _generate_summary(self, chapter_num: int, prose: str) -> str:
        """
        Generate a summary of a chapter using LLM.

        Args:
            chapter_num: Chapter number
            prose: Full chapter prose

        Returns:
            Summary text
        """
        from ..prompts import get_prompt_loader
        prompt_loader = get_prompt_loader()

        # Build summary prompt
        system_prompt = """You are a skilled story summarizer. Your task is to create concise summaries of book chapters that capture:
1. Key plot events and their outcomes
2. Character developments and revelations
3. Important dialogue or decisions
4. Setting changes or world-building elements
5. Emotional beats and tension points

The summary should be detailed enough to maintain continuity for future chapters, but concise enough to save context space. Aim for 200-400 words."""

        user_prompt = f"""Summarize this chapter for use as context in generating future chapters:

# Chapter {chapter_num}

{prose}

Provide a detailed summary that captures all essential plot points, character developments, and story elements needed for maintaining continuity."""

        try:
            result = await self.client.streaming_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                stream=False,
                display=False,
            )

            if result:
                summary = result.get('content', result) if isinstance(result, dict) else result
                return summary.strip()

        except Exception as e:
            # Fallback: extract first and last paragraphs
            paragraphs = [p.strip() for p in prose.split('\n\n') if p.strip()]
            if len(paragraphs) > 2:
                return f"Opening: {paragraphs[0][:500]}...\n\nClosing: {paragraphs[-1][:500]}..."
            return prose[:1000] + "..."

        return prose[:1000] + "..."

    def invalidate_summary(self, chapter_num: int) -> None:
        """
        Invalidate cached summary when chapter content changes.

        Args:
            chapter_num: Chapter number whose summary should be invalidated
        """
        summary_file = self.summaries_dir / f"chapter-{chapter_num:02d}-summary.md"
        if summary_file.exists():
            summary_file.unlink()

    def invalidate_all_summaries(self) -> None:
        """Invalidate all cached summaries."""
        if self.summaries_dir.exists():
            for summary_file in self.summaries_dir.glob("chapter-*-summary.md"):
                summary_file.unlink()
