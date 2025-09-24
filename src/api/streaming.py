"""Streaming response handling with Rich display."""
import json
import asyncio
import time
from typing import AsyncIterator, Dict, Any, Optional, Callable
from rich.live import Live
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn


class StreamHandler:
    """Handle streaming responses with Rich display."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize stream handler."""
        self.console = console or Console()
        self.buffer = ""
        self.total_tokens = 0

    async def handle_json_stream_with_display(
        self,
        response,
        model_name: str = "Model",
        display_field: str = "premise",
        display_label: str = "Generating",
        on_token: Optional[Callable[[str, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Handle SSE stream for JSON responses, displaying specific fields as they stream.

        Args:
            response: The streaming response
            model_name: Name of the model for display
            display_field: The JSON field to display as it streams (e.g., "premise", "treatment")
            display_label: Label for what's being generated
            on_token: Optional callback for each token
        """
        full_content = ""
        display_content = ""
        field_found = False
        in_value = False
        escape_next = False
        token_count = 0
        start_time = time.time()
        last_processed_idx = 0  # Track what we've already processed
        usage = {}  # Track usage info from stream

        # Create live display - don't use transient to avoid clearing screen
        live = Live(console=self.console, refresh_per_second=10, transient=False)
        live.start()

        try:
            async for line in response.content:
                line = line.decode('utf-8').strip()

                if not line or not line.startswith('data: '):
                    continue

                if line == 'data: [DONE]':
                    break

                try:
                    data_str = line[6:]
                    data = json.loads(data_str)

                    if 'choices' in data and data['choices']:
                        choice = data['choices'][0]

                        if 'delta' in choice and 'content' in choice['delta']:
                            token = choice['delta']['content']
                            # Skip empty content deltas (common with Grok)
                            if token:
                                full_content += token
                                token_count += 1

                            # Simple approach: Look for field and extract value
                            if token and not field_found:
                                # Check if we now have the field pattern
                                field_pattern = f'"{display_field}":'
                                if field_pattern in full_content:
                                    field_found = True
                                    # Find where the value starts
                                    field_idx = full_content.find(field_pattern)
                                    after_field = full_content[field_idx + len(field_pattern):]
                                    # Skip whitespace and find opening quote
                                    after_field = after_field.lstrip()
                                    if after_field.startswith('"'):
                                        in_value = True
                                        last_processed_idx = len(full_content) - len(after_field) + 1

                            # If we're tracking a value, extract only new content
                            if in_value and token:
                                # Process only the new portion
                                for i in range(last_processed_idx, len(full_content)):
                                    char = full_content[i]
                                    if char == '"' and not escape_next:
                                        # End of value
                                        in_value = False
                                        break
                                    elif char == '\\' and not escape_next:
                                        escape_next = True
                                    elif escape_next:
                                        if char == 'n':
                                            display_content += '\n'
                                        elif char == 't':
                                            display_content += '\t'
                                        elif char == 'r':
                                            display_content += '\r'
                                        else:
                                            display_content += char
                                        escape_next = False
                                    else:
                                        display_content += char
                                last_processed_idx = len(full_content)

                            # Update live display
                            elapsed = time.time() - start_time
                            tokens_per_sec = token_count / elapsed if elapsed > 0 else 0

                            display_lines = []

                            # Status line
                            status_text = Text()
                            status_text.append(f"{display_label} with {model_name}", style="cyan")
                            status_text.append(f" • {elapsed:.1f}s", style="dim")
                            status_text.append(f" • {token_count} tokens", style="dim")
                            if tokens_per_sec > 0:
                                status_text.append(f" • {tokens_per_sec:.0f} t/s", style="dim")
                            display_lines.append(status_text)

                            # Show the content we're extracting
                            if display_content:
                                display_lines.append("")
                                display_lines.append(Text(display_content))

                            from rich.console import Group
                            live.update(Group(*display_lines))

                            if on_token:
                                on_token(token, token_count)

                    # Extract usage info if present
                    if 'usage' in data:
                        usage = data['usage']

                except json.JSONDecodeError:
                    continue

        finally:
            live.stop()
            if display_content:
                self.console.print()

        # Parse the complete JSON
        try:
            result = json.loads(full_content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown
            content = full_content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            result = json.loads(content.strip())

        # Add metadata
        result['token_count'] = token_count
        result['elapsed_time'] = time.time() - start_time
        # Include usage if we got it from the stream
        if usage:
            result['usage'] = usage
        return result

    async def handle_sse_stream_with_status(
        self,
        response,
        model_name: str = "Model",
        on_token: Optional[Callable[[str, int], None]] = None,
        display: bool = True
    ) -> Dict[str, Any]:
        """
        Handle SSE stream with Claude Code-style status display.

        Shows live updates of:
        - Elapsed time
        - Token count
        - Tokens per second
        - Content as it streams
        """
        content = ""
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        finish_reason = None
        model = None
        token_count = 0
        start_time = time.time()

        if display:
            # Create live display - don't use transient to avoid clearing screen
            live = Live(console=self.console, refresh_per_second=10, transient=False)
            live.start()
        else:
            live = None

        try:
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
                            # Skip empty content deltas (common with Grok)
                            if token:
                                content += token
                                token_count += 1

                            # Call token callback if provided
                            if on_token:
                                on_token(token, token_count)

                            # Update display with status
                            if live:
                                elapsed = time.time() - start_time
                                tokens_per_sec = token_count / elapsed if elapsed > 0 else 0

                                # Create inline display like Claude Code
                                display_lines = []

                                # Status line
                                status_text = Text()
                                status_text.append(f"Generating with {model_name}", style="cyan")
                                status_text.append(f" • {elapsed:.1f}s", style="dim")
                                status_text.append(f" • {token_count} tokens", style="dim")
                                if tokens_per_sec > 0:
                                    status_text.append(f" • {tokens_per_sec:.0f} t/s", style="dim")
                                display_lines.append(status_text)

                                # Content
                                display_lines.append("")  # Empty line
                                display_lines.append(Text(content))

                                # Update live display
                                from rich.console import Group
                                live.update(Group(*display_lines))

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
                # Just print a newline to separate from status
                if content:
                    self.console.print()

        return {
            'content': content,
            'usage': usage,
            'finish_reason': finish_reason,
            'model': model,
            'token_count': token_count,
            'elapsed_time': time.time() - start_time
        }

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
                            # Skip empty content deltas (common with Grok)
                            if token:
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