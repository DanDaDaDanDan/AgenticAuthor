"""Logging configuration for AgenticAuthor."""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

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
    logger.info("=" * 60)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (defaults to 'agentic')

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"agentic.{name}")
    return logging.getLogger("agentic")