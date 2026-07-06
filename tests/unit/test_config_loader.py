import tempfile
import unittest
from pathlib import Path

from rpg_translator.config.loader import DEFAULT_CONFIG_PATH, ConfigLoader
from rpg_translator.config.profiles import ConfigPaths
from rpg_translator.core.errors import ConfigError
from rpg_translator.core.models import ProviderKind


def _loader() -> ConfigLoader:
    return ConfigLoader(ConfigPaths(defaults=DEFAULT_CONFIG_PATH, user=None))


class ConfigLoaderTests(unittest.TestCase):
    def test_loads_packaged_defaults(self) -> None:
        config = _loader().load()

        self.assertEqual(config.app_name, "RPG Maker Translator")
        self.assertEqual(config.source_language, "en")
        self.assertEqual(config.target_language, "ru")
        self.assertEqual(config.active_provider, "lm_studio")
        self.assertIs(config.active_provider_profile.kind, ProviderKind.LM_STUDIO)
        self.assertTrue(config.extraction.translate_dialogue)
        self.assertTrue(config.stable_hash)

    def test_project_config_and_overrides_are_layered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_config = Path(directory) / ".rpg_translator.toml"
            project_config.write_text(
                """
[provider]
active_profile = "ollama"

[translation]
batch_max_segments = 4
""".strip(),
                encoding="utf-8",
            )

            config = _loader().load(
                project_config_path=project_config,
                overrides={"translation": {"batch_max_chars": 1200}},
            )

        self.assertEqual(config.active_provider, "ollama")
        self.assertIs(config.active_provider_profile.kind, ProviderKind.OLLAMA)
        self.assertEqual(config.translation.batch_max_segments, 4)
        self.assertEqual(config.translation.batch_max_chars, 1200)

    def test_invalid_active_provider_fails_validation(self) -> None:
        with self.assertRaises(ConfigError):
            _loader().load(overrides={"provider": {"active_profile": "missing"}})

    def test_provider_secrets_are_not_serialized_by_default(self) -> None:
        config = _loader().load(
            overrides={"provider": {"profiles": {"lm_studio": {"api_key": "secret-value"}}}},
        )

        profile_dict = config.to_dict()["provider"]["profiles"]["lm_studio"]

        self.assertEqual(config.active_provider_profile.effective_api_key, "secret-value")
        self.assertIs(profile_dict["api_key"], True)
        self.assertNotIn("secret-value", str(config.to_dict()))


if __name__ == "__main__":
    unittest.main()
