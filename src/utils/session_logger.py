"""Session logging system that captures all output immediately."""
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO, Any
import json
import traceback
from rich.console import Console
from io import StringIO


class SessionLogger:
    """Logs all session output to timestamped files."""

    def __init__(self, logs_dir: Optional[Path] = None):
        """Initialize session logger.

        Args:
            logs_dir: Directory for log files (default: .agentic/logs)
        """
        # Set up logs directory
        self.logs_dir = logs_dir or Path(".agentic/logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Create single JSONL log file (JSON Lines format)
        self.session_start = datetime.now()
        timestamp = self.session_start.strftime("%Y%m%d_%H%M%S")
        self.log_file_path = self.logs_dir / f"session_{timestamp}.jsonl"

        # Open log file
        self.log_file: Optional[TextIO] = None

        # Initialize file
        self._init_log_files()

        # Track if we're intercepting
        self.intercepting = False
        self.original_stdout = None
        self.original_stderr = None

    def _init_log_files(self):
        """Initialize JSONL log file with session start event."""
        try:
            # Create JSONL file (line buffered for immediate writes)
            self.log_file = open(self.log_file_path, 'w', encoding='utf-8', buffering=1)

            # Write session start event
            self._write_event("session_start", {
                "timestamp": self.session_start.isoformat(),
                "log_file": str(self.log_file_path),
                "cwd": str(Path.cwd()),
                "pid": os.getpid()
            })

        except Exception as e:
            print(f"Warning: Could not create log file: {e}")

    def log(self, message: str, level: str = "INFO", **metadata):
        """Log a message immediately in JSONL format.

        Args:
            message: Message to log
            level: Log level (INFO, WARNING, ERROR, DEBUG)
            **metadata: Additional metadata to include
        """
        if not self.log_file:
            return

        try:
            self._write_event("log", {
                "timestamp": datetime.now().isoformat(),
                "level": level,
                "message": message,
                **metadata
            })

        except Exception:
            pass  # Silent fail to avoid disrupting the session

    def log_command(self, command: str, args: str = "", result: Any = None, error: Optional[str] = None):
        """Log a command execution in JSONL format.

        Args:
            command: Command name
            args: Command arguments
            result: Command result (will be stringified)
            error: Error message if command failed
        """
        event_data = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "args": args
        }

        if error:
            event_data["error"] = error
        elif result is not None:
            # Try to serialize result, fall back to string
            try:
                if isinstance(result, (dict, list)):
                    event_data["result"] = result
                else:
                    event_data["result"] = str(result)
            except:
                event_data["result"] = "<non-serializable>"

        self._write_event("command", event_data)

    def log_api_call(self, model: str, prompt: str, response: str, tokens: dict, error: Optional[str] = None, full_messages: list = None, request_params: dict = None, operation: str = None, finish_reason: str = None):
        """Log an API call with FULL request and response details in JSONL.

        Args:
            model: Model name
            prompt: Prompt sent (converted from messages for backward compatibility)
            response: Response received
            tokens: Token usage dict
            error: Error message if call failed
            full_messages: Complete messages array sent to API (list of dicts)
            request_params: Full request parameters (temperature, max_tokens, etc.)
            operation: Optional operation name (e.g., "premise-generation", "chapter-3")
            finish_reason: API finish reason (e.g., "stop", "length", "content_filter")
        """
        self._write_event("api_call", {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "operation": operation,
            "request_params": request_params or {},
            "messages": full_messages or [],
            "prompt": prompt,  # Keep for backward compatibility
            "response": response if not error else None,
            "response_length": len(response) if response else 0,
            "tokens": tokens or {},
            "finish_reason": finish_reason,
            "error": error
        })

        # Also save as individual text file for easy debugging
        self.save_llm_call_file(
            model=model,
            messages=full_messages or [],
            response=response if not error else f"ERROR: {error}",
            request_params=request_params or {},
            tokens=tokens or {},
            operation=operation,
            error=error,
            finish_reason=finish_reason
        )

    def log_api_error(self, model: str, error: Exception, request_params: dict = None, full_messages: list = None):
        """Log an API call that failed with FULL request details in JSONL.

        Args:
            model: Model name that was being used
            error: Exception that occurred
            request_params: Optional dict of request parameters (temperature, max_tokens, etc.)
            full_messages: Complete messages array that was sent to API
        """
        self._write_event("api_error", {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "error": str(error),
            "error_type": type(error).__name__,
            "request_params": request_params or {},
            "messages": full_messages or []
        })

    def save_llm_call_file(
        self,
        model: str,
        messages: list,
        response: str,
        request_params: dict,
        tokens: dict,
        operation: Optional[str] = None,
        error: Optional[str] = None,
        finish_reason: Optional[str] = None
    ):
        """Save LLM call details to individual text file for easy debugging.

        Creates a human-readable text file with:
        - Timestamp, model, and operation
        - All request parameters
        - Complete messages/prompt
        - Full response
        - Token usage and cost
        - Finish reason (stop, length, content_filter, etc.)

        Files are saved to: .agentic/debug/llm-calls/YYYYMMDD_HHMMSS_model_operation.txt

        Args:
            model: Model name
            messages: Complete messages array
            response: Response text
            request_params: Request parameters dict
            tokens: Token usage dict
            operation: Optional operation name
            error: Optional error message
            finish_reason: Optional API finish reason
        """
        try:
            # Create debug directory
            debug_dir = self.logs_dir.parent / "debug" / "llm-calls"
            debug_dir.mkdir(parents=True, exist_ok=True)

            # Create filename
            timestamp = datetime.now()
            timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")

            # Sanitize model name for filename
            model_clean = model.replace("/", "_").replace("\\", "_")

            # Sanitize operation name for filename
            operation_clean = operation.replace(" ", "-").replace("/", "-") if operation else "unknown"

            filename = f"{timestamp_str}_{model_clean}_{operation_clean}.txt"
            filepath = debug_dir / filename

            # Build file content
            content_parts = []

            # Header
            content_parts.append("=" * 80)
            content_parts.append("LLM CALL DEBUG LOG")
            content_parts.append("=" * 80)
            content_parts.append(f"Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            content_parts.append(f"Model: {model}")
            if operation:
                content_parts.append(f"Operation: {operation}")
            if error:
                content_parts.append(f"ERROR: {error}")
            content_parts.append("")

            # Parameters section
            content_parts.append("=" * 80)
            content_parts.append("PARAMETERS")
            content_parts.append("=" * 80)
            for key, value in request_params.items():
                content_parts.append(f"{key}: {value}")
            content_parts.append("")

            # Messages section
            content_parts.append("=" * 80)
            content_parts.append("MESSAGES")
            content_parts.append("=" * 80)
            for msg in messages:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                content_parts.append(f"\n[{role.upper()}]")
                content_parts.append(content)
                content_parts.append("")

            # Response section
            content_parts.append("=" * 80)
            content_parts.append("RESPONSE")
            content_parts.append("=" * 80)
            content_parts.append(response)
            content_parts.append("")

            # Metadata section
            content_parts.append("=" * 80)
            content_parts.append("METADATA")
            content_parts.append("=" * 80)
            if tokens:
                prompt_tokens = tokens.get('prompt_tokens', 0)
                completion_tokens = tokens.get('completion_tokens', 0)
                total_tokens = tokens.get('total_tokens', 0)
                content_parts.append(f"Prompt Tokens: {prompt_tokens:,}")
                content_parts.append(f"Completion Tokens: {completion_tokens:,}")
                content_parts.append(f"Total Tokens: {total_tokens:,}")

                # Try to calculate cost if possible (would need model pricing)
                # For now just note tokens
            else:
                content_parts.append("Token usage: Not available")

            content_parts.append(f"Response Length: {len(response)} characters")

            if finish_reason:
                content_parts.append(f"Finish Reason: {finish_reason}")

            content_parts.append("")

            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content_parts))

        except Exception as e:
            # Silent fail - don't disrupt the session if debugging file can't be saved
            # But log to the regular log
            self.log(f"Failed to save LLM call debug file: {e}", level="WARNING")

    def log_error(self, error: Exception, context: str = ""):
        """Log an error with traceback in JSONL.

        Args:
            error: Exception object
            context: Additional context about where the error occurred
        """
        self._write_event("error", {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "error": str(error),
            "type": type(error).__name__,
            "traceback": traceback.format_exc()
        })

    def log_console_output(self, content: str, output_type: str = "stdout"):
        """Log console output (stdout/stderr) in JSONL.

        Args:
            content: Output content
            output_type: Type of output (stdout/stderr)
        """
        if not content or not content.strip():
            return

        self._write_event("console", {
            "timestamp": datetime.now().isoformat(),
            "type": output_type,
            "content": content
        })

    def _write_event(self, event_type: str, data: dict):
        """Write an event to the JSONL log file (one JSON object per line).

        Args:
            event_type: Type of event
            data: Event data
        """
        if not self.log_file:
            return

        try:
            event = {
                "type": event_type,
                "data": data
            }
            # Write as single JSON line
            json_line = json.dumps(event, default=str)
            self.log_file.write(json_line + '\n')
            self.log_file.flush()  # Immediate write

        except Exception:
            pass  # Silent fail to avoid disrupting the session

    def intercept_output(self):
        """Start intercepting stdout/stderr to log everything."""
        if self.intercepting:
            return

        self.intercepting = True
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        sys.stdout = LoggingWriter(self.original_stdout, self, "stdout")
        sys.stderr = LoggingWriter(self.original_stderr, self, "stderr")

    def stop_intercept(self):
        """Stop intercepting output."""
        if not self.intercepting:
            return

        self.intercepting = False
        if self.original_stdout:
            sys.stdout = self.original_stdout
        if self.original_stderr:
            sys.stderr = self.original_stderr

    def close(self):
        """Close log file."""
        self.stop_intercept()

        if self.log_file:
            # Write final event
            self._write_event("session_end", {
                "timestamp": datetime.now().isoformat(),
                "duration": str(datetime.now() - self.session_start)
            })

            self.log_file.close()
            self.log_file = None

    def get_latest_log(self) -> Optional[Path]:
        """Get the path to the latest JSONL log file.

        Returns:
            Path to the latest log file, or None if no logs exist
        """
        if not self.logs_dir.exists():
            return None

        log_files = sorted(self.logs_dir.glob("session_*.jsonl"),
                          key=lambda f: f.stat().st_mtime,
                          reverse=True)

        return log_files[0] if log_files else None

    def __enter__(self):
        """Context manager entry."""
        self.intercept_output()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type:
            self.log_error(exc_val, "Unhandled exception")
        self.close()


