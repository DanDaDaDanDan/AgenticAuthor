"""Iteration coordinator to orchestrate the iteration process."""

from typing import Dict, Any, Optional
from pathlib import Path

from ...api import OpenRouterClient
from ...models import Project
from .intent import IntentAnalyzer
from .scale import ScaleDetector
from .diff import DiffGenerator, PatchError


class IterationCoordinator:
    """Coordinate the iteration process."""

    def __init__(
        self,
        client: OpenRouterClient,
        project: Project,
        model: Optional[str] = None,
        default_target: Optional[str] = None,
        settings=None
    ):
        """
        Initialize iteration coordinator.

        Args:
            client: OpenRouter API client
            project: Current project
            model: Model to use for generation tasks (optional)
            default_target: Default target for iterations (premise/treatment/chapters/prose)
            settings: Settings object (for multi-model mode detection)
        """
        self.client = client
        self.project = project
        self.settings = settings
        self.model = model
        self.default_target = default_target

        # Validate model
        if not model:
            raise ValueError("No model selected. Use /model <model-name> to select a model.")

        # Initialize components (all use the same model)
        self.intent_analyzer = IntentAnalyzer(client, model, default_target=default_target)
        self.scale_detector = ScaleDetector(client, model)
        self.diff_generator = DiffGenerator(client, model)

    async def process_feedback(
        self,
        feedback: str,
        auto_commit: bool = True,
        show_preview: bool = False
    ) -> Dict[str, Any]:
        """
        Process user feedback and execute iteration.

        Args:
            feedback: User's natural language feedback
            auto_commit: Whether to automatically commit changes
            show_preview: Whether to show preview before applying

        Returns:
            Result dict with success status, changes, and commit info

        Raises:
            ValueError: If feedback is invalid or cannot be processed
        """
        result = {
            'success': False,
            'feedback': feedback,
            'intent': None,
            'scale': None,
            'changes': [],
            'commit': None,
            'error': None
        }

        try:
            # Step 1: Analyze intent
            intent = await self.intent_analyzer.analyze(feedback, self.project)
            result['intent'] = intent

            # Step 2: Check confidence
            if intent['confidence'] < 0.8:
                return self._request_clarification(intent, result)

            # Step 3: Handle non-iteration intents
            if intent['intent_type'] == 'analyze':
                result['error'] = "Analysis system not yet implemented. Use /analyze command."
                return result

            if intent['intent_type'] == 'clarify':
                return self._request_clarification(intent, result)

            # Step 4: Detect scale
            scale = await self._determine_scale(intent)
            result['scale'] = scale

            # Step 5: Execute based on scale
            if scale == "patch":
                changes = await self._execute_patch(intent, show_preview)
            else:
                changes = await self._execute_regenerate(intent)

            result['changes'] = changes
            result['success'] = True

            # Step 6: Check LOD consistency and offer sync
            if result['success']:
                result['lod_sync'] = await self._check_lod_consistency(intent)

            return result

        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
            return result

    async def _check_lod_consistency(self, intent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if LODs are consistent after iteration."""
        try:
            from ..lod_sync import LODSyncManager

            sync_manager = LODSyncManager(self.client, self.project, self.model)

            # Determine which LOD was modified
            target_type = intent.get('target_type')
            target_id = intent.get('target_id')

            if target_type in ['chapter', 'chapters']:
                # Include chapter number if specific chapter was modified
                if target_id and target_type == 'chapter':
                    modified_lod = f'chapters:{target_id}'
                else:
                    modified_lod = 'chapters'
            elif target_type == 'prose':
                # Include chapter number for prose
                if target_id:
                    modified_lod = f'prose:{target_id}'
                else:
                    modified_lod = 'prose'
            elif target_type == 'treatment':
                modified_lod = 'treatment'
            elif target_type == 'premise':
                modified_lod = 'premise'
            else:
                return None

            # Check consistency
            changes_desc = intent.get('description', '')
            consistency_report = await sync_manager.check_consistency(
                modified_lod=modified_lod,
                changes_description=changes_desc
            )

            # Only return if there are inconsistencies
            if not consistency_report.get('is_consistent', True):
                return consistency_report

            return None

        except Exception as e:
            # Don't fail the iteration if consistency check fails
            from ...utils.logging import get_logger
            logger = get_logger()
            if logger:
                logger.warning(f"LOD consistency check failed: {e}")
            return None

    async def _determine_scale(self, intent: Dict[str, Any]) -> str:
        """Determine if change should be patch or regenerate."""
        # First, try heuristic detection
        scale = self.scale_detector.detect_scale(intent)

        # If unclear and we have content, ask the model
        if scale == "ask_model":
            content, content_type = self._get_target_content(intent)

            if content:
                scale_data = await self.scale_detector.ask_model_for_scale(
                    intent, content, content_type
                )
                scale = scale_data['scale']
            else:
                # No content available, default to regenerate
                scale = "regenerate"

        return scale

    async def _execute_patch(
        self,
        intent: Dict[str, Any],
        show_preview: bool = False
    ) -> list:
        """Execute patch-based iteration."""
        changes = []

        # Get target content
        content, content_type = self._get_target_content(intent)

        if not content:
            raise ValueError(
                f"No content found for {intent['target_type']}. "
                f"Generate it first before iterating."
            )

        # Get file path
        file_path = self._get_target_file_path(intent)

        # Generate diff
        diff = await self.diff_generator.generate_diff(
            original=content,
            intent=intent,
            file_path=str(file_path.relative_to(self.project.path)),
            context=self._build_context(intent)
        )

        # Show preview if requested
        if show_preview:
            preview = self.diff_generator.create_preview(content, diff)
            # TODO: Show preview to user and ask for confirmation
            # For now, just include it in changes
            changes.append({
                'type': 'preview',
                'diff': preview
            })

        # Apply diff
        try:
            modified = self.diff_generator.apply_diff(content, diff)
        except PatchError as e:
            # Fallback to regeneration if patch fails
            raise ValueError(
                f"Patch failed: {str(e)}. Try rephrasing your request, "
                f"or the change may be too large for a patch."
            )

        # Write modified content
        file_path.write_text(modified, encoding='utf-8')

        change_info = {
            'type': 'patch',
            'file': str(file_path.relative_to(self.project.path)),
            'diff': diff,
            'original_length': len(content.split()),
            'modified_length': len(modified.split())
        }

        # For chapters.yaml, add chapter count info
        if intent['target_type'] == 'chapters':
            # Parse YAML to count chapters
            import yaml
            try:
                chapters_data = yaml.safe_load(modified)
                if isinstance(chapters_data, list):
                    change_info['chapter_count'] = len(chapters_data)
            except:
                pass  # Fall back to word count

        changes.append(change_info)

        return changes

    async def _execute_regenerate(self, intent: Dict[str, Any]) -> list:
        """Execute full regeneration."""
        changes = []

        target_type = intent['target_type']

        # Import generators as needed
        if target_type == 'premise':
            from ..premise import PremiseGenerator
            generator = PremiseGenerator(self.client, self.project, self.model)

            # Extract new requirements from intent
            concept = intent.get('original_feedback', '')

            result = await generator.generate(user_input=concept)

            # Save premise
            self.project.save_premise(result['premise'])

            changes.append({
                'type': 'regenerate',
                'target': 'premise',
                'file': 'premise.md',
                'word_count': len(result['premise'].split())
            })

        elif target_type == 'treatment':
            from ..treatment import TreatmentGenerator
            generator = TreatmentGenerator(self.client, self.project, self.model)

            # Use multi-model competition if enabled
            if self.settings and self.settings.multi_model_mode:
                result = await generator.generate_with_competition()
            else:
                result = await generator.generate()

            # Save treatment
            self.project.save_treatment(result)

            changes.append({
                'type': 'regenerate',
                'target': 'treatment',
                'file': 'treatment.md',
                'word_count': len(result.split())
            })

        elif target_type == 'chapters':
            # Multiple chapters - regenerate all chapter outlines with feedback
            from ..chapters import ChapterGenerator
            generator = ChapterGenerator(self.client, self.project, self.model)

            # Get current chapter count or use default
            current_chapters = self.project.list_chapters()
            chapter_count = len(current_chapters) if current_chapters else None

            # Get total words from treatment or use default
            treatment = self.project.get_treatment()
            total_words = len(treatment.split()) * 20 if treatment else 50000  # Rough estimate

            # Regenerate with feedback as guidance
            feedback_text = intent.get('description', '')

            # Use multi-model competition if enabled
            if self.settings and self.settings.multi_model_mode:
                result = await generator.generate_with_competition(
                    chapter_count=chapter_count,
                    total_words=total_words,
                    template=None,
                    feedback=feedback_text
                )
            else:
                result = await generator.generate(
                    chapter_count=chapter_count,
                    total_words=total_words,
                    feedback=feedback_text
                )

            changes.append({
                'type': 'regenerate',
                'target': 'chapters',
                'file': 'chapters.yaml',
                'count': len(result)
            })

        elif target_type in ['chapter', 'prose']:
            # Single chapter regeneration
            chapter_num = self._extract_chapter_number(intent)

            if not chapter_num:
                raise ValueError("Cannot determine which chapter to regenerate")

            from ..prose import ProseGenerator
            generator = ProseGenerator(self.client, self.project, self.model)

            # Use multi-model competition if enabled
            if self.settings and self.settings.multi_model_mode:
                result = await generator.generate_chapter_with_competition(chapter_num)
            else:
                result = await generator.generate_chapter_sequential(chapter_num)

            # Save chapter
            chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
            chapter_file.write_text(result, encoding='utf-8')

            changes.append({
                'type': 'regenerate',
                'target': f'chapter {chapter_num}',
                'file': str(chapter_file.relative_to(self.project.path)),
                'word_count': len(result.split())
            })

        else:
            raise ValueError(f"Regeneration not implemented for {target_type}")

        return changes

    def _get_target_content(self, intent: Dict[str, Any]) -> tuple[Optional[str], str]:
        """
        Get the content to be modified.

        Returns:
            Tuple of (content, content_type)
        """
        target_type = intent['target_type']

        if target_type == 'premise':
            premise = self.project.get_premise()
            return (premise, 'premise')

        elif target_type == 'treatment':
            treatment = self.project.get_treatment()
            return (treatment, 'treatment')

        elif target_type == 'chapters':
            # Multiple chapters - load chapters.yaml for patch/regen decision
            chapters_file = self.project.path / "chapters.yaml"
            if chapters_file.exists():
                content = chapters_file.read_text(encoding='utf-8')
                return (content, 'chapters')
            return (None, 'chapters')

        elif target_type == 'chapter':
            # Single chapter - if default_target is 'chapters', load chapters.yaml
            # Otherwise, load prose
            if self.default_target == 'chapters':
                # User is iterating chapters - load chapters.yaml unconditionally
                chapters_file = self.project.path / "chapters.yaml"
                if chapters_file.exists():
                    content = chapters_file.read_text(encoding='utf-8')
                    return (content, 'chapters')
                raise ValueError("No chapters.yaml found. Generate chapters first with /generate chapters")
            else:
                # User is iterating prose
                chapter_num = self._extract_chapter_number(intent)
                if not chapter_num:
                    raise ValueError("Cannot determine chapter number")

                chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
                if chapter_file.exists():
                    content = chapter_file.read_text(encoding='utf-8')
                    return (content, f'chapter {chapter_num}')
                raise ValueError(
                    f"No prose found for chapter {chapter_num}. "
                    f"Generate with /generate prose {chapter_num} or use /iterate chapters for outlines."
                )

        elif target_type == 'prose':
            # Explicitly prose - always load prose file
            chapter_num = self._extract_chapter_number(intent)
            if not chapter_num:
                raise ValueError("Cannot determine chapter number")

            chapter_file = self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"
            if chapter_file.exists():
                content = chapter_file.read_text(encoding='utf-8')
                return (content, f'chapter {chapter_num}')
            raise ValueError(
                f"No prose found for chapter {chapter_num}. "
                f"Generate with /generate prose {chapter_num}"
            )

        return (None, target_type)

    def _get_target_file_path(self, intent: Dict[str, Any]) -> Path:
        """Get file path for target content."""
        target_type = intent['target_type']

        if target_type == 'premise':
            return self.project.premise_file

        elif target_type == 'treatment':
            return self.project.treatment_file

        elif target_type == 'chapters':
            # Multiple chapters - return chapters.yaml
            return self.project.path / "chapters.yaml"

        elif target_type == 'chapter':
            # Single chapter - if default_target is 'chapters', return chapters.yaml
            if self.default_target == 'chapters':
                return self.project.path / "chapters.yaml"
            else:
                # Return prose file
                chapter_num = self._extract_chapter_number(intent)
                if chapter_num:
                    return self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"

        elif target_type == 'prose':
            # Explicitly prose - always return prose file
            chapter_num = self._extract_chapter_number(intent)
            if chapter_num:
                return self.project.chapters_dir / f"chapter-{chapter_num:02d}.md"

        raise ValueError(f"Cannot determine file path for {target_type}")

    def _extract_chapter_number(self, intent: Dict[str, Any]) -> Optional[int]:
        """Extract chapter number from intent."""
        target_id = intent.get('target_id')

        if target_id:
            # Try to parse as integer
            try:
                return int(target_id)
            except (ValueError, TypeError):
                # Try to extract number from string like "chapter 3" or "3-5"
                import re
                match = re.search(r'\d+', str(target_id))
                if match:
                    return int(match.group())

        # Try to extract from feedback
        feedback = intent.get('original_feedback', '')
        import re
        match = re.search(r'chapter\s+(\d+)', feedback, re.IGNORECASE)
        if match:
            return int(match.group(1))

        return None

    def _build_context(self, intent: Dict[str, Any]) -> str:
        """Build additional context for diff generation."""
        context_parts = []

        # Add premise if modifying chapter
        if intent['target_type'] in ['chapter', 'prose']:
            premise = self.project.get_premise()
            if premise:
                context_parts.append(f"Story Premise:\n{premise[:200]}...")

        # Add treatment summary if available
        if intent['target_type'] == 'prose':
            treatment = self.project.get_treatment()
            if treatment:
                context_parts.append(f"Treatment Summary:\n{treatment[:300]}...")

        return '\n\n'.join(context_parts)


    def _request_clarification(
        self,
        intent: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request clarification from user."""
        result['success'] = False
        result['needs_clarification'] = True

        # Generate clarification question based on intent
        reasoning = intent.get('reasoning', 'Intent is unclear')

        result['clarification_needed'] = {
            'reason': reasoning,
            'suggestions': self._generate_suggestions(intent)
        }

        return result

    def _generate_suggestions(self, intent: Dict[str, Any]) -> list:
        """Generate helpful suggestions for user."""
        suggestions = []

        target_type = intent.get('target_type')

        if target_type == 'chapter':
            if not intent.get('target_id'):
                suggestions.append("Please specify which chapter you want to modify (e.g., 'chapter 3')")

        if intent.get('scope') == 'unclear':
            suggestions.append("Please clarify how extensive the change should be")

        if intent.get('action') == 'unclear':
            suggestions.append("Please describe more specifically what you want to change")

        # Generic suggestion
        if not suggestions:
            suggestions.append("Please provide more details about what you want to change")

        return suggestions
