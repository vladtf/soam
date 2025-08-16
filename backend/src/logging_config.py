import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from contextvars import ContextVar
import colorlog

# Context variable for per-request correlation
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.request_id = _request_id_var.get()
        except Exception:
            record.request_id = "-"
        return True


def set_request_id(req_id: str | None) -> None:
    _request_id_var.set(req_id or "-")


def setup_logging(service_name: str, log_file: str | None = None) -> None:
    """Configure root logging once with console + rotating file handlers.

    Respects LOG_LEVEL env (default INFO). Adds request_id to each record.
    Uses colored console output for better readability.
    """
    if getattr(setup_logging, "_configured", False):
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers to avoid duplicates in reloads
    for h in list(root.handlers):
        root.removeHandler(h)

    # Define log format
    log_format = "%(log_color)s%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(threadName)s - %(message)s%(reset)s"
    datefmt = "%Y-%m-%dT%H:%M:%S%z"
    
    # Create colored formatter for console
    console_formatter = colorlog.ColoredFormatter(
        log_format,
        datefmt=datefmt,
        log_colors={
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
            'DEBUG': 'cyan',
        }
    )
    
    # Create regular formatter for file (no colors)
    file_format = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(threadName)s - %(message)s"
    file_formatter = logging.Formatter(fmt=file_format, datefmt=datefmt)
    
    req_filter = RequestIdFilter()

    # Console handler with colors
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(console_formatter)
    console.addFilter(req_filter)
    root.addHandler(console)

    # File handler without colors
    if log_file:
        file_handler = TimedRotatingFileHandler(log_file, when="midnight", backupCount=7, encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(req_filter)
        root.addHandler(file_handler)

    # Tame noisy third-party loggers
    noisy_level = os.getenv("NOISY_LOG_LEVEL", "WARNING").upper()
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "urllib3", "botocore", "minio"):
        logging.getLogger(name).setLevel(getattr(logging, noisy_level, logging.WARNING))

    setup_logging._configured = True  # type: ignore[attr-defined]
