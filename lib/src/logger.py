import logging
import sys
from pathlib import Path

_PROJECT_LOG_DIR = None
_FILE_HANDLER = None


def set_project_log_dir(path):
    global _PROJECT_LOG_DIR, _FILE_HANDLER
    _PROJECT_LOG_DIR = Path(path)
    _PROJECT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_path = _PROJECT_LOG_DIR / "project.log"
    _FILE_HANDLER = logging.FileHandler(log_path, encoding="utf-8")
    _FILE_HANDLER.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )

    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger, logging.Logger) and not any(
            isinstance(handler, logging.FileHandler) and handler.baseFilename == str(log_path)
            for handler in logger.handlers
        ):
            logger.addHandler(_FILE_HANDLER)


def clear_project_log_dir():
    if _PROJECT_LOG_DIR and _PROJECT_LOG_DIR.exists():
        for item in _PROJECT_LOG_DIR.glob("*.log"):
            try:
                item.unlink()
            except OSError:
                pass


def get_logger(name="video_agent"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        logger.addHandler(handler)

    if _FILE_HANDLER and _FILE_HANDLER not in logger.handlers:
        logger.addHandler(_FILE_HANDLER)

    return logger

