"""Semantic diff generation for human-readable change summaries."""

from typing import Dict, Any, List


class SemanticDiffGenerator:
    """Generates human-readable summaries of content changes."""

    def __init__(self, client, model: str):
        """
        Initialize semantic diff generator.

        Args:
            client: OpenRouter API client
            model: Model to use for diff generation
        """
        self.client = client
        self.model = model

    async def generate_diff(
        self,
        feedback: str,
        iteration_history: List[Dict[str, str]],
        old_content: str,
        new_content: str,
        judge_reasoning: str,
        target: str
    ) -> str:
        """
        Generate semantic diff summary.

        Args:
            feedback: User feedback for this iteration
            iteration_history: Previous iterations (feedback + summaries)
            old_content: Content before iteration
            new_content: Content after iteration
            judge_reasoning: Judge's approval reasoning
            target: Iteration target (premise, treatment, chapters, prose)

        Returns:
            Markdown-formatted semantic diff
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

        # Render semantic diff prompt
        prompts = prompt_loader.render(
            "analysis/semantic_diff",
            feedback=feedback,
            iteration_history=history_text,
            old_content=old_content,
            new_content=new_content,
            judge_reasoning=judge_reasoning,
            target=target
        )

        # Get temperature from config
        temperature = prompt_loader.get_temperature("analysis/semantic_diff", default=0.3)

        # Generate semantic diff
        result = await self.client.streaming_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ],
            temperature=temperature,
            stream=False,
            display=False
        )

        if not result:
            raise Exception("No response from semantic diff generator")

        diff_text = result.get('content', result) if isinstance(result, dict) else result

        return diff_text.strip()
