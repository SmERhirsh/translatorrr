import unittest

from rpg_translator.core.models import JsonPointer
from rpg_translator.rpgmaker.parsers import parse_event_commands


class EventCommandParserTests(unittest.TestCase):
    def test_parses_dialogue_choices_and_scrolling_text(self) -> None:
        commands = [
            {"code": 101, "indent": 0, "parameters": ["Actor1", 0, 0, 2, "Guide"]},
            {"code": 401, "indent": 0, "parameters": ["Hello \\N[1]."]},
            {"code": 102, "indent": 0, "parameters": [["Yes", "No"], 0, 0, 2, 0]},
            {"code": 402, "indent": 0, "parameters": [0, "Yes"]},
            {"code": 105, "indent": 0, "parameters": [2, False]},
            {"code": 405, "indent": 0, "parameters": ["The story begins."]},
        ]

        occurrences = parse_event_commands(commands, JsonPointer.root().child("list"))

        self.assertEqual(
            [(occurrence.field_name, occurrence.text, occurrence.pointer.as_string()) for occurrence in occurrences],
            [
                ("speaker_name", "Guide", "/list/0/parameters/4"),
                ("dialogue", "Hello \\N[1].", "/list/1/parameters/0"),
                ("choice", "Yes", "/list/2/parameters/0/0"),
                ("choice", "No", "/list/2/parameters/0/1"),
                ("choice_branch", "Yes", "/list/3/parameters/1"),
                ("scrolling_text", "The story begins.", "/list/5/parameters/0"),
            ],
        )


if __name__ == "__main__":
    unittest.main()

