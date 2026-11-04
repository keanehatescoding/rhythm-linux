"""Write the app's log to a rotating file in the data folder, as well as to stderr."""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_NAME = "rhythm_linux"
LOG_FILE_NAME = "rhythm-linux.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3


def setup_logging(data_dir: str | Path) -> Path | None:
    """Send warnings and errors to the log file and stderr.

    Returns the log file path, or None if the file could not be opened (the app
    still runs and logs to stderr). Calling it twice does not add duplicate handlers.
    """
    logger = logging.getLogger(LOG_NAME)
    logger.setLevel(logging.INFO)
    if getattr(logger, "_rhythm_configured", False):
        return getattr(logger, "_rhythm_log_path", None)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    stderr = logging.StreamHandler(sys.stderr)
    stderr.setLevel(logging.WARNING)
    stderr.setFormatter(fmt)
    logger.addHandler(stderr)

    path = Path(data_dir) / LOG_FILE_NAME
    log_path: Path | None = path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
        handler.setLevel(logging.WARNING)
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    except OSError as exc:
        log_path = None
        logger.warning("Could not open the log file %s: %s", path, exc)

    logger._rhythm_configured = True  # type: ignore[attr-defined]
    logger._rhythm_log_path = log_path  # type: ignore[attr-defined]
    return log_path
