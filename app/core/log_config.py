import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import app_settings

# logs/ folder in the project root
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"

FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging():
    # Docker and hosting sites like Render collect what an app prints to the
    # terminal (stdout), that's where logs belong in a container
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(FORMAT))

    # "app" is the parent of every module logger in app/, like
    # app.services.notification, so they all print with the same format
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    # Don't add a second handler if this runs twice
    if not app_logger.handlers:
        app_logger.addHandler(console)
    app_logger.propagate = False

    requests_logger = logging.getLogger("fastship.requests")
    requests_logger.setLevel(logging.INFO)
    requests_logger.propagate = False
    if requests_logger.handlers:
        return

    if app_settings.ENVIRONMENT == "production":
        # A file inside a container is lost on every restart, print instead
        requests_logger.addHandler(console)
        return

    # On your machine: uvicorn already prints each request in the terminal,
    # keep these in a file. A new file starts at 1 MB, keeping the last 3
    LOG_DIR.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_DIR / "requests.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(FORMAT))
    requests_logger.addHandler(file_handler)
