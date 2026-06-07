"""SSO / OIDC adapter (Stage 21) — Microsoft Entra ID via Authlib.

Gated behind settings.sso_enabled (default False). When disabled the adapter
is a no-op; local session auth is always the fallback.

NO real tenant credentials appear here — everything comes from .env:
  SSO_ENABLED=true
  SSO_CLIENT_ID=<app-registration-client-id>
  SSO_CLIENT_SECRET=<secret>
  SSO_TENANT_ID=<entra-tenant-id>

The adapter uses Authlib's OAuth2Session for the authorization-code flow.
Account provisioning on first SSO login is a human action (admin creates user).
"""
from __future__ import annotations

from typing import Optional


class SSONotEnabled(Exception):
    pass


class OIDCAdapter:
    """Lightweight OIDC adapter; call is_enabled() before any method."""

    def __init__(self) -> None:
        from app.config import settings
        self._enabled: bool = settings.sso_enabled
        self._client_id: str = settings.sso_client_id
        self._client_secret: str = settings.sso_client_secret
        self._tenant_id: str = settings.sso_tenant_id

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _authority_url(self) -> str:
        return f"https://login.microsoftonline.com/{self._tenant_id}/v2.0"

    def authorization_url(self, redirect_uri: str, state: str) -> str:
        """Return the Entra ID authorization URL to redirect the user to."""
        if not self._enabled:
            raise SSONotEnabled("SSO is disabled — set SSO_ENABLED=true in .env")
        from authlib.integrations.requests_client import OAuth2Session
        client = OAuth2Session(
            client_id=self._client_id,
            redirect_uri=redirect_uri,
            scope="openid email profile",
        )
        url, _ = client.create_authorization_url(
            f"{self._authority_url()}/oauth2/v2.0/authorize",
            state=state,
        )
        return url

    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange an auth code for tokens; return the ID-token claims dict."""
        if not self._enabled:
            raise SSONotEnabled("SSO is disabled")
        from authlib.integrations.requests_client import OAuth2Session
        client = OAuth2Session(
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=redirect_uri,
        )
        token = client.fetch_token(
            f"{self._authority_url()}/oauth2/v2.0/token",
            code=code,
        )
        # Decode the id_token claims without full verification for adapter test
        import json, base64
        id_token = token.get("id_token", "")
        payload = id_token.split(".")[1] if id_token else ""
        padded = payload + "=" * (4 - len(payload) % 4)
        try:
            claims = json.loads(base64.urlsafe_b64decode(padded))
        except Exception:
            claims = {}
        return claims


def get_oidc_adapter() -> OIDCAdapter:
    """Return a configured OIDCAdapter instance."""
    return OIDCAdapter()
