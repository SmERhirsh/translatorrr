"""Structured logging setup."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from rpg_translator.config.schema import LoggingSettings
from rpg_translator.core.paths import ensure_directory, user_data_dir

PACKAGE_LOGGER_NAME = "rpg_translator"

_RESERVED_LOG_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}

_SECRET_PATTERNS = (
    re.compile(r"(api[_-]?key\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(Bearer\s+)([A-Za-z0-9._\-]+)", re.IGNORECASE),
)
_SECRET_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|token|secret)", re.IGNORECASE)


def redact_secret(value: Any) -> Any:
    """Redact likely API keys/tokens from values before logging."""

    if isinstance(value, str):
        redacted = value
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub(r"\1***", redacted)
        return redacted
    if isinstance(value, dict):
        return {
            key: "***" if _SECRET_KEY_PATTERN.search(str(key)) else redact_secret(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_secret(item) for item in value]
    return value


class JsonLogFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secret(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_LOG_RECORD_ATTRS
        }
        if extras:
            payload["extra"] = redact_secret(_json_safe(extras))

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def configure_logging(
    settings: LoggingSettings,
    *,
    log_dir: Path | None = None,
) -> logging.Logger:
    """Configure the package logger.

    Repeated calls replace existing handlers to avoid duplicate GUI/CLI output.
    """

    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    logger.setLevel(settings.level)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    if settings.console_enabled:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(settings.level)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"),
        )
        logger.addHandler(console_handler)

    if settings.file_enabled:
        resolved_log_dir = ensure_directory(
            Path(settings.log_dir).expanduser()
            if settings.log_dir
            else (log_dir or user_data_dir() / "logs"),
        )
        log_path = resolved_log_dir / "rpg-maker-translator.log"
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=settings.max_bytes,
            backupCount=settings.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(settings.level)
        if settings.json_file:
            file_handler.setFormatter(JsonLogFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s [%(name)s] %(filename)s:%(lineno)d %(message)s",
                ),
            )
        logger.addHandler(file_handler)

    logging.captureWarnings(True)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a package logger or child logger."""

    return logging.getLogger(name or PACKAGE_LOGGER_NAME)
