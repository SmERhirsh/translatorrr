"""Minimal Phase 1 command entry point.

The GUI and translation pipeline are intentionally not initialized in Phase 1.
"""

from __future__ import annotations

import sys

from rpg_translator.app.cli import main as cli_main


def main() -> int:
    """Load configuration and initialize logging.

    This keeps the installed console script useful for smoke checks without
    introducing translation or GUI behavior before their phases.
    """
    # Delegate to CLI for full functionality
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())

