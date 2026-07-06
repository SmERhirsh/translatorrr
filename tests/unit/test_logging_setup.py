import tempfile
import unittest
from pathlib import Path

from rpg_translator.config.schema import LoggingSettings
from rpg_translator.logging import configure_logging


class LoggingSetupTests(unittest.TestCase):
    def test_json_logging_redacts_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_dir = Path(directory)
            settings = LoggingSettings(
                level="INFO",
                console_enabled=False,
                file_enabled=True,
                json_file=True,
                log_dir=str(log_dir),
            )
            logger = configure_logging(settings)

            try:
                logger.info(
                    "Calling provider with Authorization: Bearer abc123",
                    extra={"api_key": "secret-value", "safe": "visible"},
                )
                for handler in logger.handlers:
                    handler.flush()

                content = (log_dir / "rpg-maker-translator.log").read_text(encoding="utf-8")
            finally:
                for handler in list(logger.handlers):
                    logger.removeHandler(handler)
                    handler.close()

        self.assertNotIn("abc123", content)
        self.assertNotIn("secret-value", content)
        self.assertIn("visible", content)


if __name__ == "__main__":
    unittest.main()
