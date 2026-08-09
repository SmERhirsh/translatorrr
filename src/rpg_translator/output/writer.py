"""Output writer for translated RPG Maker projects."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from rpg_translator.config.schema import AppConfig, OutputMode
from rpg_translator.core.errors import OutputWriteError
from rpg_translator.core.models import (
    GameProject,
    JsonPointer,
    OutputManifestEntry,
    ProjectFile,
    RPGMakerFileKind,
    SegmentStatus,
    TextSegment,
)
from rpg_translator.rpgmaker.json_loader import load_project_data_files


def write_translated_project(
    project: GameProject,
    translated_segments: tuple[TextSegment, ...],
    output_dir: Path,
    config: AppConfig,
) -> tuple[OutputManifestEntry, ...]:
    """Write translated project files to output directory.

    Args:
        project: Source game project.
        translated_segments: Translated segments with JSON pointer context.
        output_dir: Target output directory.
        config: Application configuration.

    Returns:
        Tuple of manifest entries for changed files.
    """
    output_mode = config.output.mode

    if output_mode is OutputMode.MANIFEST_ONLY:
        # Just write manifest without modifying files
        return _write_manifest_only(project, translated_segments, output_dir)

    # Create output directory structure
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group translations by source file
    translations_by_file: dict[Path, list[TextSegment]] = {}
    for segment in translated_segments:
        if segment.status is SegmentStatus.TRANSLATED and segment.translation:
            if segment.source_file not in translations_by_file:
                translations_by_file[segment.source_file] = []
            translations_by_file[segment.source_file].append(segment)

    manifest_entries: list[OutputManifestEntry] = []

    # Process each file that has translations
    for source_path, segments in translations_by_file.items():
        entry = _translate_and_write_file(
            source_path=source_path,
            segments=segments,
            output_dir=output_dir,
            project=project,
            config=config,
        )
        if entry:
            manifest_entries.append(entry)

    # Write manifest
    if config.output.write_manifest:
        _write_manifest(manifest_entries, output_dir / "translation_manifest.json")

    return tuple(manifest_entries)


def _translate_and_write_file(
    source_path: Path,
    segments: list[TextSegment],
    output_dir: Path,
    project: GameProject,
    config: AppConfig,
) -> OutputManifestEntry | None:
    """Translate a single file and write it to output."""
    try:
        # Load original JSON
        content = source_path.read_text(encoding="utf-8")
        data = json.loads(content)

        # Apply translations by JSON pointer
        changed_count = 0
        for segment in segments:
            if segment.translation and segment.context.json_pointer:
                _apply_translation_at_pointer(
                    data,
                    segment.context.json_pointer,
                    segment.translation,
                )
                changed_count += 1

        if changed_count == 0:
            return None

        # Determine output path
        relative_path = source_path.relative_to(project.root_path)
        if config.output.mode is OutputMode.TRANSLATED_COPY:
            # Place in output directory with same relative path
            output_path = output_dir / relative_path
        else:
            # Default: place in suffixed directory
            suffix = config.output.directory_suffix
            output_path = project.root_path.parent / f"{project.root_path.name}{suffix}" / relative_path

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write output JSON
        _write_json(output_path, data, config)

        # Calculate hashes
        source_hash = _hash_file(source_path)
        output_hash = _hash_file(output_path)

        return OutputManifestEntry(
            source_path=source_path,
            output_path=output_path,
            source_sha256=source_hash,
            output_sha256=output_hash,
            changed_segments=changed_count,
        )

    except (json.JSONDecodeError, OSError, KeyError) as exc:
        raise OutputWriteError(
            f"Failed to write translated file: {source_path}",
            details={"error": str(exc)},
        ) from exc


def _apply_translation_at_pointer(
    data: dict[str, Any] | list[Any],
    pointer: JsonPointer,
    translation: str,
) -> None:
    """Apply a translation at the specified JSON pointer location."""
    target = data
    parts = pointer.parts

    # Navigate to parent
    for i, part in enumerate(parts[:-1]):
        if isinstance(part, int):
            if not isinstance(target, list):
                raise KeyError(f"Expected array at {'/'.join(str(p) for p in parts[:i])}")
            target = target[part]
        else:
            if not isinstance(target, dict):
                raise KeyError(f"Expected object at {'/'.join(str(p) for p in parts[:i])}")
            target = target[part]

    # Set final value
    final_part = parts[-1]
    if isinstance(final_part, int):
        if not isinstance(target, list):
            raise KeyError(f"Expected array at pointer")
        target[final_part] = translation
    else:
        if not isinstance(target, dict):
            raise KeyError(f"Expected object at pointer")
        target[final_part] = translation


def _write_json(path: Path, data: Any, config: AppConfig) -> None:
    """Write JSON data to file with configured formatting."""
    indent = 2 if config.output.preserve_json_indentation else None
    separators = (",", ": ") if indent else (",", ":")

    content = json.dumps(
        data,
        ensure_ascii=False,
        indent=indent,
        separators=separators,
        sort_keys=False,  # Preserve original key order
    )
    path.write_text(content + "\n", encoding="utf-8")


def _hash_file(path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    import hashlib

    digest = hashlib.sha256()
    content = path.read_bytes()
    digest.update(content)
    return digest.hexdigest()


def _write_manifest_only(
    project: GameProject,
    translated_segments: tuple[TextSegment, ...],
    output_dir: Path,
) -> tuple[OutputManifestEntry, ...]:
    """Write only a manifest without modifying files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Count translated segments per file
    counts_by_file: dict[Path, int] = {}
    for segment in translated_segments:
        if segment.status is SegmentStatus.TRANSLATED:
            counts_by_file[segment.source_file] = counts_by_file.get(segment.source_file, 0) + 1

    manifest_entries = tuple(
        OutputManifestEntry(
            source_path=source_path,
            output_path=source_path,  # Same as source for manifest-only mode
            source_sha256="",  # Would need to calculate
            output_sha256="",
            changed_segments=count,
        )
        for source_path, count in counts_by_file.items()
    )

    _write_manifest(manifest_entries, output_dir / "translation_manifest.json")
    return manifest_entries


def _write_manifest(entries: tuple[OutputManifestEntry, ...], manifest_path: Path) -> None:
    """Write translation manifest to JSON file."""
    manifest_data = {
        "version": "1.0",
        "entries": [
            {
                "source_path": str(entry.source_path),
                "output_path": str(entry.output_path),
                "source_sha256": entry.source_sha256,
                "output_sha256": entry.output_sha256,
                "changed_segments": entry.changed_segments,
            }
            for entry in entries
        ],
        "total_files": len(entries),
        "total_changed_segments": sum(entry.changed_segments for entry in entries),
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
