"""Security API — MFA enrollment, verification, recovery codes (Stage 21)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.deps import get_current_user
from app.models.users import User
from app.services.security.mfa import (
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_code,
    totp_provisioning_uri,
    verify_totp,
    verify_recovery_code,
)

router = APIRouter(prefix="/security", tags=["security"])


class EnrollMFAResponse(BaseModel):
    provisioning_uri: str
    recovery_codes: list[str]


class VerifyMFARequest(BaseModel):
    totp_token: str


# ── MFA enrollment ────────────────────────────────────────────────────────────

@router.post("/mfa/enroll", response_model=EnrollMFAResponse)
def enroll_mfa(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a new TOTP secret and recovery codes for the current user.

    Returns the provisioning URI for QR code and the one-time recovery codes.
    MFA is NOT marked active until /mfa/activate is called with a valid token.
    """
    secret = generate_totp_secret()
    current_user.mfa_secret = secret

    codes = generate_recovery_codes()
    current_user.mfa_recovery_hashes = [hash_recovery_code(c) for c in codes]
    db.commit()

    uri = totp_provisioning_uri(secret, current_user.email)
    return EnrollMFAResponse(provisioning_uri=uri, recovery_codes=codes)


@router.post("/mfa/activate")
def activate_mfa(
    body: VerifyMFARequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm enrollment by verifying a TOTP token; sets mfa_enabled=True."""
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA not enrolled — call /mfa/enroll first")
    if not verify_totp(current_user.mfa_secret, body.totp_token):
        raise HTTPException(status_code=401, detail="Invalid TOTP token")
    current_user.mfa_enabled = True
    db.commit()
    return {"mfa_enabled": True}


@router.delete("/mfa/disable")
def disable_mfa(
    body: VerifyMFARequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disable MFA after verifying current TOTP token."""
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA not enrolled")
    if not verify_totp(current_user.mfa_secret, body.totp_token):
        raise HTTPException(status_code=401, detail="Invalid TOTP token")
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    current_user.mfa_recovery_hashes = None
    db.commit()
    return {"mfa_enabled": False}


@router.get("/mfa/status")
def mfa_status(current_user: User = Depends(get_current_user)):
    """Return whether MFA is enrolled and active for the current user."""
    return {
        "mfa_enrolled": current_user.mfa_secret is not None,
        "mfa_enabled": current_user.mfa_enabled,
        "recovery_codes_remaining": len(current_user.mfa_recovery_hashes or []),
    }
