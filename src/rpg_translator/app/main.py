"""Minimal Phase 1 command entry point.

The GUI and translation pipeline are intentionally not initialized in Phase 1.
"""

from __future__ import annotations

from rpg_translator.config import load_config
from rpg_translator.logging import configure_logging, get_logger


def main() -> int:
    """Load configuration and initialize logging.

    This keeps the installed console script useful for smoke checks without
    introducing translation or GUI behavior before their phases.
    """

    config = load_config()
    configure_logging(config.logging)
    logger = get_logger(__name__)
    logger.info("RPG Maker Translator initialized", extra={"phase": "phase_1"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

