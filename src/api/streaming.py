"""Streaming response handling with Rich display."""
import json
import re
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

    def _extract_json_from_markdown(self, content: str) -> Optional[str]:
        """
        Extract JSON from markdown code blocks or other formatting.
        Only handles known formatting patterns, does NOT repair truncated content.

        Args:
            content: The content that might contain JSON in markdown

        Returns:
            Extracted JSON string or None if no known pattern found
        """
        # Pattern 1: ```json ... ```
        if content.startswith("```json"):
            content = content[7:]
            if "```" in content:
                content = content[:content.index("```")]
                return content.strip()

        # Pattern 2: ``` ... ```
        elif content.startswith("```"):
            content = content[3:]
            if "```" in content:
                content = content[:content.index("```")]
                return content.strip()

        # Pattern 3: Ends with ``` (complete markdown block)
        elif content.endswith("```") and "```" in content[:-3]:
            # Find the first ``` and extract content between
            start = content.index("```")
            # Check if it's ```json
            if content[start:].startswith("```json"):
                content = content[start+7:-3]
            else:
                content = content[start+3:-3]
            return content.strip()

        # No known formatting pattern found
        return None

    async def handle_json_stream_with_display(
        self,
        response,
        model_name: str = "Model",
        display_field: str = "premise",
        display_label: str = "Generating",
        on_token: Optional[Callable[[str, int], None]] = None,
        model_obj: Any = None  # Required: actual model object for capability checking
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

        # Use console.status for fixed bottom status bar (Claude Code style)
        status_context = self.console.status(
            f"{display_label}...",
            spinner="dots",
            spinner_style="cyan"
        )
        status_context.__enter__()

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
                                # Also check for field pattern with spaces
                                field_pattern_spaced = f'"{display_field}" :'
                                if field_pattern in full_content or field_pattern_spaced in full_content:
                                    field_found = True
                                    # Find where the value starts (try both patterns)
                                    field_idx = full_content.find(field_pattern)
                                    if field_idx == -1:
                                        field_idx = full_content.find(field_pattern_spaced)
                                        field_pattern = field_pattern_spaced
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

                            # Update status bar and stream content
                            if token:
                                elapsed = time.time() - start_time
                                tokens_per_sec = token_count / elapsed if elapsed > 0 else 0

                                # Update status bar (stays at bottom)
                                status_text = f"{display_label} with {model_name} • {elapsed:.1f}s • {token_count} tokens"
                                if tokens_per_sec > 0:
                                    status_text += f" • {tokens_per_sec:.0f} t/s"
                                status_context.update(status_text)

                                # Stream content to console (scrollable)
                                if display_content and last_processed_idx > 0:
                                    # Print only new content since last update
                                    new_content_start = len(display_content) - (len(full_content) - last_processed_idx)
                                    if new_content_start >= 0:
                                        new_text = display_content[new_content_start:]
                                        if new_text:
                                            self.console.print(new_text, end="", highlight=False)

                            if on_token:
                                on_token(token, token_count)

                    # Extract usage info if present
                    if 'usage' in data:
                        usage = data['usage']

                except json.JSONDecodeError:
                    continue

        finally:
            status_context.__exit__(None, None, None)
            # Add newline after streaming content
            if display_content:
                self.console.print()

        # Parse the complete JSON
        try:
            parsed_json = json.loads(full_content)
        except json.JSONDecodeError as e:
            # First try to extract JSON from known formatting patterns
            extracted = self._extract_json_from_markdown(full_content.strip())

            if extracted:
                # Try parsing the extracted JSON
                try:
                    parsed_json = json.loads(extracted)
                except json.JSONDecodeError as e2:
                    # Even extracted JSON failed - likely truncated
                    self._handle_truncated_json(extracted, e2, model_obj, model_name)
            else:
                # No known formatting pattern - check for truncation
                self._handle_truncated_json(full_content.strip(), e, model_obj, model_name)

    def _handle_truncated_json(self, content: str, error: json.JSONDecodeError, model_obj: Any, model_name: str = "Model"):
        """
        Handle truncated or malformed JSON by failing fast with clear error.

        Args:
            content: The problematic JSON content
            error: The JSON decode error

        Raises:
            json.JSONDecodeError with helpful context
        """
        # Clear indicators of truncation
        truncation_indicators = [
            "Unterminated string",
            "Expecting value",
            "Expecting ',' delimiter",
            "Expecting property name",
            "Expecting ':' delimiter"
        ]

        is_likely_truncated = any(indicator in str(error) for indicator in truncation_indicators)

        if is_likely_truncated:
            self.console.print(f"\n[red]❌  Response appears to be truncated[/red]")
            self.console.print(f"[yellow]Error: {error}[/yellow]")
            self.console.print(f"[dim]Response length: {len(content)} characters (~{len(content)//4} tokens)[/dim]")

            # Check if we hit model's actual output limit
            if not model_obj:
                raise ValueError("Model object required for truncation detection - cannot determine output limits")

            max_output = model_obj.get_max_output_tokens()
            if max_output:
                # Convert tokens to approximate character count (rough estimate: 1 token ≈ 4 chars)
                max_chars = max_output * 4
                estimated_tokens = len(content) // 4
                if abs(estimated_tokens - max_output) < 200:  # Within 200 tokens of limit
                    self.console.print(f"[yellow]⚠️   Model output limit reached[/yellow]")
                    self.console.print(f"[dim]Model: {model_obj.id}[/dim]")
                    self.console.print(f"[dim]Max output: {max_output} tokens • Received: ~{estimated_tokens} tokens ({len(content)} chars)[/dim]")

            # Save for debugging
            from pathlib import Path
            debug_dir = Path.home() / ".agentic" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / f"truncated_json_{int(time.time())}.json"

            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(content)

            self.console.print(f"[dim]Saved truncated response to: {debug_file}[/dim]")
            self.console.print(f"\n[yellow]Suggestions:[/yellow]")
            self.console.print(f"  • Use a model with larger output capacity")
            self.console.print(f"  • Reduce the number of chapters requested")
            self.console.print(f"  • Simplify the generation requirements")
            self.console.print(f"\n[dim]Note: Tokens ≠ characters. ~1 token = 4 characters for English text.[/dim]")

            # Fail fast with clear error
            raise json.JSONDecodeError(
                f"Response truncated at ~{len(content)} chars. {error.msg}",
                error.doc,
                error.pos
            )
        else:
            # Other JSON error - still fail but with different message
            self.console.print(f"\n[red]❌  Invalid JSON response[/red]")
            self.console.print(f"[yellow]Error: {error}[/yellow]")

            # Save for debugging
            from pathlib import Path
            debug_dir = Path.home() / ".agentic" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / f"invalid_json_{int(time.time())}.json"

            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(content)

            self.console.print(f"[dim]Saved invalid JSON to: {debug_file}[/dim]")
            raise error

        # Return result with metadata in a wrapper if parsed_json is not a dict
        if isinstance(parsed_json, dict):
            # If it's already a dict, we can add metadata directly
            parsed_json['token_count'] = token_count
            parsed_json['elapsed_time'] = time.time() - start_time
            # Include usage if we got it from the stream
            if usage:
                parsed_json['usage'] = usage
            return parsed_json
        else:
            # If it's an array or other type, wrap it with metadata
            return {
                'data': parsed_json,
                'token_count': token_count,
                'elapsed_time': time.time() - start_time,
                'usage': usage if usage else {}
            }

    async def handle_sse_stream_with_status(
        self,
        response,
        model_name: str = "Model",
        on_token: Optional[Callable[[str, int], None]] = None,
        display: bool = True,
        display_mode: str = "status"  # New parameter: "status", "live", or "simple"
    ) -> Dict[str, Any]:
        """
        Handle SSE stream with status display.

        Shows live updates of:
        - Elapsed time
        - Token count
        - Tokens per second
        - Content as it streams

        Args:
            response: The SSE response stream
            model_name: Name of the model for display
            on_token: Optional callback for each token
            display: Whether to display output
            display_mode: Display mode - "status" (console.status), "live" (Live display), or "simple" (plain)
        """
        content = ""
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        finish_reason = None
        model = None
        token_count = 0
        start_time = time.time()
        status_context = None
        live = None

        # Initialize display based on mode
        if display:
            if display_mode == "status":
                # Use console.status for fixed status bar that doesn't interfere with scrolling
                status_context = self.console.status(
                    f"Starting generation with {model_name}...",
                    spinner="dots",
                    spinner_style="cyan"
                )
                status_context.__enter__()
            elif display_mode == "live":
                # Keep original Live display for backwards compatibility
                live = Live(console=self.console, refresh_per_second=10, transient=False, vertical_overflow="visible")
                live.start()
            # For "simple" mode, we don't need any special display setup

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

                            # Update display based on mode
                            if display and token:  # Only update display when we have actual tokens
                                elapsed = time.time() - start_time
                                tokens_per_sec = token_count / elapsed if elapsed > 0 else 0

                                if display_mode == "status" and status_context:
                                    # Update status bar (stays at bottom, doesn't interfere with scrolling)
                                    status_text = f"Generating with {model_name} • {elapsed:.1f}s • {token_count} tokens"
                                    if tokens_per_sec > 0:
                                        status_text += f" • {tokens_per_sec:.0f} t/s"
                                    status_context.update(status_text)

                                    # Stream content to console (normal scrollable output)
                                    self.console.print(token, end="", highlight=False)

                                elif display_mode == "live" and live:
                                    # Original Live display behavior
                                    display_lines = []

                                    # Status line
                                    status_text = Text()
                                    status_text.append(f"Generating with {model_name}", style="cyan")
                                    status_text.append(f" • {elapsed:.1f}s", style="dim")
                                    status_text.append(f" • {token_count} tokens", style="dim")
                                    if tokens_per_sec > 0:
                                        status_text.append(f" • {tokens_per_sec:.0f} t/s", style="dim")
                                    display_lines.append(status_text)

                                    # Content - show full content as it streams
                                    display_lines.append("")  # Empty line
                                    display_lines.append(Text(content))

                                    # Update live display
                                    from rich.console import Group
                                    live.update(Group(*display_lines))

                                elif display_mode == "simple":
                                    # Simple mode - just print tokens as they come
                                    self.console.print(token, end="", highlight=False)

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
            # Clean up display
            if status_context:
                status_context.__exit__(None, None, None)
                # Print newline after streaming completes when using status mode
                if display_mode == "status":
                    self.console.print()  # Add newline at end
            if live:
                live.stop()
                # Don't print content here - let the caller handle it

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