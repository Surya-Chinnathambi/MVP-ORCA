"""Startup self-check — fails loud on missing or insecure secrets.

Usage:
    from app.services.ops.health import startup_check
    startup_check(settings)

The check accepts any object with the following attributes:
    secret_key: str
    encryption_key: str
    environment: str  ("dev" | "test" | "prod")

Severity rules:
    Always   — fail if secret_key is empty
    prod only — fail if secret_key is the default placeholder value
    prod only — fail if encryption_key is not set
"""
from __future__ import annotations

_DEFAULT_SECRET_KEY = "change-me-in-production"

# Accept either of the two placeholder values seen in .env.example
_INSECURE_SECRETS = frozenset({
    _DEFAULT_SECRET_KEY,
    "change-me-in-production-use-32-char-minimum",
})


def startup_check(cfg) -> None:
    """Validate security-critical configuration.

    Raises RuntimeError listing all failures so the operator sees every
    problem at once rather than fixing one per restart.
    """
    errors: list[str] = []

    secret_key: str = getattr(cfg, "secret_key", "") or ""
    encryption_key: str = getattr(cfg, "encryption_key", "") or ""
    environment: str = getattr(cfg, "environment", "dev") or "dev"

    # Always required
    if not secret_key:
        errors.append("SECRET_KEY is required but not set")

    # Production-only checks
    if environment == "prod":
        if secret_key in _INSECURE_SECRETS:
            errors.append(
                "SECRET_KEY must be changed from its default value in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if not encryption_key:
            errors.append(
                "ENCRYPTION_KEY must be set in production. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

    if errors:
        raise RuntimeError(
            "Startup configuration check failed:\n"
            + "\n".join(f"  [{i + 1}] {e}" for i, e in enumerate(errors))
        )
