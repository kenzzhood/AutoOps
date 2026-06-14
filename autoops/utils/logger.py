"""Rich console logging with file tee to ~/.autoops/logs/autoops.log."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from autoops.utils.file_utils import ensure_data_dir

_console = Console()
_logger: logging.Logger | None = None


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure logging to Rich console and autoops.log file."""
    global _logger
    if _logger is not None:
        return _logger

    data_dir = ensure_data_dir()
    log_path = data_dir / "logs" / "autoops.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("autoops")
    logger.setLevel(level)
    logger.handlers.clear()

    rich_handler = RichHandler(
        console=_console,
        show_time=True,
        show_path=False,
        markup=True,
    )
    rich_handler.setLevel(level)
    logger.addHandler(rich_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(file_handler)

    _logger = logger
    return logger


def get_logger(name: str = "autoops") -> logging.Logger:
    """Return configured logger, setting up if needed."""
    setup_logging()
    return logging.getLogger(name)


def get_console() -> Console:
    """Return shared Rich console."""
    return _console
