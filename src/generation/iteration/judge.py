"""Judge validation for iteration quality."""

import json
from typing import Dict, Any, Optional, List
from pathlib import Path


class IterationJudge:
    """Validates that generated content matches user feedback."""

    def __init__(self, client, model: str):
        """
        Initialize iteration judge.

        Args:
            client: OpenRouter API client
            model: Model to use for judging
        """
        self.client = client
        self.model = model

    async def validate(
        self,
        feedback: str,
        iteration_history: List[Dict[str, str]],
        old_content: str,
        new_content: str,
        context: str,
        target: str
    ) -> Dict[str, Any]:
        """
        Validate that new content matches feedback and context.

        Args:
            feedback: User feedback for this iteration
            iteration_history: Previous iterations (feedback + summaries)
            old_content: Content before iteration
            new_content: Content after iteration
            context: Upstream context (premise, treatment, etc.)
            target: Iteration target (premise, treatment, chapters, prose)

        Returns:
            Dict with:
                - verdict: "approved" or "needs_revision"
                - reasoning: Detailed explanation
                - specific_issues: List of issues (if needs_revision)
                - suggestions: List of suggestions (if needs_revision)
        """
        from ...prompts import get_prompt_loader
        prompt_loader = get_prompt_loader()

        # Build iteration history context
        history_text = ""
        if iteration_history:
            history_text = "\n\nPREVIOUS ITERATIONS:\n"
            for i, it in enumerate(iteration_history, 1):
                history_text += f"\n{i}. Feedback: {it['feedback']}\n"
                history_text += f"   Result: {it['semantic_summary']}\n"

        # Render judge prompt
        prompts = prompt_loader.render(
            "validation/iteration_fidelity",
            feedback=feedback,
            iteration_history=history_text,
            old_content=old_content,
            new_content=new_content,
            context=context,
            target=target
        )

        # Get temperature from config
        temperature = prompt_loader.get_temperature("validation/iteration_fidelity", default=0.1)

        # Call LLM with structured JSON output
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=temperature,
            stream=False,
            display=False,
            response_format={"type": "json_object"}
        )

        if not result:
            raise Exception("No response from judge")

        response_text = result.get('content', result) if isinstance(result, dict) else result

        # Parse JSON response
        try:
            # Strip markdown fences if present
            response_text = response_text.strip()
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1] if len(lines) > 2 else lines)

            # Parse JSON (allow non-strict for control characters)
            try:
                verdict_data = json.loads(response_text)
            except json.JSONDecodeError as strict_error:
                if 'control character' in str(strict_error).lower():
                    verdict_data = json.loads(response_text, strict=False)
                else:
                    raise

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse judge verdict JSON: {e}\n\nResponse: {response_text}")

        # Validate response structure
        if 'verdict' not in verdict_data:
            raise Exception(f"Judge response missing 'verdict' field: {verdict_data}")

        return verdict_data
