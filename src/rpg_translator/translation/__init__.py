"""Translation engine primitives.

Provider calls and actual translation workflows are intentionally outside Phase 2.
"""

from rpg_translator.translation.placeholderizer import (
    ProtectedText,
    extract_protected_token_inventory,
    protect_text,
    restore_placeholders,
    validate_control_codes_preserved,
    validate_placeholders_present,
)

__all__ = [
    "ProtectedText",
    "extract_protected_token_inventory",
    "protect_text",
    "restore_placeholders",
    "validate_control_codes_preserved",
    "validate_placeholders_present",
]

