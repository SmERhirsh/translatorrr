"""Protection for RPG Maker control codes and other non-translatable tokens."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import re
from typing import Iterable

from rpg_translator.core.errors import PlaceholderMismatchError
from rpg_translator.core.models import PlaceholderKind, ProtectedToken, ValidationIssue, ValidationSeverity

_HTML_TAG_PATTERN = r"</?[A-Za-z][A-Za-z0-9:_-]*(?:\s+[^<>\r\n]*?)?/?>"
_RPGMAKER_CODE_PATTERN = r"\\(?:[A-Za-z]+(?:\[[^\]\r\n]*\])?|[{}.$|!><^\\])"
_ESCAPE_SEQUENCE_PATTERN = r"\\(?:n|r|t|\"|')"
_FORMAT_ARGUMENT_PATTERN = r"%(?:\d+|[A-Za-z])"
_BRACE_ARGUMENT_PATTERN = r"\{[A-Za-z_][A-Za-z0-9_]*\}|\{\d+\}"
_LINE_BREAK_PATTERN = r"\r\n|\r|\n"

_TOKEN_PATTERN = re.compile(
    "|".join(
        [
            f"(?P<html>{_HTML_TAG_PATTERN})",
            f"(?P<escape>{_ESCAPE_SEQUENCE_PATTERN})",
            f"(?P<rpg>{_RPGMAKER_CODE_PATTERN})",
            f"(?P<format>{_FORMAT_ARGUMENT_PATTERN})",
            f"(?P<brace>{_BRACE_ARGUMENT_PATTERN})",
            f"(?P<linebreak>{_LINE_BREAK_PATTERN})",
        ],
    ),
)


@dataclass(frozen=True, slots=True)
class ProtectedText:
    """Text after non-translatable tokens have been replaced by placeholders."""

    original_text: str
    protected_text: str
    tokens: tuple[ProtectedToken, ...]


@dataclass(frozen=True, slots=True)
class _TokenMatch:
    original: str
    kind: PlaceholderKind
    start: int
    end: int


def protect_text(text: str) -> ProtectedText:
    """Replace protected RPG Maker syntax with stable placeholders."""

    matches = tuple(_find_token_matches(text))
    if not matches:
        return ProtectedText(original_text=text, protected_text=text, tokens=())

    placeholders = _make_placeholders(text, len(matches))
    protected_parts: list[str] = []
    tokens: list[ProtectedToken] = []
    cursor = 0

    for index, match in enumerate(matches):
        placeholder = placeholders[index]
        protected_parts.append(text[cursor : match.start])
        protected_parts.append(placeholder)
        tokens.append(
            ProtectedToken(
                placeholder=placeholder,
                original=match.original,
                kind=match.kind,
                index=index,
            ),
        )
        cursor = match.end

    protected_parts.append(text[cursor:])
    return ProtectedText(
        original_text=text,
        protected_text="".join(protected_parts),
        tokens=tuple(tokens),
    )


def restore_placeholders(
    text: str,
    tokens: Iterable[ProtectedToken],
    *,
    strict: bool = True,
) -> str:
    """Restore placeholders in translated/protected text."""

    token_tuple = tuple(tokens)
    if strict:
        issues = validate_placeholders_present(text, token_tuple)
        if issues:
            raise PlaceholderMismatchError(
                "Protected placeholders are missing, duplicated, or modified",
                details={"issues": [issue.message for issue in issues]},
            )

    restored = text
    for token in token_tuple:
        restored = restored.replace(token.placeholder, token.original)
    return restored


def extract_protected_token_inventory(text: str) -> Counter[tuple[PlaceholderKind, str]]:
    """Return a multiset of protected token originals found in text."""

    return Counter((match.kind, match.original) for match in _find_token_matches(text))


def validate_placeholders_present(
    text: str,
    tokens: Iterable[ProtectedToken],
) -> tuple[ValidationIssue, ...]:
    """Ensure every placeholder exists exactly once in protected text."""

    issues: list[ValidationIssue] = []
    for token in tokens:
        count = text.count(token.placeholder)
        if count == 0:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Missing protected placeholder: {token.placeholder}",
                    code="placeholder_missing",
                    details={"placeholder": token.placeholder, "original": token.original},
                ),
            )
        elif count > 1:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Duplicated protected placeholder: {token.placeholder}",
                    code="placeholder_duplicated",
                    details={
                        "placeholder": token.placeholder,
                        "original": token.original,
                        "count": count,
                    },
                ),
            )
    return tuple(issues)


def validate_control_codes_preserved(
    source_text: str,
    candidate_text: str,
) -> tuple[ValidationIssue, ...]:
    """Validate that every protected source token survives unchanged."""

    source_inventory = extract_protected_token_inventory(source_text)
    candidate_inventory = extract_protected_token_inventory(candidate_text)
    if source_inventory == candidate_inventory:
        return ()

    issues: list[ValidationIssue] = []
    missing = source_inventory - candidate_inventory
    added = candidate_inventory - source_inventory

    for (kind, original), count in missing.items():
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Protected token was lost or modified: {original}",
                code="protected_token_missing",
                details={"kind": kind.value, "original": original, "count": count},
            ),
        )
    for (kind, original), count in added.items():
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Unexpected protected token appeared: {original}",
                code="protected_token_added",
                details={"kind": kind.value, "original": original, "count": count},
            ),
        )
    return tuple(issues)


def _find_token_matches(text: str) -> Iterable[_TokenMatch]:
    for match in _TOKEN_PATTERN.finditer(text):
        matched = match.group(0)
        kind = _kind_from_match(match)
        yield _TokenMatch(original=matched, kind=kind, start=match.start(), end=match.end())


def _kind_from_match(match: re.Match[str]) -> PlaceholderKind:
    group = match.lastgroup
    if group == "html":
        return PlaceholderKind.HTML_TAG
    if group == "rpg":
        return PlaceholderKind.RPGMAKER_CONTROL_CODE
    if group == "escape":
        return PlaceholderKind.ESCAPE_SEQUENCE
    if group in {"format", "brace"}:
        return PlaceholderKind.FORMAT_ARGUMENT
    if group == "linebreak":
        return PlaceholderKind.LINE_BREAK
    return PlaceholderKind.UNKNOWN


def _make_placeholders(text: str, count: int) -> tuple[str, ...]:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    for salt in range(1000):
        prefix = f"__RPGMT_{digest}_{salt}_"
        placeholders = tuple(f"{prefix}{index:04d}__" for index in range(count))
        if all(placeholder not in text for placeholder in placeholders):
            return placeholders
    raise PlaceholderMismatchError("Could not generate collision-free placeholders")
