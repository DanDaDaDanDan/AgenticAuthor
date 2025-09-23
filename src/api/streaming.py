"""Streaming response handling with Rich display."""
import json
import asyncio
from typing import AsyncIterator, Dict, Any, Optional, Callable
from rich.live import Live
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn


class StreamHandler:
    """Handle streaming responses with Rich display."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize stream handler."""
        self.console = console or Console()
        self.buffer = ""
        self.total_tokens = 0

    async def handle_sse_stream(
        self,
        response,
        on_token: Optional[Callable[[str, int], None]] = None,
        display: bool = True
    ) -> Dict[str, Any]:
        """
        Handle Server-Sent Events stream from OpenRouter.

        Args:
            response: aiohttp response object
            on_token: Optional callback for each token
            display: Whether to display output in console

        Returns:
            Complete response data including content and usage
        """
        content = ""
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        finish_reason = None
        model = None

        # Create live display if needed
        live = Live(console=self.console, refresh_per_second=10) if display else None

        try:
            if live:
                live.start()

            async for line in response.content:
                line = line.decode('utf-8').strip()

                if not line or not line.startswith('data: '):
                    continue

                if line == 'data: [DONE]':
                    break

                try:
                    # Parse SSE data
                    data_str = line[6:]  # Remove 'data: ' prefix
                    data = json.loads(data_str)

                    # Handle different event types
                    if 'choices' in data and data['choices']:
                        choice = data['choices'][0]

                        # Extract content delta
                        if 'delta' in choice and 'content' in choice['delta']:
                            token = choice['delta']['content']
                            content += token
                            self.total_tokens += 1

                            # Call token callback if provided
                            if on_token:
                                on_token(token, self.total_tokens)

                            # Update display
                            if live:
                                # Show content as markdown for better formatting
                                live.update(Markdown(content))

                        # Check for finish reason
                        if 'finish_reason' in choice and choice['finish_reason']:
                            finish_reason = choice['finish_reason']

                    # Extract model info
                    if 'model' in data:
                        model = data['model']

                    # Extract usage info
                    if 'usage' in data:
                        usage = data['usage']

                except json.JSONDecodeError:
                    # Skip malformed data
                    continue

        finally:
            if live:
                live.stop()

        return {
            'content': content,
            'usage': usage,
            'finish_reason': finish_reason,
            'model': model
        }

    async def stream_with_progress(
        self,
        response,
        task_description: str = "Generating..."
    ) -> Dict[str, Any]:
        """
        Stream response with a progress indicator.

        Args:
            response: aiohttp response object
            task_description: Description for the progress task

        Returns:
            Complete response data
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task(task_description, total=None)

            def update_progress(token: str, count: int):
                progress.update(
                    task,
                    description=f"{task_description} ({count} tokens)"
                )

            result = await self.handle_sse_stream(
                response,
                on_token=update_progress,
                display=False
            )

            progress.update(task, completed=True)

        # Display final result
        if result['content']:
            self.console.print(Markdown(result['content']))

        return result

    async def collect_stream(self, response) -> str:
        """
        Collect stream content without displaying.

        Args:
            response: aiohttp response object

        Returns:
            Complete content string
        """
        result = await self.handle_sse_stream(response, display=False)
        return result['content']


class TokenCounter:
    """Track token usage across requests."""

    def __init__(self):
        """Initialize token counter."""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0

    def update(self, usage: Dict[str, int], cost: float = 0.0):
        """Update token counts from usage data."""
        self.prompt_tokens += usage.get('prompt_tokens', 0)
        self.completion_tokens += usage.get('completion_tokens', 0)
        self.total_tokens += usage.get('total_tokens', 0)
        self.total_cost += cost
        self.request_count += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get usage summary."""
        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'total_cost': self.total_cost,
            'request_count': self.request_count,
            'avg_tokens_per_request': (
                self.total_tokens / self.request_count if self.request_count > 0 else 0
            )
        }

    def reset(self):
        """Reset all counters."""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0