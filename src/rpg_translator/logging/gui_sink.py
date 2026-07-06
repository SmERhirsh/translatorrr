"""Future GUI log sink primitives."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class GuiLogMessage:
    """Plain record that can be bridged to Qt signals in the GUI phase."""

    timestamp: datetime
    level: str
    logger: str
    message: str


class BufferedGuiLogHandler(logging.Handler):
    """Small in-memory handler useful before the Qt log view exists."""

    def __init__(self, capacity: int = 1000) -> None:
        super().__init__()
        self._messages: deque[GuiLogMessage] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        self._messages.append(
            GuiLogMessage(
                timestamp=datetime.fromtimestamp(record.created, tz=UTC),
                level=record.levelname,
                logger=record.name,
                message=record.getMessage(),
            ),
        )

    def messages(self) -> tuple[GuiLogMessage, ...]:
        return tuple(self._messages)

