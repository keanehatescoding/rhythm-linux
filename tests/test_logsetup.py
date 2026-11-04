"""The log file is written to the data folder, once, and a failure does not stop startup."""
import logging

import pytest

from rhythm_linux import logsetup


@pytest.fixture(autouse=True)
def reset_logger():
    logger = logging.getLogger(logsetup.LOG_NAME)
    yield
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    for attr in ("_rhythm_configured", "_rhythm_log_path"):
        if hasattr(logger, attr):
            delattr(logger, attr)


def test_errors_are_written_to_the_log_file(tmp_path):
    path = logsetup.setup_logging(tmp_path / "data")

    logging.getLogger("rhythm_linux.test").error("something broke")
    for handler in logging.getLogger(logsetup.LOG_NAME).handlers:
        handler.flush()

    assert path == tmp_path / "data" / logsetup.LOG_FILE_NAME
    assert "something broke" in path.read_text(encoding="utf-8")


def test_setup_twice_adds_handlers_once(tmp_path):
    logsetup.setup_logging(tmp_path)
    count = len(logging.getLogger(logsetup.LOG_NAME).handlers)

    logsetup.setup_logging(tmp_path)

    assert len(logging.getLogger(logsetup.LOG_NAME).handlers) == count


def test_unwritable_folder_returns_none_and_does_not_raise(tmp_path):
    blocker = tmp_path / "file-not-folder"
    blocker.write_text("x", encoding="utf-8")

    assert logsetup.setup_logging(blocker / "data") is None
