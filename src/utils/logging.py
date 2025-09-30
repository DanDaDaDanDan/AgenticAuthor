"""Logging configuration for AgenticAuthor."""

import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import json
import os

def cleanup_old_logs(log_dir: Path = None, days_to_keep: int = 1) -> int:
    """
    Clean up log files older than specified days.

    Args:
        log_dir: Directory containing logs (defaults to ~/.agentic/logs)
        days_to_keep: Number of days to keep logs (default 1)

    Returns:
        Number of files deleted
    """
    if log_dir is None:
        log_dir = Path.home() / ".agentic" / "logs"

    if not log_dir.exists():
        return 0

    cutoff_time = datetime.now() - timedelta(days=days_to_keep)
    files_deleted = 0

    # Clean up both .log and .json files
    for pattern in ["*.log", "*.json"]:
        for log_file in log_dir.glob(pattern):
            try:
                # Get file modification time
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

                # Delete if older than cutoff
                if file_mtime < cutoff_time:
                    log_file.unlink()
                    files_deleted += 1
            except Exception:
                # Silently ignore errors for individual files
                pass

    return files_deleted


def cleanup_test_artifacts(project_root: Path = None, days_to_keep: int = 1) -> int:
    """
    Clean up test screenshots and debug files older than specified days.

    Args:
        project_root: Project root directory (defaults to current working directory)
        days_to_keep: Number of days to keep test artifacts (default 1)

    Returns:
        Number of files deleted
    """
    if project_root is None:
        project_root = Path.cwd()

    files_deleted = 0
    cutoff_time = datetime.now() - timedelta(days=days_to_keep)

    # Clean up test screenshots
    screenshots_dir = project_root / "tests" / "screenshots"
    if screenshots_dir.exists():
        for screenshot in screenshots_dir.glob("*.png"):
            try:
                file_mtime = datetime.fromtimestamp(screenshot.stat().st_mtime)
                if file_mtime < cutoff_time:
                    screenshot.unlink()
                    files_deleted += 1
            except Exception:
                pass

    # Clean up test baseline files
    baselines_dir = project_root / "tests" / "baselines"
    if baselines_dir.exists():
        for baseline in baselines_dir.glob("*.json"):
            try:
                file_mtime = datetime.fromtimestamp(baseline.stat().st_mtime)
                if file_mtime < cutoff_time:
                    baseline.unlink()
                    files_deleted += 1
            except Exception:
                pass

    # Clean up root-level test files
    for pattern in ["test_*.py", "*_tui.py"]:
        for test_file in project_root.glob(pattern):
            try:
                file_mtime = datetime.fromtimestamp(test_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    test_file.unlink()
                    files_deleted += 1
            except Exception:
                pass

    # Clean up TUI development files
    tui_files = [
        project_root / "src" / "api" / "streaming_tui.py",
        project_root / "src" / "cli" / "agentic_tui.py"
    ]
    for tui_file in tui_files:
        if tui_file.exists():
            try:
                file_mtime = datetime.fromtimestamp(tui_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    tui_file.unlink()
                    files_deleted += 1
            except Exception:
                pass

    return files_deleted


def setup_logging(
    log_file: Optional[Path] = None,
    level: str = "INFO",
    console_output: bool = False
) -> logging.Logger:
    """
    Setup logging configuration.

    Args:
        log_file: Path to log file (defaults to .agentic/logs/agentic.log)
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        console_output: Whether to also output to console

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("agentic")
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Setup log file
    if log_file is None:
        log_dir = Path.home() / ".agentic" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Clean up old logs at startup
        files_deleted = cleanup_old_logs(log_dir, days_to_keep=1)

        # Also clean up test artifacts
        test_files_deleted = cleanup_test_artifacts(days_to_keep=1)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = log_dir / f"agentic_{timestamp}.log"

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # File handler with detailed format
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Console handler if requested (simpler format)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_format = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

    # Log startup
    logger.info("=" * 60)
    logger.info(f"AgenticAuthor logging started - Level: {level}")
    logger.info(f"Log file: {log_file}")
    if 'files_deleted' in locals() and files_deleted > 0:
        logger.info(f"Cleaned up {files_deleted} old log files")
    if 'test_files_deleted' in locals() and test_files_deleted > 0:
        logger.info(f"Cleaned up {test_files_deleted} test artifacts")
    logger.info("=" * 60)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance. If the logger hasn't been set up yet, sets it up with default configuration.

    Args:
        name: Logger name (defaults to 'agentic')

    Returns:
        Logger instance
    """
    logger_name = f"agentic.{name}" if name else "agentic"
    logger = logging.getLogger(logger_name)

    # If the root logger has no handlers, it hasn't been set up yet
    root_logger = logging.getLogger("agentic")
    if not root_logger.handlers:
        # Auto-setup with default configuration
        setup_logging(level="DEBUG")

    return logger