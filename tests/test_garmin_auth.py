"""Regression checks for session rotation, encrypted storage, and failed syncs."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sync_garmin_data
from garmin_token_cache import cache_prefix, read_session, write_session


def session(label):
    return json.dumps({"di_token": label + "-access-private",
                       "di_refresh_token": label + "-refresh-private",
                       "di_client_id": "test-client"})


@unittest.skipUnless(shutil.which("gpg"), "GPG is needed for encrypted session tests")
class GarminAuthTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / "cache" / "session.gpg"
        self.output = self.root / "week.json"
        self.seed = session("bootstrap")

    def test_cache_round_trip_contains_no_plaintext_tokens(self):
        value = session("rotated")
        write_session(self.cache, value, self.seed)
        self.assertEqual(json.loads(read_session(self.cache, self.seed)), json.loads(value))
        ciphertext = self.cache.read_bytes()
        for secret in json.loads(value).values():
            self.assertNotIn(secret.encode(), ciphertext)
        self.assertEqual(self.cache.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.cache.parent.iterdir()), [self.cache])

    def test_new_bootstrap_secret_cannot_restore_old_session(self):
        write_session(self.cache, session("rotated"), self.seed)
        replacement = session("replacement")
        self.assertNotEqual(cache_prefix(self.seed), cache_prefix(replacement))
        with self.assertRaisesRegex(RuntimeError, "Encrypted Garmin session"):
            read_session(self.cache, replacement)

    def test_public_cache_key_cannot_decrypt_session(self):
        write_session(self.cache, session("rotated"), self.seed)
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                ["gpg", "--no-options", "--batch", "--pinentry-mode", "loopback",
                 "--no-symkey-cache", "--homedir", folder, "--passphrase-fd", "0",
                 "--decrypt", str(self.cache)],
                input=cache_prefix(self.seed).split("-")[-1].encode() + b"\n",
                capture_output=True, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b"private", result.stdout)

    def test_corrupt_cache_is_rejected(self):
        self.cache.parent.mkdir()
        self.cache.write_bytes(b"corrupt cache; must not silently fall back to an old session")
        with self.assertRaisesRegex(RuntimeError, "Encrypted Garmin session"):
            read_session(self.cache, self.seed)

    def test_failed_cache_write_keeps_previous_session(self):
        write_session(self.cache, session("previous"), self.seed)
        previous = self.cache.read_bytes()
        with patch("garmin_token_cache._gpg", side_effect=RuntimeError("encryption failed")):
            with self.assertRaises(RuntimeError):
                write_session(self.cache, session("new"), self.seed)
        self.assertEqual(self.cache.read_bytes(), previous)
        self.assertEqual(list(self.cache.parent.iterdir()), [self.cache])

    def run_sync(self, *, fail_at=None):
        rotated = session("newly-rotated")
        observed = []

        class API:
            def __init__(self, **kwargs):
                self.tokens = self_seed
                self.client = types.SimpleNamespace(dumps=lambda: self.tokens)

            def login(self, folder):
                observed.append(json.loads((Path(folder) / "garmin_tokens.json").read_text()))
                if fail_at == "unchanged-login":
                    raise RuntimeError("authentication failed")
                self.tokens = rotated
                if fail_at == "rotated-login":
                    raise RuntimeError("profile request failed after rotation")

        self_seed = self.seed
        arguments = ["sync_garmin_data.py", "--date", "2026-11-09",
                     "--output", str(self.output), "--encrypted-token-cache", str(self.cache)]
        log = io.StringIO()
        with patch.dict(sys.modules, {"garminconnect": types.SimpleNamespace(Garmin=API)}), \
             patch.dict(os.environ, {"GARMIN_TOKENS_JSON": self.seed}), \
             patch.object(sys, "argv", arguments), \
             patch.object(sync_garmin_data, "fetch_week") as fetch, \
             contextlib.redirect_stdout(log):
            fetch.return_value = {"period_start": "2026-11-02", "period_end": "2026-11-08",
                                  "activities": [], "missing_requests": []}
            if fail_at == "fetch":
                fetch.side_effect = RuntimeError("data request failed after rotation")
            if fail_at:
                with self.assertRaises(RuntimeError):
                    sync_garmin_data.main()
            else:
                sync_garmin_data.main()
        for secret in json.loads(rotated).values():
            self.assertNotIn(secret, log.getvalue())
        return observed, rotated

    def test_next_sync_uses_latest_session_and_never_exports_credentials(self):
        cached = session("cached")
        write_session(self.cache, cached, self.seed)
        observed, rotated = self.run_sync()
        self.assertEqual(observed, [json.loads(cached)])
        self.assertEqual(json.loads(read_session(self.cache, self.seed)), json.loads(rotated))
        self.assertNotIn("di_token", self.output.read_text())
        self.assertNotIn("private", self.output.read_text())

    def test_rotated_session_survives_login_or_data_failure(self):
        for stage in ("rotated-login", "fetch"):
            with self.subTest(stage=stage):
                self.output.write_text("previous dashboard export")
                _, rotated = self.run_sync(fail_at=stage)
                self.assertEqual(json.loads(read_session(self.cache, self.seed)), json.loads(rotated))
                self.assertEqual(self.output.read_text(), "previous dashboard export")

    def test_failed_login_without_rotation_creates_no_cache(self):
        self.run_sync(fail_at="unchanged-login")
        self.assertFalse(self.cache.exists())


if __name__ == "__main__":
    unittest.main()
