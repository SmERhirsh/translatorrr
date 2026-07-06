import unittest

from rpg_translator.core.models import JsonPointer, stable_text_hash


class ModelTests(unittest.TestCase):
    def test_json_pointer_escapes_special_characters(self) -> None:
        pointer = JsonPointer.root().child("events").child(1).child("a/b~c")

        self.assertEqual(pointer.as_string(), "/events/1/a~1b~0c")

    def test_stable_text_hash_normalizes_line_endings_and_outer_space(self) -> None:
        self.assertEqual(stable_text_hash(" hello\r\nworld \n"), stable_text_hash("hello\nworld"))


if __name__ == "__main__":
    unittest.main()
