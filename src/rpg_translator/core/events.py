"""Domain events for later GUI and worker integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base event emitted by services."""

    name: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass(frozen=True, slots=True)
class ProjectScanned(DomainEvent):
    """Emitted when project detection and file scanning completes."""

    name: str = "project_scanned"


@dataclass(frozen=True, slots=True)
class JobStatusChanged(DomainEvent):
    """Emitted when a resumable job changes state."""

    name: str = "job_status_changed"