class LoggingWriter:
    """Writer that duplicates output to both original stream and logger."""

    def __init__(self, original, logger: SessionLogger, stream_type: str):
        """Initialize logging writer.

        Args:
            original: Original stream (stdout/stderr)
            logger: SessionLogger instance
            stream_type: Type of stream (stdout/stderr)
        """
        self.original = original
        self.logger = logger
        self.stream_type = stream_type
        # Provide buffer attribute that prompt_toolkit expects
        self.buffer = getattr(original, 'buffer', original)

    def write(self, text):
        """Write to both original stream and logger."""
        # Write to original stream
        if self.original:
            self.original.write(text)

        # Log the output
        self.logger.log_console_output(text, self.stream_type)

    def flush(self):
        """Flush the original stream."""
        if self.original:
            self.original.flush()

    def __getattr__(self, name):
        """Delegate other attributes to original stream."""
        return getattr(self.original, name)


# Global session logger instance
_session_logger: Optional[SessionLogger] = None


def get_session_logger() -> Optional[SessionLogger]:
    """Get the global session logger."""
    return _session_logger


def init_session_logger(logs_dir: Optional[Path] = None) -> SessionLogger:
    """Initialize the global session logger.

    Args:
        logs_dir: Directory for log files

    Returns:
        The initialized SessionLogger
    """
    global _session_logger
    _session_logger = SessionLogger(logs_dir)
    return _session_logger


def get_latest_log() -> Optional[Path]:
    """Get the path to the latest JSONL log file.

    Returns:
        Path to the latest log file
    """
    logs_dir = Path(".agentic/logs")
    if not logs_dir.exists():
        return None

    log_files = sorted(logs_dir.glob("session_*.jsonl"),
                      key=lambda f: f.stat().st_mtime,
                      reverse=True)

    return log_files[0] if log_files else None