"""`flybrain register` against the response POST /v1/me/agents returns."""

import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flybrain import cli

RESPONSE = {
    "success": True,
    "agent": {"id": "agent-id", "name": "Fly TEST", "ticker": "FLYTEST"},
    "api_key": {"secret": "the-secret", "warning": "Store this now."},
    "claim_url": "https://www.clawstreet.io/claim/the-token",
}


def fly_config() -> dict:
    return {"name": "Fly TEST", "ticker": "FLYTEST", "universe": "stocks", "cadence": "daily",
            "bot_id": None, "key": "env:CLAWSTREET_API_KEY_TEST"}


def register(env_file: Path, save_fly: mock.Mock) -> str:
    out = io.StringIO()
    with mock.patch.object(cli, "load_fly", return_value=fly_config()), \
            mock.patch.object(cli, "save_fly", save_fly), \
            mock.patch.object(cli.clawstreet, "register", return_value=RESPONSE), \
            mock.patch("flybrain.config.ENV_FILE", env_file), \
            contextlib.redirect_stdout(out):
        cli.register(argparse.Namespace(fly="test"))
    return out.getvalue()


class RegisterTest(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.env_file = Path(folder.name) / ".env"

    def test_stores_only_the_secret(self) -> None:
        register(self.env_file, mock.Mock())
        self.assertEqual(self.env_file.read_text(), "CLAWSTREET_API_KEY_TEST=the-secret\n")

    def test_saves_the_agent_id(self) -> None:
        save_fly = mock.Mock()
        register(self.env_file, save_fly)
        self.assertEqual(save_fly.call_args.args[1]["bot_id"], "agent-id")

    def test_prints_the_claim_url(self) -> None:
        self.assertIn(RESPONSE["claim_url"], register(self.env_file, mock.Mock()))

    def test_a_failed_save_still_leaves_the_key_and_the_claim_url(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(OSError):
            register(self.env_file, mock.Mock(side_effect=OSError("disk full")))
        self.assertIn("the-secret", self.env_file.read_text())


if __name__ == "__main__":
    unittest.main()
