import unittest

from rpg_translator.core.errors import PlaceholderMismatchError
from rpg_translator.core.models import PlaceholderKind
from rpg_translator.translation import (
    protect_text,
    restore_placeholders,
    validate_control_codes_preserved,
    validate_placeholders_present,
)


class PlaceholderizerTests(unittest.TestCase):
    def test_protects_and_restores_rpgmaker_control_codes_and_tags(self) -> None:
        source = "Hello \\N[1], take <b>Potion</b> for %1 HP!\\."

        protected = protect_text(source)
        restored = restore_placeholders(protected.protected_text, protected.tokens)

        self.assertEqual(restored, source)
        self.assertNotIn("\\N[1]", protected.protected_text)
        self.assertNotIn("<b>", protected.protected_text)
        self.assertNotIn("%1", protected.protected_text)
        self.assertEqual(
            [token.kind for token in protected.tokens],
            [
                PlaceholderKind.RPGMAKER_CONTROL_CODE,
                PlaceholderKind.HTML_TAG,
                PlaceholderKind.HTML_TAG,
                PlaceholderKind.FORMAT_ARGUMENT,
                PlaceholderKind.RPGMAKER_CONTROL_CODE,
            ],
        )

    def test_strict_restore_rejects_missing_placeholder(self) -> None:
        protected = protect_text("Value: \\V[2]")
        modified = protected.protected_text.replace(protected.tokens[0].placeholder, "")

        with self.assertRaises(PlaceholderMismatchError):
            restore_placeholders(modified, protected.tokens)

    def test_placeholder_validation_rejects_duplicates(self) -> None:
        protected = protect_text("Name: \\N[1]")
        duplicated = protected.protected_text + protected.tokens[0].placeholder

        issues = validate_placeholders_present(duplicated, protected.tokens)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "placeholder_duplicated")

    def test_control_code_validation_detects_loss_or_modification(self) -> None:
        source = "Hello \\N[1], color \\C[3]red\\C[0]."
        candidate = "Hello \\N[2], color \\C[3]red."

        issues = validate_control_codes_preserved(source, candidate)
        codes = {issue.code for issue in issues}

        self.assertIn("protected_token_missing", codes)
        self.assertIn("protected_token_added", codes)


if __name__ == "__main__":
    unittest.main()

