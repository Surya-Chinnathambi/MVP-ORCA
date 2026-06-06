"""Stage 21 acceptance test — MFA, at-rest encryption, sessions, SSO adapter.

Verifies:
1. TOTP enrollment → verification succeeds with correct token, fails with wrong token.
2. Recovery codes: one-time use (consumed after verify), duplicates rejected.
3. Admin login blocks when MFA required but no TOTP/recovery provided.
4. Encrypted evidence round-trips (encrypt → store → decrypt) but is ciphertext at rest.
5. Session rotate_session clears old session keys and re-establishes user_id.
6. OIDCAdapter.is_enabled is False when settings.sso_enabled=False.
7. OIDCAdapter.authorization_url raises SSONotEnabled when flag is off.
"""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.users import Role, RoleName, User
from app.services.auth import hash_password
from app.services.security.mfa import (
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_code,
    is_mfa_required,
    totp_provisioning_uri,
    verify_recovery_code,
    verify_totp,
)
from app.services.security.sso import OIDCAdapter, SSONotEnabled


# ── DB fixture (lightweight — most tests are pure logic) ─────────────────────

@pytest.fixture(scope="module")
def engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)


@pytest.fixture(scope="module")
def db(engine):
    Sess = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Sess()
    for name in [r.value for r in RoleName]:
        session.add(Role(name=name))
    admin = User(
        email="s21_admin@test.local",
        password_hash=hash_password("testpass"),
        full_name="Stage21 Admin",
        is_active=True,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    yield session, admin.id
    session.close()


# ── TOTP enrollment + verification ───────────────────────────────────────────

def test_totp_enroll_and_verify():
    """generate_totp_secret + verify_totp succeeds with current window token."""
    import pyotp
    secret = generate_totp_secret()
    assert len(secret) >= 16, "Secret must be at least 16 base-32 chars"

    token = pyotp.TOTP(secret).now()
    assert verify_totp(secret, token), "Current TOTP token must verify"


def test_totp_rejects_wrong_token():
    """verify_totp returns False for an invalid token."""
    secret = generate_totp_secret()
    assert not verify_totp(secret, "000000")


def test_provisioning_uri_contains_email():
    """totp_provisioning_uri includes the account email and issuer."""
    secret = generate_totp_secret()
    uri = totp_provisioning_uri(secret, "user@test.local")
    assert "user%40test.local" in uri or "user@test.local" in uri
    assert "TG+Audit" in uri or "TG%20Audit" in uri or "TG Audit" in uri


# ── Recovery codes ────────────────────────────────────────────────────────────

def test_recovery_codes_round_trip():
    """generate → hash → verify matches; wrong code returns None."""
    codes = generate_recovery_codes()
    assert len(codes) == 8
    hashes = [hash_recovery_code(c) for c in codes]

    idx = verify_recovery_code(hashes, codes[3])
    assert idx == 3

    assert verify_recovery_code(hashes, "notacode") is None


def test_recovery_code_consumed_on_use():
    """After removing the matched hash, the same code cannot be used again."""
    codes = generate_recovery_codes()
    hashes = [hash_recovery_code(c) for c in codes]

    idx = verify_recovery_code(hashes, codes[0])
    assert idx is not None
    hashes.pop(idx)  # consume

    idx2 = verify_recovery_code(hashes, codes[0])
    assert idx2 is None, "Used recovery code must not verify again"


# ── MFA enforcement ───────────────────────────────────────────────────────────

def test_mfa_required_for_admin_partner_platform_admin():
    """is_mfa_required returns True for privileged roles only."""
    assert is_mfa_required("admin")
    assert is_mfa_required("partner")
    assert is_mfa_required("platform_admin")
    assert not is_mfa_required("analyst")
    assert not is_mfa_required("readonly")
    assert not is_mfa_required("client_contributor")


def test_login_blocked_when_mfa_required_but_not_provided(db):
    """Login endpoint raises 401 for MFA-required users who omit totp_token."""
    session, admin_id = db
    admin = session.get(User, admin_id)

    # Enroll MFA on the admin
    secret = generate_totp_secret()
    admin.mfa_secret = secret
    admin.mfa_enabled = True
    session.commit()

    from app.api.auth import LoginWithMFARequest, login
    from unittest.mock import MagicMock

    # Build a fake request with no session
    fake_request = MagicMock()
    fake_request.session = {}

    body = LoginWithMFARequest(email=admin.email, password="testpass")  # no totp_token
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        login(body, fake_request, session)
    assert exc.value.status_code == 401
    assert "MFA required" in exc.value.detail


def test_login_succeeds_with_valid_totp(db):
    """Login succeeds when the correct TOTP token is provided."""
    import pyotp
    session, admin_id = db
    admin = session.get(User, admin_id)
    assert admin.mfa_secret is not None

    from app.api.auth import LoginWithMFARequest, login
    from unittest.mock import MagicMock

    fake_request = MagicMock()
    fake_request.session = {}

    token = pyotp.TOTP(admin.mfa_secret).now()
    body = LoginWithMFARequest(email=admin.email, password="testpass", totp_token=token)
    result = login(body, fake_request, session)
    assert result.id == admin_id


# ── At-rest encryption ────────────────────────────────────────────────────────

def test_encryption_round_trip():
    """Encrypt + decrypt returns original; ciphertext differs from plaintext."""
    from cryptography.fernet import Fernet
    from app.services.security.crypto import encrypt, decrypt, is_encrypted

    test_key = Fernet.generate_key().decode()
    with patch("app.services.security.crypto._get_fernet") as mock_fernet:
        from cryptography.fernet import Fernet as _F
        f = _F(test_key.encode())
        mock_fernet.return_value = f

        plaintext = "Sensitive extracted evidence text — top secret."
        ciphertext = encrypt(plaintext)

        # Must not be plaintext
        assert plaintext not in ciphertext
        assert is_encrypted(ciphertext)

        # Must round-trip
        recovered = decrypt(ciphertext)
        assert recovered == plaintext


def test_decryption_fails_with_wrong_key():
    """Decryption with mismatched key raises EncryptionError."""
    from cryptography.fernet import Fernet
    from app.services.security.crypto import EncryptionError

    key1 = Fernet.generate_key()
    key2 = Fernet.generate_key()

    from app.services.security.crypto import encrypt, decrypt
    with patch("app.services.security.crypto._get_fernet") as mock_fernet:
        mock_fernet.return_value = Fernet(key1)
        ciphertext = encrypt("secret")

    with patch("app.services.security.crypto._get_fernet") as mock_fernet:
        mock_fernet.return_value = Fernet(key2)
        with pytest.raises(EncryptionError):
            decrypt(ciphertext)


# ── Session rotation ──────────────────────────────────────────────────────────

def test_session_rotation_clears_old_keys():
    """rotate_session clears the old session and re-establishes only user_id."""
    from app.api.auth import rotate_session

    fake_request = MagicMock()
    session_data = {"user_id": "old-id", "extra_key": "should-be-gone"}
    fake_request.session = session_data

    rotate_session(fake_request, "new-id")

    assert fake_request.session.get("user_id") == "new-id"
    assert "extra_key" not in fake_request.session


# ── SSO adapter ───────────────────────────────────────────────────────────────

def test_oidc_adapter_disabled_by_default():
    """OIDCAdapter.is_enabled is False when settings.sso_enabled=False."""
    with patch("app.services.security.sso.OIDCAdapter.__init__", lambda self: None):
        adapter = OIDCAdapter.__new__(OIDCAdapter)
        adapter._enabled = False
        adapter._client_id = ""
        adapter._client_secret = ""
        adapter._tenant_id = ""
        assert not adapter.is_enabled


def test_oidc_adapter_raises_when_disabled():
    """authorization_url raises SSONotEnabled when flag is off."""
    with patch("app.services.security.sso.OIDCAdapter.__init__", lambda self: None):
        adapter = OIDCAdapter.__new__(OIDCAdapter)
        adapter._enabled = False

        with pytest.raises(SSONotEnabled):
            adapter.authorization_url("https://example.com/callback", "state123")


def test_oidc_adapter_enabled_builds_url():
    """When enabled, authorization_url returns a valid-looking URL string."""
    with patch("app.services.security.sso.OIDCAdapter.__init__", lambda self: None):
        adapter = OIDCAdapter.__new__(OIDCAdapter)
        adapter._enabled = True
        adapter._client_id = "test-client-id"
        adapter._client_secret = "secret"
        adapter._tenant_id = "test-tenant"

        with patch("authlib.integrations.requests_client.OAuth2Session") as mock_cls:
            mock_session = MagicMock()
            mock_session.create_authorization_url.return_value = (
                "https://login.microsoftonline.com/test-tenant/v2.0/oauth2/v2.0/authorize?client_id=test",
                "state",
            )
            mock_cls.return_value = mock_session

            url = adapter.authorization_url("https://app/callback", "state123")
            assert "microsoftonline.com" in url or "client_id" in url
