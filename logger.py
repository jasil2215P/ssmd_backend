import json
import logging
import os
import sys
import time
from typing import Any


class _ColourFormatter(logging.Formatter):
    RESET = "\x1b[0m"
    GREY = "\x1b[38;5;240m"
    CYAN = "\x1b[36m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    RED = "\x1b[31m"
    BOLD_RED = "\x1b[1;31m"
    BLUE = "\x1b[34m"

    LEVEL_COLOURS = {
        logging.DEBUG: GREY,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        colour = self.LEVEL_COLOURS.get(record.levelno, self.RESET)
        level = f"{colour}{record.levelname:<8}{self.RESET}"
        name = f"{self.BLUE}{record.name}{self.RESET}"
        ts = f"{self.GREY}{self.formatTime(record, '%H:%M:%S')}{self.RESET}"

        msg = record.getMessage()
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)

        _std = logging.LogRecord.__dict__.keys() | {
            "message", "asctime", "args", "exc_info", "exc_text", "stack_info"
        }
        extras: dict[str, Any] = {
            k: v for k, v in record.__dict__.items() if k not in _std
        }
        extras_str = ""
        if extras:
            kv = "  ".join(f"{self.CYAN}{k}{self.RESET}={v!r}" for k, v in extras.items())
            extras_str = f"  {kv}"

        return f"{ts}  {level}  {name}  {msg}{extras_str}"


class _JsonFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        _std = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        for k, v in record.__dict__.items():
            if k not in _std:
                payload[k] = v
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    environment = os.getenv("ENVIRONMENT", "development")
    is_production = environment == "production"
    level = logging.WARNING if is_production else logging.DEBUG

    root = logging.getLogger()
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    if is_production:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(_ColourFormatter())

    root.setLevel(level)
    root.addHandler(handler)

    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("uvicorn.error").setLevel(logging.WARNING if is_production else logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class Timer:

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1_000

    @property
    def ms(self) -> float:
        return getattr(self, "elapsed_ms", 0.0)
