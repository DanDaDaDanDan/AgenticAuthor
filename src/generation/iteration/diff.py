"""Unified diff generation and application."""

import re
import difflib
from typing import Dict, Any, Optional
from pathlib import Path
from jinja2 import Template

from ...api import OpenRouterClient


DIFF_GENERATION_TEMPLATE = """You are generating a unified diff to modify book content.

Original Content:
```
{{ original_content }}
```

Requested Change:
- Description: {{ intent_description }}
- Action: {{ action }}
- Scope: {{ scope }}

{% if context %}
Additional Context:
{{ context }}
{% endif %}

Generate a unified diff that makes the requested change.

CRITICAL REQUIREMENTS:
1. Use standard unified diff format
2. Include adequate context (3-5 lines before/after changes)
3. Make minimal, precise changes
4. Preserve formatting and style
5. Maintain narrative consistency
6. Start with "--- a/{{ file_path }}" and "+++ b/{{ file_path }}"

Example format:
--- a/{{ file_path }}
+++ b/{{ file_path }}
@@ -45,7 +45,12 @@
 [context line]
 [context line]
-[old line to remove]
+[new line to add]
+[another new line]
 [context line]
 [context line]

Output ONLY the diff, nothing else. No explanations, no markdown code blocks, just the raw diff.
"""


class PatchError(Exception):
    """Error applying patch."""
    pass


