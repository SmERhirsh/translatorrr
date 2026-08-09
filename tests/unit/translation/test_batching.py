"""Unit tests for translation batching."""

from __future__ import annotations

import pytest

from rpg_translator.core.models import JsonPointer, RPGMakerFileKind, SegmentContext, TextSegment
from rpg_translator.translation.batching import SegmentBatch, create_batches


class TestCreateBatches:
    """Tests for the create_batches function."""

    def test_empty_segments(self) -> None:
        """Empty input produces empty output."""
        batches = create_batches(())
        assert batches == ()

    def test_single_segment(self) -> None:
        """Single segment creates single batch."""
        segments = (
            TextSegment(
                segment_id="seg_1",
                source_text="Hello",
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            ),
        )
        batches = create_batches(segments)
        assert len(batches) == 1
        assert batches[0].batch_index == 0
        assert batches[0].segment_ids == ("seg_1",)

    def test_multiple_segments_within_limit(self) -> None:
        """Multiple small segments fit in one batch."""
        segments = tuple(
            TextSegment(
                segment_id=f"seg_{i}",
                source_text=f"Text {i}",
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            )
            for i in range(5)
        )
        batches = create_batches(segments, max_segments=10, max_chars=1000)
        assert len(batches) == 1
        assert batches[0].batch_index == 0
        assert len(batches[0].segments) == 5

    def test_max_segments_limit(self) -> None:
        """Batches respect max_segments limit."""
        segments = tuple(
            TextSegment(
                segment_id=f"seg_{i}",
                source_text=f"Text {i}",
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            )
            for i in range(20)
        )
        batches = create_batches(segments, max_segments=6, max_chars=10000)
        assert len(batches) == 4  # 20 / 6 = 3 full + 1 partial
        assert batches[0].batch_index == 0
        assert len(batches[0].segments) == 6
        assert batches[1].batch_index == 1
        assert len(batches[1].segments) == 6
        assert batches[2].batch_index == 2
        assert len(batches[2].segments) == 6
        assert batches[3].batch_index == 3
        assert len(batches[3].segments) == 2

    def test_max_chars_limit(self) -> None:
        """Batches respect max_chars limit."""
        # Each segment is 100 chars
        segments = tuple(
            TextSegment(
                segment_id=f"seg_{i}",
                source_text="x" * 100,
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            )
            for i in range(10)
        )
        # Max 250 chars per batch = 2 segments + part of 3rd
        batches = create_batches(segments, max_segments=100, max_chars=250)
        assert len(batches) >= 4  # At least 4 batches needed
        # First batch should have 2 segments (200 chars)
        assert batches[0].total_chars <= 250
        assert len(batches[0].segments) == 2

    def test_order_preserved(self) -> None:
        """Segment order is preserved across batches."""
        segments = tuple(
            TextSegment(
                segment_id=f"seg_{i:03d}",
                source_text=f"Text {i}",
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            )
            for i in range(10)
        )
        batches = create_batches(segments, max_segments=3)
        all_ids = []
        for batch in batches:
            all_ids.extend(batch.segment_ids)
        expected_ids = [f"seg_{i:03d}" for i in range(10)]
        assert all_ids == expected_ids

    def test_partial_final_batch(self) -> None:
        """Last batch can be smaller than max."""
        segments = tuple(
            TextSegment(
                segment_id=f"seg_{i}",
                source_text=f"Text {i}",
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            )
            for i in range(7)
        )
        batches = create_batches(segments, max_segments=3)
        assert len(batches) == 3
        assert len(batches[0].segments) == 3
        assert len(batches[1].segments) == 3
        assert len(batches[2].segments) == 1  # Partial final batch


class TestSegmentBatch:
    """Tests for the SegmentBatch dataclass."""

    def test_segment_ids_property(self) -> None:
        """segment_ids returns correct tuple."""
        segments = tuple(
            TextSegment(
                segment_id=f"seg_{i}",
                source_text=f"Text {i}",
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            )
            for i in range(3)
        )
        batch = SegmentBatch(batch_index=0, segments=segments)
        assert batch.segment_ids == ("seg_0", "seg_1", "seg_2")

    def test_total_chars_property(self) -> None:
        """total_chars sums correctly."""
        segments = (
            TextSegment(
                segment_id="seg_1",
                source_text="abc",  # 3 chars
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            ),
            TextSegment(
                segment_id="seg_2",
                source_text="defgh",  # 5 chars
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            ),
        )
        batch = SegmentBatch(batch_index=0, segments=segments)
        assert batch.total_chars == 8
