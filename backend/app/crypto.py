"""Encrypt connector secrets at rest. The key never leaves this machine."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class SecretError(Exception):
    pass


def _fernet() -> Fernet:
    settings = get_settings()
    raw = settings.connector_master_key.strip()
    if not raw:
        path = settings.backend_root / "data" / "connector.key"
        if path.is_file():
            raw = path.read_text(encoding="utf-8").strip()
        else:
            raw = Fernet.generate_key().decode("ascii")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(raw + "\n", encoding="utf-8")
    try:
        return Fernet(raw.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise SecretError("CONNECTOR_MASTER_KEY is not a valid Fernet key") from exc


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise SecretError("Stored connector secret could not be decrypted") from exc
