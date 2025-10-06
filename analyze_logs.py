#!/usr/bin/env python
"""Log analysis helper for Claude Code to debug issues.

This script helps Claude Code analyze the latest session log when there's an error.
It provides a summary of the session, identifies errors, and extracts relevant context.
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


def get_latest_log(logs_dir: Path = Path(".agentic/logs")) -> Optional[Path]:
    """Get the most recent log file.

    Args:
        logs_dir: Directory containing log files

    Returns:
        Path to latest log file or None
    """
    if not logs_dir.exists():
        print(f"Logs directory not found: {logs_dir}")
        return None

    # Find all session logs
    log_files = sorted(
        logs_dir.glob("session_*.log"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )

    if not log_files:
        print("No log files found")
        return None

    return log_files[0]


def get_latest_json_log(logs_dir: Path = Path(".agentic/logs")) -> Optional[Path]:
    """Get the most recent JSON log file.

    Args:
        logs_dir: Directory containing log files

    Returns:
        Path to latest JSON log file or None
    """
    if not logs_dir.exists():
        return None

    json_files = sorted(
        logs_dir.glob("session_*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )

    return json_files[0] if json_files else None


def analyze_text_log(log_path: Path) -> Dict[str, Any]:
    """Analyze a text log file.

    Args:
        log_path: Path to log file

    Returns:
        Analysis results
    """
    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    analysis = {
        "file": str(log_path),
        "total_lines": len(lines),
        "errors": [],
        "warnings": [],
        "commands": [],
        "api_calls": [],
        "last_lines": []
    }

    for i, line in enumerate(lines):
        # Look for errors
        if "[ERROR]" in line or "ERROR:" in line or "Error:" in line:
            context = {
                "line_num": i + 1,
                "line": line.strip(),
                "context": lines[max(0, i-2):min(len(lines), i+3)]
            }
            analysis["errors"].append(context)

        # Look for warnings
        elif "[WARNING]" in line or "WARNING:" in line:
            analysis["warnings"].append({
                "line_num": i + 1,
                "line": line.strip()
            })

        # Look for commands
        elif "COMMAND:" in line:
            analysis["commands"].append({
                "line_num": i + 1,
                "line": line.strip()
            })

        # Look for API calls
        elif "API CALL:" in line:
            analysis["api_calls"].append({
                "line_num": i + 1,
                "line": line.strip()
            })

    # Get last 50 lines for context
    analysis["last_lines"] = [l.rstrip() for l in lines[-50:]]

    return analysis


def analyze_json_log(json_path: Path) -> Dict[str, Any]:
    """Analyze a JSON log file.

    Args:
        json_path: Path to JSON log file

    Returns:
        Analysis results
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        events = json.load(f)

    analysis = {
        "file": str(json_path),
        "total_events": len(events),
        "errors": [],
        "commands": [],
        "api_calls": [],
        "session_info": None
    }

    for event in events:
        event_type = event.get("type")
        data = event.get("data", {})

        if event_type == "session_start":
            analysis["session_info"] = data

        elif event_type == "error":
            analysis["errors"].append({
                "timestamp": data.get("timestamp"),
                "context": data.get("context"),
                "error": data.get("error"),
                "traceback": data.get("traceback", "").split('\n')[-5:]  # Last 5 lines
            })

        elif event_type == "command":
            analysis["commands"].append({
                "timestamp": data.get("timestamp"),
                "command": data.get("command"),
                "args": data.get("args"),
                "error": data.get("error")
            })

        elif event_type == "api_call":
            analysis["api_calls"].append({
                "timestamp": data.get("timestamp"),
                "model": data.get("model"),
                "tokens": data.get("tokens"),
                "error": data.get("error")
            })

    return analysis


def print_analysis(analysis: Dict[str, Any], format: str = "summary"):
    """Print analysis results.

    Args:
        analysis: Analysis results
        format: Output format (summary, full, errors)
    """
    print(f"\n=== Log Analysis: {Path(analysis['file']).name} ===\n")

    if format == "errors" or format == "full":
        if analysis["errors"]:
            print(f"ERRORS FOUND: {len(analysis['errors'])}")
            print("-" * 50)
            for error in analysis["errors"]:
                if isinstance(error, dict) and "line_num" in error:
                    print(f"Line {error['line_num']}: {error['line']}")
                    if "context" in error and format == "full":
                        print("Context:")
                        for ctx_line in error["context"]:
                            print(f"  {ctx_line.rstrip()}")
                else:
                    # JSON error format
                    print(f"Time: {error.get('timestamp', 'N/A')}")
                    print(f"Context: {error.get('context', 'N/A')}")
                    print(f"Error: {error.get('error', 'N/A')}")
                    if format == "full" and error.get('traceback'):
                        print("Traceback (last 5 lines):")
                        for line in error['traceback']:
                            print(f"  {line}")
                print()
        else:
            print("No errors found")
        print()

    if format == "summary" or format == "full":
        # Summary statistics
        print("SUMMARY:")
        print(f"  Total lines/events: {analysis.get('total_lines', analysis.get('total_events', 0))}")
        print(f"  Errors: {len(analysis.get('errors', []))}")
        print(f"  Warnings: {len(analysis.get('warnings', []))}")
        print(f"  Commands executed: {len(analysis.get('commands', []))}")
        print(f"  API calls: {len(analysis.get('api_calls', []))}")
        print()

        # Recent commands
        if analysis.get("commands"):
            print("RECENT COMMANDS:")
            for cmd in analysis["commands"][-5:]:
                if isinstance(cmd, dict) and "line" in cmd:
                    print(f"  {cmd['line']}")
                else:
                    print(f"  /{cmd.get('command', '')} {cmd.get('args', '')}")
            print()

        # Last lines for context (text log only)
        if analysis.get("last_lines") and format == "full":
            print("LAST 20 LINES:")
            print("-" * 50)
            for line in analysis["last_lines"][-20:]:
                print(line)


def main():
    """Main entry point for log analysis."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze AgenticAuthor session logs")
    parser.add_argument(
        "log_file",
        nargs="?",
        help="Specific log file to analyze (default: latest)"
    )
    parser.add_argument(
        "--format",
        choices=["summary", "full", "errors"],
        default="summary",
        help="Output format"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Analyze JSON log instead of text log"
    )
    parser.add_argument(
        "--logs-dir",
        default=".agentic/logs",
        help="Logs directory (default: .agentic/logs)"
    )

    args = parser.parse_args()

    logs_dir = Path(args.logs_dir)

    # Get log file
    if args.log_file:
        log_path = Path(args.log_file)
    else:
        if args.json:
            log_path = get_latest_json_log(logs_dir)
        else:
            log_path = get_latest_log(logs_dir)

    if not log_path or not log_path.exists():
        print("No log file found")
        sys.exit(1)

    # Analyze
    if log_path.suffix == ".json" or args.json:
        analysis = analyze_json_log(log_path)
    else:
        analysis = analyze_text_log(log_path)

    # Print results
    print_analysis(analysis, args.format)


if __name__ == "__main__":
    main()