"""Parsers for RPG Maker event command text."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from rpg_translator.core.models import JsonPointer

SHOW_TEXT = 101
SHOW_TEXT_LINE = 401
SHOW_CHOICES = 102
CHOICE_BRANCH = 402
SCROLLING_TEXT = 105
SCROLLING_TEXT_LINE = 405


@dataclass(frozen=True, slots=True)
class EventTextOccurrence:
    """One translatable string found inside an event command list."""

    text: str
    pointer: JsonPointer
    field_name: str
    command_index: int
    command_code: int
    metadata: Mapping[str, Any] = field(default_factory=dict)


def parse_event_commands(
    commands: Sequence[Any],
    base_pointer: JsonPointer,
) -> tuple[EventTextOccurrence, ...]:
    """Extract translatable text from a RPG Maker event-command list."""

    occurrences: list[EventTextOccurrence] = []

    for command_index, command in enumerate(commands):
        if not isinstance(command, Mapping):
            continue

        code = command.get("code")
        parameters = command.get("parameters", [])
        if not isinstance(code, int) or not isinstance(parameters, list):
            continue

        command_pointer = base_pointer.child(command_index)

        if code == SHOW_TEXT:
            occurrence = _parse_show_text_speaker(parameters, command_pointer, command_index, code)
            if occurrence is not None:
                occurrences.append(occurrence)
            continue

        if code == SHOW_TEXT_LINE:
            occurrence = _parse_single_parameter_text(
                parameters,
                command_pointer,
                command_index,
                code,
                parameter_index=0,
                field_name="dialogue",
                role="show_text_line",
            )
            if occurrence is not None:
                occurrences.append(occurrence)
            continue

        if code == SHOW_CHOICES:
            occurrences.extend(_parse_show_choices(parameters, command_pointer, command_index, code))
            continue

        if code == CHOICE_BRANCH:
            occurrence = _parse_single_parameter_text(
                parameters,
                command_pointer,
                command_index,
                code,
                parameter_index=1,
                field_name="choice_branch",
                role="choice_branch_label",
            )
            if occurrence is not None:
                occurrences.append(occurrence)
            continue

        if code == SCROLLING_TEXT_LINE:
            occurrence = _parse_single_parameter_text(
                parameters,
                command_pointer,
                command_index,
                code,
                parameter_index=0,
                field_name="scrolling_text",
                role="scrolling_text_line",
            )
            if occurrence is not None:
                occurrences.append(occurrence)

    return tuple(occurrences)


def _parse_show_text_speaker(
    parameters: Sequence[Any],
    command_pointer: JsonPointer,
    command_index: int,
    code: int,
) -> EventTextOccurrence | None:
    if len(parameters) <= 4:
        return None
    value = parameters[4]
    if not _is_translatable_string(value):
        return None
    return EventTextOccurrence(
        text=value,
        pointer=command_pointer.child("parameters").child(4),
        field_name="speaker_name",
        command_index=command_index,
        command_code=code,
        metadata={"role": "show_text_speaker"},
    )


def _parse_show_choices(
    parameters: Sequence[Any],
    command_pointer: JsonPointer,
    command_index: int,
    code: int,
) -> tuple[EventTextOccurrence, ...]:
    if not parameters or not isinstance(parameters[0], list):
        return ()

    occurrences: list[EventTextOccurrence] = []
    for choice_index, choice in enumerate(parameters[0]):
        if not _is_translatable_string(choice):
            continue
        occurrences.append(
            EventTextOccurrence(
                text=choice,
                pointer=command_pointer.child("parameters").child(0).child(choice_index),
                field_name="choice",
                command_index=command_index,
                command_code=code,
                metadata={"role": "choice", "choice_index": choice_index},
            ),
        )
    return tuple(occurrences)


def _parse_single_parameter_text(
    parameters: Sequence[Any],
    command_pointer: JsonPointer,
    command_index: int,
    code: int,
    *,
    parameter_index: int,
    field_name: str,
    role: str,
) -> EventTextOccurrence | None:
    if len(parameters) <= parameter_index:
        return None
    value = parameters[parameter_index]
    if not _is_translatable_string(value):
        return None
    return EventTextOccurrence(
        text=value,
        pointer=command_pointer.child("parameters").child(parameter_index),
        field_name=field_name,
        command_index=command_index,
        command_code=code,
        metadata={"role": role},
    )


def _is_translatable_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())

