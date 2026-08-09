"""Batching utilities for translation segments."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rpg_translator.core.models import TextSegment


@dataclass(frozen=True, slots=True)
class SegmentBatch:
    """A batch of text segments to be translated together."""

    batch_index: int
    segments: tuple[TextSegment, ...]

    @property
    def segment_ids(self) -> tuple[str, ...]:
        return tuple(segment.segment_id for segment in self.segments)

    @property
    def total_chars(self) -> int:
        return sum(len(segment.source_text) for segment in self.segments)


def create_batches(
    segments: Sequence[TextSegment],
    *,
    max_segments: int = 16,
    max_chars: int = 6000,
) -> tuple[SegmentBatch, ...]:
    """Split segments into batches respecting size constraints.

    Args:
        segments: Ordered sequence of segments to batch.
        max_segments: Maximum number of segments per batch.
        max_chars: Maximum total characters per batch.

    Returns:
        Tuple of SegmentBatch objects preserving input order.
    """
    if not segments:
        return ()

    batches: list[SegmentBatch] = []
    current_batch: list[TextSegment] = []
    current_chars = 0
    batch_index = 0

    for segment in segments:
        segment_chars = len(segment.source_text)

        # Check if adding this segment would exceed limits
        if (
            current_batch
            and (
                len(current_batch) >= max_segments
                or current_chars + segment_chars > max_chars
            )
        ):
            # Finalize current batch
            batches.append(
                SegmentBatch(
                    batch_index=batch_index,
                    segments=tuple(current_batch),
                )
            )
            batch_index += 1
            current_batch = []
            current_chars = 0

        current_batch.append(segment)
        current_chars += segment_chars

    # Don't forget the last batch
    if current_batch:
        batches.append(
            SegmentBatch(
                batch_index=batch_index,
                segments=tuple(current_batch),
            )
        )

    return tuple(batches)