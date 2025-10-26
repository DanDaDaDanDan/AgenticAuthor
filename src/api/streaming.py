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


class StreamHandler:
    """Handle streaming responses with Rich display."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize stream handler."""
        self.console = console or Console()
        self.buffer = ""
        self.total_tokens = 0

    def _repair_json_escaping(self, content: str) -> str:
        """
        Repair common JSON escaping issues from LLM responses.

        Fixes:
        - Double-escaped quotes: \\" -> \" (when LLM pre-escapes quotes in prose)
        - Literal newlines in string values: \n → \\n (CRITICAL for copy editing)
        - Literal tabs in string values: \t → \\t
        - Literal carriage returns: \r → \\r
        - Preserves intentional backslashes (like \\n for newline representation)

        Args:
            content: Raw JSON string from LLM

        Returns:
            Repaired JSON string
        """
        import re
        from ..utils.logging import get_logger

        logger = get_logger()
        original_content = content
        repairs_made = []

        # Fix pattern: \\" (double-escaped quote) -> " (normal quote)
        # This handles cases where LLM pre-escaped quotes in prose text
        # The pattern looks for: backslash, backslash, quote
        # And replaces with: backslash, quote (which is correct JSON escaping)
        repaired = re.sub(r'\\\\(")', r'\\\1', content)
        if repaired != content:
            fixes = content.count('\\\\"') - repaired.count('\\\\"')
            repairs_made.append(f"double-escaped quotes: {fixes}")
            content = repaired

        # CRITICAL FIX: Literal newlines/tabs/cr in JSON string values
        # This is the PRIMARY cause of copy editing failures at position ~9760
        # Pattern: detect literal newlines/tabs that should be escaped
        # We need to be careful not to break already-valid JSON structure

        # First, let's detect if we have literal newlines in what should be string values
        # Look for the pattern: \" followed by literal newline/tab followed by more content
        # This suggests we're inside a JSON string value that has unescaped whitespace

        literal_newlines = content.count('\n')
        literal_tabs = content.count('\t')
        literal_cr = content.count('\r')

        if literal_newlines > 30 or literal_tabs > 30 or literal_cr > 5:
            # Large number of literal whitespace suggests they're in a string value
            # Need to escape them, but ONLY within string values, not in JSON structure

            # Strategy: Parse JSON structure to identify string value regions
            # Then escape only the literal whitespace within those regions

            # Quick heuristic: if we see `\\" \n\n\"` pattern, that's definitely wrong
            problem_pattern = r'(\\") ([\n\r\t]+)(")'
            if re.search(problem_pattern, content):
                if logger:
                    logger.warning("DETECTED: Literal whitespace after escaped quote (copy editing bug pattern)")

                # Fix this specific pattern: `\\" \n\n\"` → `\\"\n\n\"`
                content = re.sub(r'(\\") +([\n\r\t]+)', r'\1\2', content)  # Remove space before newlines
                repairs_made.append("removed spaces before literal newlines")

            # Now escape all literal newlines/tabs/cr in the JSON
            # We need to do this ONLY in string value regions
            # For simplicity, we'll do a smart replacement that avoids JSON structure newlines

            # Count newlines in what appears to be a large string value (line 2 usually)
            lines = content.split('\n')
            if len(lines) > 2 and len(lines[1]) > 5000:
                # Line 2 is huge - this is typical of copy editing with edited_chapter field
                # All newlines in line 2 (after the opening brace and key) should be escaped

                # Reconstruct: keep line 1 intact, escape all in line 2+, keep last line
                line1 = lines[0]
                # Find where the string value actually starts (after "edited_chapter": ")
                remaining = '\n'.join(lines[1:])

                # Escape literal newlines, tabs, cr in the string value
                escaped = remaining.replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')

                content = line1 + '\n' + escaped
                repairs_made.append(f"escaped literal newlines: {literal_newlines}, tabs: {literal_tabs}, cr: {literal_cr}")

        # Log if repairs were made
        if repairs_made:
            if logger:
                logger.warning(f"JSON repair: Applied fixes - {', '.join(repairs_made)}")
                logger.debug(f"JSON repair: Original length {len(original_content)}, repaired length {len(content)}")

        return content

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

        # NO Live display - it interferes with streaming content causing garbled output
        # Just show a simple message at the start
        self.console.print(f"[cyan]{display_label}...[/cyan]")
        self.console.print()  # Blank line for readability

        # DIAGNOSTIC: Capture raw SSE events for debugging JSON issues
        raw_sse_events = [] if logger else None

        try:
            event_count = 0
            async for line in response.content:
                event_count += 1
                if event_count == 1 and logger:
                    logger.debug(f"Stream: First SSE event received, starting to parse")
                line = line.decode('utf-8').strip()

                # Capture raw SSE events for potential debugging (sample only to avoid memory issues)
                if raw_sse_events is not None and (event_count <= 50 or event_count % 100 == 0):
                    raw_sse_events.append((event_count, line[:500]))  # Truncate to 500 chars per event

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
                                # DIAGNOSTIC: Detect literal newlines being added to JSON string values
                                # This is the root cause of copy editing failures at position ~9760
                                if logger and '\n' in token and token_count > 50:
                                    # Only log if we're deep enough into the response (not just JSON structure)
                                    # And if we see a literal newline in the token
                                    if token_count % 100 == 0:  # Sample every 100 tokens to avoid spam
                                        logger.debug(f"Token {token_count}: contains {token.count(chr(10))} literal newline(s), token_len={len(token)}")
                                        logger.debug(f"Token sample: {repr(token[:50])}")

                                full_content += token
                                token_count += 1

                            # Mode-specific field detection
                            if token and not field_found:
                                if mode == "array_first":
                                    # Phase 1: Look for array start (once)
                                    if not array_started and '[' in full_content:
                                        array_started = True
                                        array_idx = full_content.find('[')
                                        if logger:
                                            logger.debug(f"Array detected at position {array_idx}")

                                    # Phase 2: Look for first object after array (keep checking until found)
                                    if array_started and not in_first_object:
                                        array_idx = full_content.find('[')
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

                                    # Phase 3: If we're in the first object, look for the field (search from start, not last_processed_idx)
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
                                    # Strip markdown fences in real-time for clean display
                                    field_found = True
                                    in_value = True
                                    last_processed_idx = 0
                                    # Clean display: strip markdown fences if present
                                    cleaned = full_content
                                    if cleaned.startswith("```json\n"):
                                        cleaned = cleaned[8:]  # Remove ```json\n (8 chars)
                                    elif cleaned.startswith("```json"):
                                        cleaned = cleaned[7:]  # Remove ```json (7 chars)
                                    elif cleaned.startswith("```\n"):
                                        cleaned = cleaned[4:]  # Remove ```\n (4 chars)
                                    elif cleaned.startswith("```"):
                                        cleaned = cleaned[3:]  # Remove ``` (3 chars)
                                    # Remove trailing fence if complete
                                    if cleaned.endswith("\n```"):
                                        cleaned = cleaned[:-4]  # Remove \n``` (4 chars)
                                    elif cleaned.endswith("```"):
                                        cleaned = cleaned[:-3]  # Remove ``` (3 chars)
                                    display_content = cleaned

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

                            # NO status display updates - they cause garbling
                            # Just stream content to console (scrollable)
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
            # Add newline after streaming content
            if display_content:
                self.console.print()

            # Show completion message with stats
            elapsed = time.time() - start_time
            tokens_per_sec = token_count / elapsed if elapsed > 0 else 0
            word_count = len(display_content.split()) if display_content else 0
            self.console.print(f"\n[dim]✓ {word_count:,} words generated in {elapsed:.1f}s ({tokens_per_sec:.0f} t/s)[/dim]\n")

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
            # Repair common JSON escaping issues before parsing
            repaired_content = self._repair_json_escaping(full_content)
            parsed_json = json.loads(repaired_content)
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

                    # Save raw SSE events if we captured them (DIAGNOSTIC)
                    if raw_sse_events:
                        try:
                            from pathlib import Path
                            debug_dir = Path('.agentic/debug')
                            debug_dir.mkdir(parents=True, exist_ok=True)
                            sse_debug_file = debug_dir / f"sse_events_{int(time.time())}.jsonl"

                            with open(sse_debug_file, 'w', encoding='utf-8') as f:
                                for event_num, event_data in raw_sse_events:
                                    f.write(json.dumps({"event": event_num, "data": event_data}) + '\n')

                            logger.warning(f"Saved {len(raw_sse_events)} raw SSE events to: {sse_debug_file}")
                        except Exception as sse_err:
                            logger.error(f"Failed to save SSE events: {sse_err}")

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
        display_mode: str = "status",  # New parameter: "status", "live", or "simple"
        generation_id_from_header: Optional[str] = None  # Generation ID from HTTP headers
    ) -> Dict[str, Any]:
        """
        Handle SSE stream with status display and graceful long-operation handling.

        DESIGNED FOR VERY LONG OPERATIONS:
        - Supports 30+ minute operations (novel generation, heavy reasoning)
        - Shows periodic "heartbeat" messages during long pauses (every 30s)
        - No read timeouts - waits as long as needed for reasoning models
        - User can cancel anytime with Ctrl+C

        Shows live updates of:
        - Elapsed time
        - Token count
        - Tokens per second
        - Content as it streams
        - "Model thinking..." messages during long pauses (o1/o3 reasoning)

        Args:
            response: The SSE response stream
            model_name: Name of the model for display
            on_token: Optional callback for each token
            display: Whether to display output
            display_mode: Display mode - "status" (console.status), "live" (Live display), "simple" (plain), or "silent" (no status, just content)
            generation_id_from_header: Generation ID from HTTP X-Generation-ID header

        Note:
            During long reasoning pauses (5+ minutes), status will show:
            "Model thinking... (Xm Ys since last token, N tokens so far)"
            This is NORMAL for reasoning models like o1/o3 - they think before writing.
        """
        # Import loggers at method start
        from ..utils.logging import get_logger
        from ..utils.session_logger import get_session_logger

        logger = get_logger()
        session_logger = get_session_logger()

        content = ""
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        finish_reason = None
        model = None
        token_count = 0
        start_time = time.time()
        status_context = None
        live = None

        # COMPREHENSIVE METADATA CAPTURE: Track all SSE event metadata
        generation_id_from_stream = None  # From SSE event 'id' field
        created_timestamp = None  # From SSE event 'created' field
        first_event_logged = False  # Track if we've logged the first event

        # GRACEFUL LONG-OPERATION HANDLING: Track time for heartbeat messages
        last_token_time = time.time()  # When we last received a token
        last_heartbeat_time = time.time()  # When we last showed a heartbeat
        heartbeat_interval = 30  # Show heartbeat every 30 seconds of silence

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
            try:
                async for line in response.content:
                    line = line.decode('utf-8').strip()

                    # GRACEFUL LONG-OPERATION HANDLING: Show periodic heartbeat during long pauses
                    # If no tokens for 30+ seconds, show user that we're still waiting
                    current_time = time.time()
                    time_since_last_token = current_time - last_token_time
                    time_since_last_heartbeat = current_time - last_heartbeat_time

                    # STALL DETECTION: If stream has stalled (started generating but stopped), abort and retry
                    # This catches API backend failures where connection stays open but data stops flowing
                    MAX_STALL_TIME = 60  # seconds without tokens before considering it stalled
                    MIN_TOKENS_FOR_STALL = 10  # need at least some tokens to consider it "stalled" vs "slow start"

                    if token_count > MIN_TOKENS_FOR_STALL and time_since_last_token > MAX_STALL_TIME:
                        # Stream has stalled - we started generating but haven't received tokens in 60s
                        elapsed_total = current_time - start_time
                        error_msg = (
                            f"Stream stalled: received {token_count} tokens then stopped. "
                            f"No new tokens for {int(time_since_last_token)}s (max: {MAX_STALL_TIME}s). "
                            f"This usually indicates an API backend failure."
                        )
                        if logger:
                            logger.error(error_msg)
                            logger.error(f"Stream stats: {token_count} tokens, {len(content)} chars, {elapsed_total:.1f}s total")

                        # Raise exception to trigger retry logic
                        raise Exception(f"Generation stalled after {token_count} tokens (API backend likely crashed)")

                    if time_since_last_token >= heartbeat_interval and time_since_last_heartbeat >= heartbeat_interval:
                        elapsed_total = current_time - start_time
                        if display and display_mode == "status" and status_context:
                            # Update status to show we're still waiting
                            mins = int(time_since_last_token // 60)
                            secs = int(time_since_last_token % 60)
                            status_context.update(
                                f"[yellow]Model thinking...[/yellow] ({mins}m {secs}s since last token, {token_count} tokens so far)"
                            )
                        elif logger and token_count == 0:
                            # If we haven't received any tokens yet, log that we're waiting
                            logger.info(f"Waiting for model response... {int(elapsed_total)}s elapsed (this is normal for reasoning models)")
                        elif logger:
                            # Log periodic heartbeat for reasoning pauses
                            logger.debug(f"Model paused (reasoning): {int(time_since_last_token)}s since last token, {token_count} tokens received so far")

                        last_heartbeat_time = current_time

                    if not line or not line.startswith('data: '):
                        continue

                    if line == 'data: [DONE]':
                        break

                    try:
                        # Parse SSE data
                        data_str = line[6:]  # Remove 'data: ' prefix
                        data = json.loads(data_str)

                        # COMPREHENSIVE METADATA CAPTURE: Extract ALL event metadata on first event
                        if not first_event_logged:
                            if 'id' in data:
                                generation_id_from_stream = data['id']
                            if 'created' in data:
                                created_timestamp = data['created']
                            if 'model' in data:
                                model = data['model']

                            if logger:
                                logger.debug(f"=== SSE FIRST EVENT METADATA ===")
                                logger.debug(f"Event ID (generation_id): {generation_id_from_stream}")
                                logger.debug(f"Created timestamp: {created_timestamp}")
                                logger.debug(f"Model (actual): {model}")
                                logger.debug(f"Object type: {data.get('object', 'N/A')}")
                                # Log generation_id from header vs stream
                                if generation_id_from_header and generation_id_from_stream:
                                    if generation_id_from_header != generation_id_from_stream:
                                        logger.warning(f"Generation ID mismatch! Header: {generation_id_from_header}, Stream: {generation_id_from_stream}")
                                # Log any unexpected top-level fields
                                expected_fields = {'id', 'object', 'created', 'model', 'choices', 'usage'}
                                unexpected = set(data.keys()) - expected_fields
                                if unexpected:
                                    logger.debug(f"Unexpected SSE fields: {unexpected} = {[data.get(k) for k in unexpected]}")

                            first_event_logged = True

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
                                    # Update last_token_time whenever we receive content
                                    last_token_time = time.time()

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

                        # Extract model info (update if it appears later in stream)
                        if 'model' in data:
                            model = data['model']

                        # COMPREHENSIVE METADATA CAPTURE: Extract COMPLETE usage object with ALL fields
                        if 'usage' in data and data['usage']:
                            usage = data['usage']  # Store entire dict - don't cherry-pick fields

                            if logger:
                                logger.debug(f"=== USAGE DATA RECEIVED ===")
                                logger.debug(f"Complete usage object: {usage}")
                                # Log standard fields
                                logger.debug(f"  prompt_tokens: {usage.get('prompt_tokens', 'N/A')}")
                                logger.debug(f"  completion_tokens: {usage.get('completion_tokens', 'N/A')}")
                                logger.debug(f"  total_tokens: {usage.get('total_tokens', 'N/A')}")
                                # Log any extended/non-standard fields (e.g., reasoning tokens, cached tokens)
                                standard_fields = {'prompt_tokens', 'completion_tokens', 'total_tokens'}
                                extended_fields = set(usage.keys()) - standard_fields
                                if extended_fields:
                                    logger.info(f"  ⚠️  EXTENDED USAGE FIELDS: {extended_fields}")
                                    for field in extended_fields:
                                        logger.info(f"    {field}: {usage[field]}")

                    except json.JSONDecodeError:
                        # Skip malformed data
                        continue

            except Exception as stream_error:
                # Handle streaming errors (TransferEncodingError, ConnectionError, etc.)
                import aiohttp
                if isinstance(stream_error, (aiohttp.ClientPayloadError, aiohttp.ClientConnectionError)):
                    # If we got partial content, return it with a warning
                    if content and token_count > 0:
                        # Log explicit warning about partial content
                        from ..utils.logging import get_logger
                        logger = get_logger()
                        if logger:
                            logger.warning(
                                f"STREAM INTERRUPTED: {type(stream_error).__name__}, "
                                f"received {token_count} tokens before interruption, "
                                f"model={model}"
                            )

                        # Show clear user warning
                        self.console.print(f"\n[bold yellow]⚠️  STREAM INTERRUPTED ({type(stream_error).__name__})[/bold yellow]")
                        self.console.print(f"[yellow]Received {token_count} tokens before interruption[/yellow]")
                        self.console.print(f"[yellow]Response saved to emergency backup and debug file[/yellow]")
                        self.console.print(f"[yellow]Check .agentic/debug/emergency-responses/ for full content[/yellow]")

                        # Set finish reason to indicate truncation
                        finish_reason = "connection_error"
                    else:
                        # No content received, re-raise
                        raise
                else:
                    # Other exceptions, re-raise
                    raise

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

                # For silent mode, show summary stats at the end (but wait for usage correction first)
                pass  # Summary will be shown after usage correction

        # If usage wasn't provided or is suspiciously low (common with truncation), estimate from token_count
        reported_completion = usage.get('completion_tokens', 0)
        if token_count > 0 and (reported_completion == 0 or reported_completion < token_count * 0.5):
            # Stream was truncated or didn't include accurate usage info
            # API sometimes reports 1 token or very low count when stream is truncated
            # Use our counted tokens as completion tokens
            usage['completion_tokens'] = token_count
            usage['total_tokens'] = usage.get('prompt_tokens', 0) + token_count

            if logger and reported_completion > 0:
                logger.warning(f"API reported {reported_completion} completion tokens but we counted {token_count} - using our count")

        # NOW show summary with corrected usage (for silent mode)
        if display and display_mode == "silent" and token_count > 0:
            elapsed = time.time() - start_time
            # Use the corrected completion_tokens from usage, not our counted tokens
            actual_completion_tokens = usage.get('completion_tokens', token_count)
            tokens_per_sec = actual_completion_tokens / elapsed if elapsed > 0 else 0
            word_count = len(content.split()) if content else 0

            self.console.print(
                f"\n[dim]✓ Generated {word_count:,} words in {elapsed:.1f}s "
                f"({actual_completion_tokens} tokens • {tokens_per_sec:.0f} t/s)[/dim]"
            )

        # Check for empty response and provide helpful error
        if not content and token_count == 0:
            error_msg = "API returned empty response (0 tokens)"

            # Check for content moderation
            if finish_reason == "content_filter":
                error_msg = "Content filtered by model's moderation system (OpenAI content policy)"
            elif finish_reason:
                error_msg = f"API returned empty response with finish_reason: {finish_reason}"
            else:
                # No finish_reason provided - this is unusual
                error_msg = f"{error_msg} with no finish_reason (possible API/model issue)"

            # Add model info if available
            if model:
                error_msg = f"{error_msg} [model: {model}]"

            # Log the error details for debugging
            if logger:
                logger.error(f"Empty response error: {error_msg}")
                logger.error(f"Stream stats: token_count={token_count}, finish_reason={finish_reason}, model={model}")

            raise Exception(error_msg)

        # CRITICAL: Save raw response to emergency backup BEFORE any post-processing
        # This ensures we never lose a response even if subsequent operations fail
        try:
            from ..config import get_settings
            from datetime import datetime
            settings = get_settings()
            emergency_dir = settings.root_dir / ".agentic" / "debug" / "emergency-responses"
            emergency_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Include model name and token count in filename for easy identification
            safe_model_name = model.replace('/', '_') if model else 'unknown'
            emergency_file = emergency_dir / f"{timestamp}_{safe_model_name}_{token_count}tokens.txt"

            # Save with metadata header
            emergency_content = f"""# Emergency Response Backup
# Timestamp: {datetime.now().isoformat()}
# Model: {model}
# Tokens: {token_count}
# Finish Reason: {finish_reason}
# Elapsed: {time.time() - start_time:.2f}s

{content}"""
            emergency_file.write_text(emergency_content, encoding='utf-8')

            if logger:
                logger.debug(f"Emergency backup saved: {emergency_file.name}")
        except Exception as backup_error:
            # NEVER let backup failure crash actual response
            if logger:
                logger.warning(f"Failed to save emergency backup: {backup_error}")
            pass

        # Return ALL captured metadata
        return {
            'content': content,
            'usage': usage,  # Complete usage dict with ALL fields (including reasoning tokens if present)
            'finish_reason': finish_reason,
            'model': model,
            'token_count': token_count,
            'elapsed_time': time.time() - start_time,
            'generation_id': generation_id_from_stream or generation_id_from_header,  # For metadata fetch
            'created_timestamp': created_timestamp  # SSE event creation time
        }

    # Removed handle_sse_stream(), stream_with_progress(), and collect_stream()
    # These are legacy methods replaced by handle_sse_stream_with_status() and handle_json_stream_with_display()
    # Active streaming uses the newer methods with better display modes and error handling


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