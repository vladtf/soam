import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from contextvars import ContextVar

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
    if getattr(setup_logging, "_configured", False):
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(threadName)s - %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S%z"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
    req_filter = RequestIdFilter()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(req_filter)
    root.addHandler(console)

    if log_file:
        file_handler = TimedRotatingFileHandler(log_file, when="midnight", backupCount=7, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(req_filter)
        root.addHandler(file_handler)

    noisy_level = os.getenv("NOISY_LOG_LEVEL", "WARNING").upper()
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "urllib3", "botocore", "minio", "paho"):
        logging.getLogger(name).setLevel(getattr(logging, noisy_level, logging.WARNING))

    setup_logging._configured = True  # type: ignore[attr-defined]
