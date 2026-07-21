"""
Logging utilities — rotating file handler and excepthook.

18_Boot_Sequence.md §2 Step 3.
21_System_Contracts.md §8.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

_LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024
_LOG_FILE_BACKUP_COUNT: int = 30


def setup_logging(log_dir: Path, log_level: str = "INFO") -> logging.Logger:
    """Configure rotating file handler and stdout console handler.

    Parameters
    ----------
    log_dir : Path
        Directory for log files (created if absent).
    log_level : str
        Root logger level (e.g. ``"INFO"``, ``"DEBUG"``).

    Returns
    -------
    logging.Logger
        The ``naira`` application logger.
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    fmt = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "naira.log",
        maxBytes=_LOG_FILE_MAX_BYTES,
        backupCount=_LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logger = logging.getLogger("naira")
    logger.info("Logger initialised — log directory: %s", log_dir)
    return logger


def install_excepthook(logger: logging.Logger) -> None:
    """Route uncaught exceptions through the logger.

    18_Boot_Sequence.md §2 Step 3(4).
    """

    def excepthook(
        exc_type: type[BaseException], exc_value: BaseException, traceback: object
    ) -> None:
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, traceback))

    sys.excepthook = excepthook
