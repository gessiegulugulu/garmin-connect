"""Encrypt rotating Garmin sessions before storing them in the Actions cache."""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import tempfile
from pathlib import Path


def validate_tokens(value: str) -> dict:
    tokens = json.loads(value)
    if not isinstance(tokens, dict) or not all(
        isinstance(tokens.get(key), str) and tokens[key]
        for key in ("di_token", "di_refresh_token", "di_client_id")
    ):
        raise ValueError("The Garmin session is missing required token fields.")
    return tokens


def cache_prefix(seed: str) -> str:
    # Changing the bootstrap secret starts a new cache and invalidates old sessions.
    if not seed:
        raise ValueError("GARMIN_TOKENS_JSON is required for the encrypted cache.")
    scope = hmac.new(seed.encode(), b"garmin-cache-scope-v1", hashlib.sha256).hexdigest()
    return "garmin-session-v1-" + scope


def _gpg(folder: Path, seed: str, *args: str) -> bytes:
    # The high-entropy bootstrap secret is never passed as a command argument.
    # Separate derivation domains: the public cache key must never reveal the
    # encryption passphrase, even though both originate from the same secret.
    passphrase = hmac.new(seed.encode(), b"garmin-cache-encryption-v1", hashlib.sha256)
    passphrase = passphrase.hexdigest().encode() + b"\n"
    result = subprocess.run(
        ["gpg", "--no-options", "--batch", "--yes", "--pinentry-mode", "loopback",
         "--no-symkey-cache", "--homedir", str(folder), "--passphrase-fd", "0", *args],
        input=passphrase, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        # GPG output must not expose a plaintext session or other account details.
        raise RuntimeError("Encrypted Garmin session could not be read or saved.")
    return result.stdout


def read_session(path: Path, seed: str) -> str:
    cache_prefix(seed)
    with tempfile.TemporaryDirectory(prefix="garmin-cache-") as folder:
        value = _gpg(Path(folder), seed, "--decrypt", str(path.resolve())).decode()
    validate_tokens(value)
    return value


def write_session(path: Path, value: str, seed: str) -> None:
    cache_prefix(seed)
    validate_tokens(value)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Both plaintext and GPG state stay in a private temporary directory. Only the
    # encrypted file is moved to the location uploaded by actions/cache/save.
    with tempfile.TemporaryDirectory(prefix="garmin-cache-", dir=path.parent) as folder:
        root = Path(folder)
        plaintext = root / "session.json"
        with plaintext.open("x", encoding="utf-8") as stream:
            plaintext.chmod(0o600)
            stream.write(value)
        encrypted = root / "session.gpg"
        _gpg(root, seed, "--output", str(encrypted.resolve()),
             "--symmetric", "--cipher-algo", "AES256", str(plaintext.resolve()))
        encrypted.chmod(0o600)
        encrypted.replace(path)
