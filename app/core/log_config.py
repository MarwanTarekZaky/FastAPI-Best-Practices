import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# logs/ folder in the project root
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"


def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)

    # A new file starts at 1 MB, keeping the last 3: requests.log.1, .2, .3
    file_handler = RotatingFileHandler(
        LOG_DIR / "requests.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )

    logger = logging.getLogger("fastship.requests")
    logger.setLevel(logging.INFO)
    # Don't add a second handler if this runs twice
    if not logger.handlers:
        logger.addHandler(file_handler)
    # Uvicorn already prints each request in the terminal, keep this one in the file
    logger.propagate = False
