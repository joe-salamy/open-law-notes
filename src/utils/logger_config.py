"""
Centralized logging configuration for the law school note generator.
Creates log files with timestamps for each run and provides formatted console output.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(log_dir: Path = None) -> logging.Logger:
    """
    Setup logging configuration with file and console handlers.

    Creates a timestamped log file in the logs directory and configures
    console output with appropriate formatting.

    Args:
        log_dir: Directory for log files (default: project_root/logs)

    Returns:
        Configured logger instance
    """
    # Set up log directory
    if log_dir is None:
        # Default to logs folder in project root
        project_root = Path(__file__).parent.parent
        log_dir = project_root / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"law_notes_{timestamp}.log"

    # Create logger
    logger = logging.getLogger("law_school_notes")
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # File handler - detailed logging
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Console handler - user-friendly output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Log initialization
    logger.info("=" * 70)
    logger.info(f"Logging initialized - Log file: {log_file}")
    logger.info("=" * 70)

    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Name of the module (typically __name__)

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"law_school_notes.{name}")
    return logging.getLogger("law_school_notes")
