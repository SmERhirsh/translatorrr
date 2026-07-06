"""Application logging helpers."""

from __future__ import annotations

import logging as std_logging

from rpg_translator.logging.setup import JsonLogFormatter, configure_logging, get_logger, redact_secret

std_logging.getLogger("rpg_translator").addHandler(std_logging.NullHandler())

__all__ = [
    "JsonLogFormatter",
    "configure_logging",
    "get_logger",
    "redact_secret",
]