class DiffGenerator:
    """Generate and apply unified diffs for content changes."""

    def __init__(self, client: OpenRouterClient, model: Optional[str] = None):
        """
        Initialize diff generator.

        Args:
            client: OpenRouter API client
            model: Model to use for diff generation (needs good code understanding)
        """
        self.client = client
        # Use a capable model for diff generation (Claude Sonnet or GPT-4)
        self.model = model or "anthropic/claude-3.5-sonnet:beta"

    async def generate_diff(
        self,
        original: str,
        intent: Dict[str, Any],
        file_path: str = "content.md",
        context: Optional[str] = None
    ) -> str:
        """
        Generate unified diff for the requested change.

        Args:
            original: Original content
            intent: Parsed intent structure
            file_path: Path for diff headers (relative)
            context: Additional context to include in prompt

        Returns:
            Unified diff as string

        Raises:
            ValueError: If diff generation fails
        """
        if not original:
            raise ValueError("Original content cannot be empty")

        # Truncate very long content for prompt (keep first/last portions)
        original_for_prompt = self._truncate_content(original, max_words=3000)

        # Render prompt
        template = Template(DIFF_GENERATION_TEMPLATE)
        prompt = template.render(
            original_content=original_for_prompt,
            intent_description=intent.get('description', ''),
            action=intent.get('action', ''),
            scope=intent.get('scope', ''),
            file_path=file_path,
            context=context or ''
        )

        messages = [
            {"role": "system", "content": "You are an expert at generating precise unified diffs. Always output valid diff format only, no other text."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = await self.client.streaming_completion(
                model=self.model,
                messages=messages,
                temperature=0.2,  # Low temperature for precise output
                stream=True,
                display=True,
                display_label="Generating changes",
                max_tokens=2000
            )

            diff = response.get('content', '').strip()

            # Clean up diff (remove markdown code blocks if present)
            diff = self._clean_diff(diff)

            # Validate diff format
            if not self.validate_diff(diff):
                raise ValueError("Generated diff is not valid unified diff format")

            return diff

        except Exception as e:
            raise ValueError(f"Failed to generate diff: {str(e)}")

    def apply_diff(self, original: str, diff: str, file_path: Optional[Path] = None) -> str:
        """
        Apply unified diff to original content.

        Args:
            original: Original content
            diff: Unified diff to apply
            file_path: Optional file path to write patch to (for debugging)

        Returns:
            Modified content

        Raises:
            PatchError: If patch cannot be applied
        """
        if not self.validate_diff(diff):
            raise PatchError("Invalid diff format")

        try:
            # Parse diff and apply using difflib
            result = self._apply_patch_python(original, diff)
            return result

        except Exception as e:
            raise PatchError(f"Failed to apply patch: {str(e)}")

    def _apply_patch_python(self, original: str, diff: str) -> str:
        """Apply patch using pure Python (difflib-based)."""
        # Split original into lines
        original_lines = original.splitlines(keepends=True)

        # Parse diff hunks
        hunks = self._parse_diff_hunks(diff)

        if not hunks:
            raise PatchError("No valid hunks found in diff")

        # Apply hunks in reverse order (to preserve line numbers)
        result_lines = original_lines.copy()

        for hunk in reversed(hunks):
            result_lines = self._apply_hunk(result_lines, hunk)

        return ''.join(result_lines)

    def _parse_diff_hunks(self, diff: str) -> list:
        """Parse diff into hunks."""
        hunks = []
        current_hunk = None

        for line in diff.splitlines():
            # Check for hunk header
            if line.startswith('@@'):
                if current_hunk:
                    hunks.append(current_hunk)

                # Parse hunk header: @@ -start,count +start,count @@
                match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2)) if match.group(2) else 1
                    new_start = int(match.group(3))
                    new_count = int(match.group(4)) if match.group(4) else 1

                    current_hunk = {
                        'old_start': old_start,
                        'old_count': old_count,
                        'new_start': new_start,
                        'new_count': new_count,
                        'lines': []
                    }
            elif current_hunk is not None:
                # Skip diff headers
                if line.startswith('---') or line.startswith('+++'):
                    continue

                # Add line to current hunk
                current_hunk['lines'].append(line)

        if current_hunk:
            hunks.append(current_hunk)

        return hunks

    def _apply_hunk(self, lines: list, hunk: dict) -> list:
        """Apply a single hunk to lines."""
        # Convert to 0-indexed
        start_idx = hunk['old_start'] - 1

        # Extract old and new content from hunk
        old_content = []
        new_content = []

        for line in hunk['lines']:
            if line.startswith('-'):
                old_content.append(line[1:])
            elif line.startswith('+'):
                new_content.append(line[1:])
            elif line.startswith(' '):
                old_content.append(line[1:])
                new_content.append(line[1:])

        # Find the location to apply the hunk
        # This is a simplified approach - real patch is more sophisticated
        end_idx = start_idx + len(old_content)

        # Replace old content with new content
        result = lines[:start_idx] + new_content + lines[end_idx:]

        return result

    def validate_diff(self, diff: str) -> bool:
        """
        Validate diff format.

        Args:
            diff: Diff string to validate

        Returns:
            True if valid, False otherwise
        """
        if not diff or not diff.strip():
            return False

        lines = diff.splitlines()

        # Must have file headers
        has_old_header = any(line.startswith('---') for line in lines)
        has_new_header = any(line.startswith('+++') for line in lines)

        if not (has_old_header and has_new_header):
            return False

        # Must have at least one hunk header
        has_hunk = any(line.startswith('@@') for line in lines)

        return has_hunk

    def _clean_diff(self, diff: str) -> str:
        """Clean diff output from LLM."""
        # Remove markdown code blocks
        if '```diff' in diff:
            diff = diff.split('```diff')[1].split('```')[0].strip()
        elif '```' in diff:
            # Try to extract diff from generic code block
            parts = diff.split('```')
            for part in parts:
                if part.strip().startswith('---'):
                    diff = part.strip()
                    break

        # Remove any leading/trailing text that's not part of diff
        lines = diff.splitlines()
        start_idx = None
        end_idx = None

        for i, line in enumerate(lines):
            if line.startswith('---'):
                start_idx = i
                break

        if start_idx is not None:
            for i in range(len(lines) - 1, start_idx, -1):
                if lines[i].startswith(('+', '-', ' ', '@@')):
                    end_idx = i + 1
                    break

            if end_idx:
                diff = '\n'.join(lines[start_idx:end_idx])

        return diff

    def _truncate_content(self, content: str, max_words: int = 3000) -> str:
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

        # Keep first 60% and last 40%
        keep_start = int(max_words * 0.6)
        keep_end = max_words - keep_start

        truncated = (
            ' '.join(words[:keep_start]) +
            '\n\n[... content truncated ...]\n\n' +
            ' '.join(words[-keep_end:])
        )

        return truncated

    def create_preview(self, original: str, diff: str) -> str:
        """
        Create a preview of what the diff will do.

        Args:
            original: Original content
            diff: Diff to preview

        Returns:
            Side-by-side preview text
        """
        try:
            modified = self.apply_diff(original, diff)

            # Create side-by-side diff for review
            original_lines = original.splitlines()
            modified_lines = modified.splitlines()

            differ = difflib.unified_diff(
                original_lines,
                modified_lines,
                lineterm='',
                n=3
            )

            return '\n'.join(differ)

        except Exception as e:
            return f"Preview failed: {str(e)}"
