"""TOTP MFA service (Stage 21).

Enrollment:  generate_totp_secret() → raw secret
             totp_provisioning_uri() → otpauth:// URI for QR
Verification: verify_totp(secret, token) → bool
Recovery:    generate_recovery_codes() → list[str] (plaintext, shown once)
             hash_recovery_code(code) → stored hash
             verify_recovery_code(stored_hashes, code) → bool, returns index if matched

Enforcement: is_mfa_required(role_name) → True for admin / partner / platform_admin roles.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from typing import Optional

import pyotp

_MFA_REQUIRED_ROLES = frozenset({"admin", "partner", "platform_admin"})
_RECOVERY_CODE_COUNT = 8
_RECOVERY_CODE_BYTES = 10  # 80 bits → 20 hex chars


# ── Core TOTP ─────────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    """Return a new random base-32 TOTP secret."""
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str, issuer: str = "TG Audit") -> str:
    """Return the otpauth:// URI for QR-code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, token: str) -> bool:
    """Return True if token is valid for secret (allows ±1 interval drift)."""
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=1)


# ── Recovery codes ────────────────────────────────────────────────────────────

def generate_recovery_codes() -> list[str]:
    """Return a list of one-time recovery codes (shown once, then hash-stored)."""
    return [secrets.token_hex(_RECOVERY_CODE_BYTES) for _ in range(_RECOVERY_CODE_COUNT)]


def hash_recovery_code(code: str) -> str:
    """SHA-256 hash of a recovery code for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


def verify_recovery_code(stored_hashes: list[str], code: str) -> Optional[int]:
    """Return the index of the matched hash, or None if no match.

    The caller must remove the matched hash from stored_hashes to prevent reuse.
    """
    h = hash_recovery_code(code)
    for i, stored in enumerate(stored_hashes):
        if secrets.compare_digest(stored, h):
            return i
    return None


# ── Enforcement helper ────────────────────────────────────────────────────────

def is_mfa_required(role_name: str) -> bool:
    """Return True when MFA is mandatory for the given role."""
    return role_name in _MFA_REQUIRED_ROLES
