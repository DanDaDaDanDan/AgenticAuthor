"""Tests for logging system."""

import pytest
import logging
from pathlib import Path
from datetime import datetime

from src.utils.logging import setup_logging, get_logger


class TestLogging:
    """Test logging functionality."""

    def test_setup_logging_default(self, temp_dir):
        """Test setting up logging with default parameters."""
        log_file = temp_dir / "test.log"
        logger = setup_logging(log_file=log_file, level="INFO")

        assert logger.name == "agentic"
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.FileHandler)

    def test_setup_logging_with_console(self, temp_dir):
        """Test setting up logging with console output."""
        log_file = temp_dir / "test.log"
        logger = setup_logging(log_file=log_file, level="DEBUG", console_output=True)

        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 2

        # Should have both file and console handlers
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert 'FileHandler' in handler_types
        assert 'StreamHandler' in handler_types

    def test_log_levels(self, temp_dir):
        """Test different log levels."""
        log_file = temp_dir / "test.log"
        logger = setup_logging(log_file=log_file, level="WARNING")

        # Log different levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Read log file
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Only WARNING and ERROR should be logged
        assert "Debug message" not in content
        assert "Info message" not in content
        assert "Warning message" in content
        assert "Error message" in content

    def test_log_file_creation(self, temp_dir):
        """Test that log file is created."""
        log_file = temp_dir / "logs" / "test.log"
        assert not log_file.exists()

        logger = setup_logging(log_file=log_file)
        logger.info("Test message")

        assert log_file.exists()
        assert log_file.parent.exists()

    def test_default_log_location(self, monkeypatch, temp_dir):
        """Test default log file location."""
        # Mock home directory
        monkeypatch.setattr(Path, 'home', lambda: temp_dir)

        logger = setup_logging()
        logger.info("Test message")

        # Should create log in ~/.agentic/logs/
        timestamp = datetime.now().strftime("%Y%m%d")
        expected_log = temp_dir / ".agentic" / "logs" / f"agentic_{timestamp}.log"
        assert expected_log.exists()

    def test_log_format(self, temp_dir):
        """Test log message format."""
        log_file = temp_dir / "test.log"
        logger = setup_logging(log_file=log_file)

        logger.info("Test message")

        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check format elements
        assert "INFO" in content
        assert "Test message" in content
        assert "agentic" in content
        # Should have timestamp
        assert datetime.now().strftime("%Y-%m-%d") in content

    def test_get_logger(self):
        """Test getting logger instances."""
        # Default logger
        logger1 = get_logger()
        assert logger1.name == "agentic"

        # Named logger
        logger2 = get_logger("test_module")
        assert logger2.name == "agentic.test_module"

        # Same name should return same instance
        logger3 = get_logger("test_module")
        assert logger3 is logger2

    def test_logger_startup_message(self, temp_dir):
        """Test that startup message is logged."""
        log_file = temp_dir / "test.log"
        logger = setup_logging(log_file=log_file, level="INFO")

        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "AgenticAuthor logging started" in content
        assert "Level: INFO" in content
        assert str(log_file) in content
        assert "=" * 60 in content

    def test_unicode_handling(self, temp_dir):
        """Test handling of unicode characters in logs."""
        log_file = temp_dir / "test.log"
        logger = setup_logging(log_file=log_file)

        # Log unicode characters
        logger.info("Unicode test: 🚀 ✨ 你好")

        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "🚀" in content
        assert "✨" in content
        assert "你好" in content

    def test_exception_logging(self, temp_dir):
        """Test logging exceptions with traceback."""
        log_file = temp_dir / "test.log"
        logger = setup_logging(log_file=log_file)

        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.error("Error occurred", exc_info=True)

        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "Error occurred" in content
        assert "ValueError: Test exception" in content
        assert "Traceback" in content

    def test_multiple_setup_calls(self, temp_dir):
        """Test that multiple setup calls clear existing handlers."""
        log_file1 = temp_dir / "test1.log"
        log_file2 = temp_dir / "test2.log"

        logger = setup_logging(log_file=log_file1)
        initial_handlers = len(logger.handlers)

        # Second setup should clear handlers
        logger = setup_logging(log_file=log_file2)
        assert len(logger.handlers) == initial_handlers

        # Log should go to second file
        logger.info("Test message")
        assert log_file2.exists()

        with open(log_file2, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "Test message" in content