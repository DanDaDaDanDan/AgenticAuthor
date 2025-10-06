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
        model_obj: Any = None,  # Required: actual model object for capability checking
        mode: str = "field"  # "field", "array_first", or "full"
    ) -> Dict[str, Any]:
        """
        Handle SSE stream for JSON responses, displaying specific fields as they stream.

        Args:
            response: The streaming response
            model_name: Name of the model for display
            display_field: The JSON field to display as it streams (e.g., "premise", "summary")
            display_label: Label for what's being generated
            on_token: Optional callback for each token
            model_obj: Model object for capability checking
            mode: Display mode - "field" (extract field from object),
                  "array_first" (show first element of array),
                  "array_progressive" (show display_field from all array elements as they complete),
                  "full" (show entire JSON)
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

        # Additional state for array_first mode
        array_started = False
        first_object_depth = 0
        current_depth = 0
        in_first_object = False

        # Additional state for array_progressive mode
        last_field_search_idx = 0  # Where we last searched for fields
        completed_fields = []  # Track which field values we've already shown

        # Track displayed content for incremental printing
        self._last_displayed_length = 0

        # Debug logging - use BOTH loggers for comprehensive coverage
        from ..utils.logging import get_logger
        from ..utils.session_logger import get_session_logger

        logger = get_logger()  # Global logger -> .agentic/logs/agentic_YYYYMMDD.log
        session_logger = get_session_logger()  # Session logger -> .agentic/logs/session_*.jsonl

        if logger:
            logger.debug(f"=== Stream handler START ===")
            logger.debug(f"Stream handler: mode={mode}, display_field={display_field}, display_label={display_label}")
            logger.debug(f"Stream handler: model_name={model_name}, model_obj provided={'YES' if model_obj else 'NO'}")

        # Use Live display for non-interfering status updates
        status_text_obj = Text(f"{display_label}...", style="cyan")
        live_display = Live(
            status_text_obj,
            console=self.console,
            refresh_per_second=4,  # Reasonable refresh rate
            transient=True  # Disappears when done
        )
        live_display.__enter__()

        try:
            event_count = 0
            async for line in response.content:
                event_count += 1
                if event_count == 1 and logger:
                    logger.debug(f"Stream: First SSE event received, starting to parse")
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

                            # Mode-specific field detection
                            if token and not field_found:
                                if mode == "array_first":
                                    # Look for array start and first object
                                    if not array_started and '[' in full_content:
                                        array_started = True
                                        array_idx = full_content.find('[')
                                        if logger:
                                            logger.debug(f"Array detected at position {array_idx}")
                                        # Look for first { after [
                                        after_bracket = full_content[array_idx + 1:]
                                        if '{' in after_bracket:
                                            first_object_depth = 0
                                            in_first_object = True
                                            # DON'T set field_found yet - we need to find the actual field!
                                            # Find the { position
                                            obj_start = full_content.find('{', array_idx)
                                            last_processed_idx = obj_start
                                            if logger:
                                                logger.debug(f"First object detected at position {obj_start}")

                                            # Now look for the display_field within first object
                                            # This will be extracted in the next iteration

                                    # If we're in the first object, look for the field (search from start, not last_processed_idx)
                                    if in_first_object and not in_value and not field_found:
                                        field_pattern = f'"{display_field}":'
                                        field_pattern_spaced = f'"{display_field}" :'
                                        # CRITICAL FIX: Search from beginning of full_content, not from last_processed_idx
                                        if field_pattern in full_content or field_pattern_spaced in full_content:
                                            # Find where the value starts (try both patterns)
                                            field_idx = full_content.find(field_pattern)
                                            if field_idx == -1:
                                                field_idx = full_content.find(field_pattern_spaced)
                                                field_pattern = field_pattern_spaced
                                            if field_idx != -1:
                                                if logger:
                                                    logger.debug(f"Field '{display_field}' found at position {field_idx}")
                                                after_field = full_content[field_idx + len(field_pattern):]
                                                # Skip whitespace and find opening quote
                                                after_field = after_field.lstrip()
                                                if after_field.startswith('"'):
                                                    field_found = True  # NOW set field_found
                                                    in_value = True
                                                    last_processed_idx = len(full_content) - len(after_field) + 1
                                                    if logger:
                                                        logger.debug(f"Starting to stream field value from position {last_processed_idx}")

                                elif mode == "array_progressive":
                                    # Show each occurrence of display_field as it completes
                                    # Search for completed field values from where we last looked
                                    field_pattern = f'"{display_field}":'
                                    field_pattern_spaced = f'"{display_field}" :'

                                    # Search from last position
                                    search_idx = last_field_search_idx
                                    while True:
                                        # Find next field occurrence
                                        field_idx = full_content.find(field_pattern, search_idx)
                                        if field_idx == -1:
                                            field_idx = full_content.find(field_pattern_spaced, search_idx)
                                            pattern_used = field_pattern_spaced if field_idx != -1 else field_pattern
                                        else:
                                            pattern_used = field_pattern

                                        if field_idx == -1:
                                            # No more fields found yet
                                            break

                                        # Find the value (should be a string)
                                        value_start_pos = field_idx + len(pattern_used)
                                        after_field = full_content[value_start_pos:].lstrip()

                                        if after_field.startswith('"'):
                                            # Find closing quote
                                            value_start = value_start_pos + (len(full_content[value_start_pos:]) - len(after_field)) + 1
                                            value_end = full_content.find('"', value_start)

                                            # Check if string is complete (not escaped quote)
                                            while value_end != -1 and value_end > 0 and full_content[value_end - 1] == '\\':
                                                value_end = full_content.find('"', value_end + 1)

                                            if value_end != -1:
                                                # Complete field value found
                                                field_value = full_content[value_start:value_end]
                                                # Decode escape sequences
                                                field_value = field_value.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
                                                field_value = field_value.replace('\\"', '"').replace('\\\\', '\\')

                                                # Check if we've already displayed this one
                                                if field_idx not in [f[0] for f in completed_fields]:
                                                    # New complete field - display it
                                                    chapter_num = len(completed_fields) + 1
                                                    self.console.print(f"\n[bold green]Chapter {chapter_num}:[/bold green]")
                                                    self.console.print(f"[dim]{field_value}[/dim]\n")
                                                    self.console.file.flush()
                                                    completed_fields.append((field_idx, field_value))
                                                    if logger:
                                                        logger.debug(f"array_progressive: Displayed chapter {chapter_num}")

                                                # Continue searching from after this field
                                                search_idx = value_end + 1
                                                last_field_search_idx = search_idx
                                            else:
                                                # Value not complete yet
                                                break
                                        else:
                                            # Not a string value, skip
                                            search_idx = field_idx + len(pattern_used)

                                    # For array_progressive, display_content is not used (we print directly)
                                    field_found = True  # Mark as found to avoid other mode logic

                                elif mode == "full":
                                    # Show entire JSON as it streams
                                    field_found = True
                                    in_value = True
                                    last_processed_idx = 0
                                    display_content = full_content

                                else:  # mode == "field" (default)
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

                            # Update status display (batched - only every 10 tokens to reduce interference)
                            if token_count % 10 == 0 or token_count == 1:
                                elapsed = time.time() - start_time
                                tokens_per_sec = token_count / elapsed if elapsed > 0 else 0

                                # Update Live display with new Text object
                                status_msg = f"{display_label} with {model_name} • {elapsed:.1f}s • {token_count} tokens"
                                if tokens_per_sec > 0:
                                    status_msg += f" • {tokens_per_sec:.0f} t/s"
                                status_text_obj.plain = status_msg  # Update text in-place
                                live_display.update(status_text_obj)

                            # Stream content to console (scrollable)
                            # Only print if we have new content extracted
                            if token and display_content:
                                # Track what we've already printed
                                displayed_length = self._last_displayed_length
                                new_content = display_content[displayed_length:]
                                if new_content:
                                    self.console.print(new_content, end="", highlight=False)
                                    self.console.file.flush()  # Force flush to prevent buffering issues
                                    self._last_displayed_length = len(display_content)
                                    if logger and displayed_length == 0:
                                        logger.debug(f"Started printing content to console")
                            elif token and not display_content:
                                # Log periodically if we're getting tokens but no display content
                                if logger and token_count % 50 == 0:  # Log every 50 tokens to avoid spam
                                    logger.warning(f"NO DISPLAY CONTENT: {token_count} tokens, display_content={len(display_content)} chars, field_found={field_found}, in_value={in_value}, array_started={array_started if mode=='array_first' else 'N/A'}")
                                    logger.warning(f"Full content sample (first 500 chars): {full_content[:500]}")

                            if on_token:
                                on_token(token, token_count)

                    # Extract usage info if present
                    if 'usage' in data:
                        usage = data['usage']

                    # Check for finish reason
                    finish_reason = None
                    if 'finish_reason' in choice and choice['finish_reason']:
                        finish_reason = choice['finish_reason']
                        if logger:
                            logger.debug(f"Stream finish_reason: {finish_reason}")
                            if finish_reason == "length":
                                logger.warning(f"Response truncated due to max_tokens limit")

                except json.JSONDecodeError:
                    continue

        finally:
            live_display.__exit__(None, None, None)
            # Add newline after streaming content
            if display_content:
                self.console.print()

            # Log streaming completion
            if logger:
                elapsed = time.time() - start_time
                logger.debug(f"=== Stream handler COMPLETE ===")
                logger.debug(f"Streaming completed: {token_count} tokens, {len(full_content)} chars in {elapsed:.1f}s")
                logger.debug(f"Events processed: {event_count}, field_found={field_found}, in_value={in_value}")
                logger.debug(f"Display content length: {len(display_content)} chars")
                logger.debug(f"Full content preview: {full_content[:200]}...")
                if model_obj:
                    max_out = model_obj.get_max_output_tokens()
                    if max_out:
                        logger.debug(f"Model output limit: {max_out} tokens, received: {token_count} tokens ({token_count/max_out*100:.1f}%)")

        # Log final finish_reason prominently
        if logger:
            if finish_reason:
                logger.warning(f"=== STREAM FINISHED: finish_reason='{finish_reason}' ===")
                if finish_reason == "length":
                    logger.error(f"TRUNCATION: Response stopped due to max_tokens limit!")
                elif finish_reason == "stop":
                    logger.info(f"Response completed normally (stop token reached)")
            else:
                logger.warning(f"=== STREAM FINISHED: NO finish_reason provided by API ===")

        # Parse the complete JSON - try markdown extraction first, then fail fast
        try:
            parsed_json = json.loads(full_content)
            if logger:
                json_type = type(parsed_json).__name__
                json_len = len(parsed_json) if isinstance(parsed_json, (list, dict)) else 0
                logger.debug(f"JSON parsed successfully: type={json_type}, length={json_len}")
        except json.JSONDecodeError as e:
            # EXCEPTION TO FAIL-FAST: Try to extract JSON from markdown blocks first
            if logger:
                logger.warning(f"JSON parsing failed, attempting markdown extraction: {e}")

            extracted = self._extract_json_from_markdown(full_content.strip())

            if extracted:
                # Try parsing the extracted JSON
                try:
                    parsed_json = json.loads(extracted)
                    if logger:
                        logger.info(f"Successfully extracted and parsed JSON from markdown block")
                except json.JSONDecodeError as e2:
                    # Even extracted JSON failed - NOW fail fast
                    if logger:
                        logger.error(f"Markdown-extracted JSON also failed: {e2}")
                        logger.error(f"Full content length: {len(extracted)} chars")
                        logger.error(f"Finish reason was: {finish_reason}")
                    self._handle_truncated_json(extracted, e2, model_obj, model_name, finish_reason)
            else:
                # No markdown blocks found - fail fast on original error
                if logger:
                    logger.error(f"No markdown blocks found, failing on original error")
                    logger.error(f"Full content length: {len(full_content)} chars")
                    logger.error(f"Finish reason was: {finish_reason}")
                    logger.error(f"Content preview: {full_content[:500]}")
                self._handle_truncated_json(full_content.strip(), e, model_obj, model_name, finish_reason)

        # Return result with metadata in a wrapper if parsed_json is not a dict
        if isinstance(parsed_json, dict):
            # If it's already a dict, we can add metadata directly
            parsed_json['token_count'] = token_count
            parsed_json['elapsed_time'] = time.time() - start_time
            parsed_json['finish_reason'] = finish_reason  # IMPORTANT: include finish_reason
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
                'finish_reason': finish_reason,  # IMPORTANT: include finish_reason
                'usage': usage if usage else {}
            }

    def _handle_truncated_json(self, content: str, error: json.JSONDecodeError, model_obj: Any, model_name: str = "Model", finish_reason: str = None):
        """
        Handle truncated or malformed JSON by failing fast with clear error.

        Args:
            content: The problematic JSON content
            error: The JSON decode error
            model_obj: Model object for capability checking
            model_name: Model display name
            finish_reason: The finish_reason from the API (length, stop, etc.)

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

            # Display finish_reason prominently
            if finish_reason:
                self.console.print(f"\n[bold yellow]API finish_reason: '{finish_reason}'[/bold yellow]")
                if finish_reason == "length":
                    self.console.print(f"[red]→ Response was TRUNCATED by the model's max_tokens limit[/red]")
                elif finish_reason == "stop":
                    self.console.print(f"[yellow]→ Response ended normally but JSON is invalid/incomplete[/yellow]")
                else:
                    self.console.print(f"[yellow]→ Response ended with reason: {finish_reason}[/yellow]")
            else:
                self.console.print(f"\n[yellow]⚠️  No finish_reason provided by API (connection issue?)[/yellow]")

            # Check if we hit model's actual output limit
            if not model_obj:
                raise ValueError("Model object required for truncation detection - cannot determine output limits")

            max_output = model_obj.get_max_output_tokens()
            if max_output:
                # Convert tokens to approximate character count (rough estimate: 1 token ≈ 4 chars)
                max_chars = max_output * 4
                estimated_tokens = len(content) // 4
                self.console.print(f"\n[dim]Model: {model_obj.id}[/dim]")
                self.console.print(f"[dim]Max output: {max_output} tokens • Received: ~{estimated_tokens} tokens ({len(content)} chars)[/dim]")

                if abs(estimated_tokens - max_output) < 200:  # Within 200 tokens of limit
                    self.console.print(f"[yellow]⚠️   Near model output limit (within 200 tokens)[/yellow]")
                elif finish_reason == "length":
                    self.console.print(f"[red]⚠️   Stopped by max_tokens parameter or model limit[/red]")

            # Save for debugging
            from pathlib import Path
            debug_dir = Path(".agentic") / "debug"
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
            debug_dir = Path(".agentic") / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / f"invalid_json_{int(time.time())}.json"

            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(content)

            self.console.print(f"[dim]Saved invalid JSON to: {debug_file}[/dim]")
            raise error

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
            display_mode: Display mode - "status" (console.status), "live" (Live display), "simple" (plain), or "silent" (no status, just content)
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
                                    # Batch status updates - only every 20 tokens to prevent flicker
                                    if token_count % 20 == 0 or token_count == 1:
                                        status_text = f"Generating with {model_name} • {elapsed:.1f}s • {token_count} tokens"
                                        if tokens_per_sec > 0:
                                            status_text += f" • {tokens_per_sec:.0f} t/s"
                                        status_context.update(status_text)

                                    # Stream content to console (normal scrollable output)
                                    self.console.print(token, end="", highlight=False)
                                    # Flush every 10 tokens to reduce buffering but not overdo it
                                    if token_count % 10 == 0:
                                        self.console.file.flush()

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
                                    # Flush periodically to prevent buffering issues
                                    if token_count % 10 == 0:
                                        self.console.file.flush()

                                elif display_mode == "silent":
                                    # Silent mode - no status, just print content
                                    # Use file.write directly for maximum compatibility
                                    self.console.file.write(token)
                                    self.console.file.flush()  # Flush every token for immediate display

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

            if live:
                live.stop()

            # Print newline after streaming completes for all modes
            if display and display_mode in ["status", "simple", "silent"]:
                self.console.file.flush()  # Final flush
                self.console.file.write("\n")  # Add newline at end
                self.console.file.flush()

                # For silent mode, show summary stats at the end
                if display_mode == "silent" and token_count > 0:
                    elapsed = time.time() - start_time
                    tokens_per_sec = token_count / elapsed if elapsed > 0 else 0
                    word_count = len(content.split()) if content else 0

                    self.console.print(
                        f"\n[dim]✓ Generated {word_count:,} words in {elapsed:.1f}s "
                        f"({token_count} tokens • {tokens_per_sec:.0f} t/s)[/dim]"
                    )

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