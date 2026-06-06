"""At-rest encryption for sensitive fields (Stage 21).

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography library.
Key is loaded from settings.encryption_key (32-byte URL-safe base64 string).

Public API:
  encrypt(plaintext: str) -> str   — returns base64-encoded ciphertext token
  decrypt(token: str) -> str       — returns plaintext
  encrypt_bytes(data: bytes) -> bytes
  decrypt_bytes(data: bytes) -> bytes

Evidence fields encrypted at rest: extracted_text, item_metadata (json-serialised).
The key MUST be set in .env — never hard-coded here.
"""
from __future__ import annotations

import base64
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(Exception):
    pass


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Load Fernet instance once from the environment / settings."""
    from app.config import settings
    key = settings.encryption_key
    if not key:
        raise EncryptionError("ENCRYPTION_KEY is not set — cannot encrypt/decrypt at rest")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        raise EncryptionError(f"Invalid ENCRYPTION_KEY: {exc}") from exc


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string; return a URL-safe base64 Fernet token (str)."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """Decrypt a Fernet token back to plaintext string."""
    f = _get_fernet()
    try:
        return f.decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError("Decryption failed — token invalid or key mismatch") from exc


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt raw bytes; return Fernet token bytes."""
    return _get_fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    """Decrypt Fernet token bytes back to original bytes."""
    try:
        return _get_fernet().decrypt(data)
    except InvalidToken as exc:
        raise EncryptionError("Decryption failed") from exc


def is_encrypted(value: str) -> bool:
    """Heuristic: Fernet tokens start with 'gAA' (version byte 0x80, base64-encoded)."""
    return isinstance(value, str) and value.startswith("gAA")
