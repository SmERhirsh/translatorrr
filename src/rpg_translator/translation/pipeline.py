"""Translation pipeline for RPG Maker projects."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rpg_translator.config.schema import AppConfig
from rpg_translator.core.errors import (
    InvalidTranslationError,
    OutputWriteError,
    PlaceholderMismatchError,
    ProviderConnectionError,
)
from rpg_translator.core.models import (
    GameProject,
    JobProgress,
    JobStatus,
    ProjectFile,
    ProtectedToken,
    RPGMakerFileKind,
    SegmentStatus,
    TextSegment,
    TranslationJob,
)
from rpg_translator.providers.base import ChatProvider
from rpg_translator.rpgmaker.extractors.registry import extract_project
from rpg_translator.rpgmaker.json_loader import load_project_data_files
from rpg_translator.translation.batching import SegmentBatch, create_batches
from rpg_translator.translation.placeholderizer import (
    protect_text,
    restore_placeholders,
    validate_control_codes_preserved,
)
from rpg_translator.translation.prompt_builder import (
    build_translation_prompt,
    parse_translation_response,
)


@dataclass(frozen=True, slots=True)
class BatchResult:
    """Result of translating a single batch."""

    batch_index: int
    segment_ids: tuple[str, ...]
    translations: dict[str, str] | None = None
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    finished_at: datetime | None = None


@dataclass(slots=True)
class CheckpointState:
    """Persistent checkpoint state for resume capability."""

    job_id: str
    project_root: str
    source_language: str
    target_language: str
    config_hash: str
    total_segments: int
    completed_segment_ids: set[str]
    translated_segments: dict[str, str]
    status: str
    created_at: str
    updated_at: str
    schema_version: str = "1.0"

    @classmethod
    def from_job(cls, job: TranslationJob, translated: dict[str, str], completed_ids: set[str]) -> "CheckpointState":
        return cls(
            job_id=job.job_id,
            project_root=str(job.project_root),
            source_language=job.source_language,
            target_language=job.target_language,
            config_hash=job.config_hash or "",
            total_segments=job.progress.total_segments,
            completed_segment_ids=completed_ids,
            translated_segments=translated,
            status=job.status.value,
            created_at=job.created_at.isoformat(),
            updated_at=datetime.now(tz=UTC).isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "job_id": self.job_id,
            "project_root": self.project_root,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "config_hash": self.config_hash,
            "total_segments": self.total_segments,
            "completed_segment_ids": list(self.completed_segment_ids),
            "translated_segments": self.translated_segments,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointState":
        # schema_version is required - missing means incompatible checkpoint
        if "schema_version" not in data:
            raise ValueError(
                "Checkpoint file missing required 'schema_version' field. "
                "The checkpoint may be corrupted or from an incompatible version."
            )
        
        schema_version = data["schema_version"]
        if schema_version != "1.0":
            raise ValueError(
                f"Unsupported checkpoint schema version: {schema_version!r}. "
                f"Expected '1.0'. The checkpoint file may be from an incompatible version."
            )
        
        return cls(
            schema_version=schema_version,
            job_id=data["job_id"],
            project_root=data["project_root"],
            source_language=data["source_language"],
            target_language=data["target_language"],
            config_hash=data.get("config_hash", ""),
            total_segments=data["total_segments"],
            completed_segment_ids=set(data.get("completed_segment_ids", [])),
            translated_segments=dict(data.get("translated_segments", {})),
            status=data["status"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


class TranslationPipeline:
    """Coordinates the end-to-end translation process."""

    def __init__(
        self,
        config: AppConfig,
        provider: ChatProvider,
        checkpoint_dir: Path | None = None,
    ) -> None:
        self._config = config
        self._provider = provider
        self._checkpoint_dir = checkpoint_dir
        self._current_progress: JobProgress | None = None
        self._batch_results: list[BatchResult] = []

    @property
    def progress(self) -> JobProgress | None:
        """Current translation progress."""
        return self._current_progress

    @property
    def batch_results(self) -> list[BatchResult]:
        """Results of all processed batches."""
        return self._batch_results

    def translate_segments(
        self,
        segments: tuple[TextSegment, ...],
        *,
        job: TranslationJob | None = None,
    ) -> tuple[TextSegment, ...]:
        """Translate extracted text segments.

        Args:
            segments: Segments to translate (in order).
            job: Optional translation job for tracking.

        Returns:
            Tuple of translated segments in the same order.
        """
        if not segments:
            return ()

        # Initialize progress tracking
        self._current_progress = JobProgress(
            total_segments=len(segments),
            pending_segments=len(segments),
        )

        # Load checkpoint if available
        completed_ids: set[str] = set()
        translated_map: dict[str, str] = {}
        if job and self._checkpoint_dir:
            checkpoint_path = self._checkpoint_dir / f"{job.job_id}.json"
            if checkpoint_path.exists():
                checkpoint = self._load_checkpoint(checkpoint_path)
                completed_ids = checkpoint.completed_segment_ids
                translated_map = checkpoint.translated_segments

        # Filter out already completed segments
        remaining_segments = tuple(
            seg for seg in segments if seg.segment_id not in completed_ids
        )

        # Protect placeholders in remaining segments
        protected_segments = []
        for segment in remaining_segments:
            protected = protect_text(segment.source_text)
            protected_segment = TextSegment(
                segment_id=segment.segment_id,
                source_text=protected.protected_text,
                source_file=segment.source_file,
                context=segment.context,
                status=SegmentStatus.PENDING,
                protected_tokens=protected.tokens,
                source_hash=segment.source_hash,
                metadata=segment.metadata,
            )
            protected_segments.append(protected_segment)

        # Create batches
        batches = create_batches(
            protected_segments,
            max_segments=self._config.translation.batch_max_segments,
            max_chars=self._config.translation.batch_max_chars,
        )

        # Translate each batch
        all_translations: dict[str, str] = {}
        for batch in batches:
            result = self._translate_batch(batch, job)
            self._batch_results.append(result)

            if result.error:
                # Mark failed segments
                for seg_id in batch.segment_ids:
                    all_translations[seg_id] = None  # type: ignore[assignment]
            else:
                # Merge translations
                for seg_id, translation in result.translations.items():
                    all_translations[seg_id] = translation
                    completed_ids.add(seg_id)
                    translated_map[seg_id] = translation

                # Save checkpoint after successful batch
                if job and self._checkpoint_dir:
                    self._save_checkpoint(job, translated_map, completed_ids)

        # Update progress
        if self._current_progress:
            self._current_progress = JobProgress(
                total_segments=len(segments),
                pending_segments=len(segments) - len(completed_ids),
                translated_segments=len(completed_ids),
                failed_segments=len(segments) - len(completed_ids) - len(all_translations),
            )

        # Build final translated segments
        result_segments: list[TextSegment] = []
        for segment in segments:
            translation = translated_map.get(segment.segment_id)
            if translation:
                # Restore placeholders
                try:
                    restored = restore_placeholders(translation, segment.protected_tokens, strict=True)
                    # Validate control codes preserved
                    issues = validate_control_codes_preserved(segment.source_text, restored)
                    if issues:
                        raise PlaceholderMismatchError(
                            "Control codes not preserved",
                            details={"issues": [issue.message for issue in issues]},
                        )
                    result_segments.append(
                        TextSegment(
                            segment_id=segment.segment_id,
                            source_text=segment.source_text,
                            source_file=segment.source_file,
                            context=segment.context,
                            status=SegmentStatus.TRANSLATED,
                            translation=restored,
                            protected_tokens=segment.protected_tokens,
                            source_hash=segment.source_hash,
                            metadata=segment.metadata,
                        )
                    )
                except PlaceholderMismatchError as exc:
                    result_segments.append(
                        TextSegment(
                            segment_id=segment.segment_id,
                            source_text=segment.source_text,
                            source_file=segment.source_file,
                            context=segment.context,
                            status=SegmentStatus.FAILED,
                            translation=None,
                            protected_tokens=segment.protected_tokens,
                            source_hash=segment.source_hash,
                            metadata={**segment.metadata, "error": str(exc)},
                        )
                    )
            elif segment.segment_id in completed_ids:
                # Already translated from checkpoint
                result_segments.append(
                    TextSegment(
                        segment_id=segment.segment_id,
                        source_text=segment.source_text,
                        source_file=segment.source_file,
                        context=segment.context,
                        status=SegmentStatus.TRANSLATED,
                        translation=translated_map[segment.segment_id],
                        protected_tokens=segment.protected_tokens,
                        source_hash=segment.source_hash,
                        metadata=segment.metadata,
                    )
                )
            else:
                # Not translated
                result_segments.append(segment)

        return tuple(result_segments)

    def _translate_batch(self, batch: SegmentBatch, job: TranslationJob | None) -> BatchResult:
        """Translate a single batch of segments."""
        result = BatchResult(
            batch_index=batch.batch_index,
            segment_ids=batch.segment_ids,
        )

        try:
            # Build prompt
            prompt = build_translation_prompt(
                batch.segments,
                self._config.source_language,
                self._config.target_language,
            )

            # Create request
            profile = self._config.active_provider_profile
            request = prompt.to_chat_request(
                model=profile.model,
                temperature=profile.temperature,
                top_p=profile.top_p,
                max_tokens=profile.max_tokens,
            )

            # Call provider
            response = self._provider.chat(request)

            # Parse and validate response
            translations = parse_translation_response(response.content, batch.segment_ids)

            # Validate placeholder integrity for each translation
            for seg_id, translation in translations.items():
                segment = next(s for s in batch.segments if s.segment_id == seg_id)
                issues = validate_control_codes_preserved(
                    segment.source_text,
                    translation,
                )
                if issues:
                    raise PlaceholderMismatchError(
                        "Placeholder validation failed",
                        details={"segment_id": seg_id, "issues": [issue.message for issue in issues]},
                    )

            return BatchResult(
                batch_index=batch.batch_index,
                segment_ids=batch.segment_ids,
                translations=translations,
                started_at=result.started_at,
                finished_at=datetime.now(tz=UTC),
            )

        except (ValueError, PlaceholderMismatchError) as exc:
            return BatchResult(
                batch_index=batch.batch_index,
                segment_ids=batch.segment_ids,
                error=str(exc),
                started_at=result.started_at,
                finished_at=datetime.now(tz=UTC),
            )
        except ProviderConnectionError as exc:
            return BatchResult(
                batch_index=batch.batch_index,
                segment_ids=batch.segment_ids,
                error=f"Provider error: {exc}",
                started_at=result.started_at,
                finished_at=datetime.now(tz=UTC),
            )

    def _save_checkpoint(self, job: TranslationJob, translated: dict[str, str], completed_ids: set[str]) -> None:
        """Save checkpoint atomically."""
        if not self._checkpoint_dir:
            return

        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = self._checkpoint_dir / f"{job.job_id}.json"
        temp_path = checkpoint_path.with_suffix(".json.tmp")

        checkpoint = CheckpointState.from_job(job, translated, completed_ids)
        temp_path.write_text(json.dumps(checkpoint.to_dict(), indent=2), encoding="utf-8")
        temp_path.replace(checkpoint_path)

    def _load_checkpoint(self, path: Path) -> CheckpointState:
        """Load checkpoint from file with schema version validation."""
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        return CheckpointState.from_dict(data)


def translate_project(
    project: GameProject,
    config: AppConfig,
    provider: ChatProvider,
    output_dir: Path,
    checkpoint_dir: Path | None = None,
) -> tuple[TranslationJob, tuple[TextSegment, ...]]:
    """Translate an entire RPG Maker project.

    Args:
        project: Detected game project.
        config: Application configuration.
        provider: Translation provider.
        output_dir: Directory for translated output.
        checkpoint_dir: Optional directory for checkpoints.

    Returns:
        Tuple of (job, translated_segments).
    """
    from rpg_translator.output.writer import write_translated_project

    # Create job
    job = TranslationJob(
        job_id=f"job_{project.title}_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}",
        project_root=project.root_path,
        source_language=config.source_language,
        target_language=config.target_language,
        status=JobStatus.RUNNING,
        config_hash=config.stable_hash,
    )

    # Extract segments
    extraction_result = extract_project(project)
    segments = extraction_result.segments

    # Translate
    pipeline = TranslationPipeline(config, provider, checkpoint_dir)
    translated_segments = pipeline.translate_segments(segments, job=job)

    # Write output
    write_translated_project(
        project=project,
        translated_segments=translated_segments,
        output_dir=output_dir,
        config=config,
    )

    # Update job status
    job = TranslationJob(
        job_id=job.job_id,
        project_root=job.project_root,
        source_language=job.source_language,
        target_language=job.target_language,
        status=JobStatus.COMPLETED,
        progress=pipeline.progress or JobProgress(),
        created_at=job.created_at,
        updated_at=datetime.now(tz=UTC),
        config_hash=job.config_hash,
    )

    return job, translated_segments