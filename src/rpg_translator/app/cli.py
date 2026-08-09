"""CLI entry point for RPG Maker Translator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rpg_translator.config import load_config
from rpg_translator.logging import configure_logging, get_logger
from rpg_translator.providers.registry import create_provider, provider_profile_from_config
from rpg_translator.rpgmaker.detector import detect_project
from rpg_translator.translation.pipeline import translate_project


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="rpg-translator",
        description="Translate RPG Maker games to other languages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add the translate command
    translate_parser = subparsers.add_parser(
        "translate",
        help="Translate an RPG Maker project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    translate_parser.add_argument(
        "project_path",
        type=Path,
        help="Path to the RPG Maker project directory",
    )
    translate_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output directory for translated project",
    )
    translate_parser.add_argument(
        "--provider-profile",
        "-p",
        type=str,
        default=None,
        help="Provider profile name from config (overrides config file)",
    )
    translate_parser.add_argument(
        "--source-language",
        "-s",
        type=str,
        default=None,
        help="Source language code (overrides config file)",
    )
    translate_parser.add_argument(
        "--target-language",
        "-t",
        type=str,
        required=True,
        help="Target language code (e.g., 'ru' for Russian)",
    )
    translate_parser.add_argument(
        "--checkpoint-dir",
        "-c",
        type=Path,
        default=None,
        help="Directory for checkpoint files (enables resume capability)",
    )
    translate_parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set the logging level (default: INFO)",
    )

    return parser


def run_translate_command(args: argparse.Namespace) -> int:
    """Execute the translate command."""
    logger = get_logger(__name__)

    # Validate project path
    if not args.project_path.exists():
        print(f"Error: Project path does not exist: {args.project_path}", file=sys.stderr)
        return 1

    if not args.project_path.is_dir():
        print(f"Error: Project path is not a directory: {args.project_path}", file=sys.stderr)
        return 1

    # Load configuration
    try:
        config = load_config()
    except Exception as exc:
        print(f"Error loading configuration: {exc}", file=sys.stderr)
        return 1

    # Apply CLI overrides
    if args.provider_profile:
        config.active_provider = args.provider_profile
    if args.source_language:
        config.source_language = args.source_language
    if args.target_language:
        config.target_language = args.target_language

    # Configure logging
    configure_logging(config.logging)
    logger.info(
        "Starting translation",
        extra={
            "project_path": str(args.project_path),
            "output_path": str(args.output),
            "source_language": config.source_language,
            "target_language": config.target_language,
        },
    )

    # Detect project
    try:
        project = detect_project(args.project_path)
    except Exception as exc:
        print(f"Error detecting project: {exc}", file=sys.stderr)
        return 1

    logger.info(
        "Project detected",
        extra={
            "title": project.title,
            "engine": project.engine.value,
            "file_count": len(project.files),
        },
    )

    # Get provider
    try:
        profile = provider_profile_from_config(config)
        provider = create_provider(profile)
    except Exception as exc:
        print(f"Error initializing provider: {exc}", file=sys.stderr)
        return 1

    # Create output directory
    try:
        args.output.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"Error creating output directory: {exc}", file=sys.stderr)
        return 1

    # Run translation
    try:
        job, translated_segments = translate_project(
            project=project,
            config=config,
            provider=provider,
            output_dir=args.output,
            checkpoint_dir=args.checkpoint_dir,
        )
        logger.info(
            "Translation completed",
            extra={
                "job_id": job.job_id,
                "segments_translated": len(translated_segments),
            },
        )
        print(f"Successfully translated '{project.title}' to {config.target_language}")
        print(f"Output written to: {args.output}")
        return 0
    except Exception as exc:
        logger.error("Translation failed", extra={"error": str(exc)})
        print(f"Error during translation: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "translate":
        return run_translate_command(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
