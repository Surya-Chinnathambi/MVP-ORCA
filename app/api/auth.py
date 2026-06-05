"""Auth API — login with optional TOTP, logout, me, session helpers."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.users import Permission, Role, User
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.users import UserOut
from app.services.auth import verify_password
from app.services.security.mfa import is_mfa_required, verify_recovery_code, verify_totp

router = APIRouter(prefix="/auth", tags=["auth"])

_SESSION_LAST_ACTIVE = "last_active"
_SESSION_USER_ID = "user_id"


# ── Idle-timeout middleware helper ────────────────────────────────────────────

def _check_and_refresh_session(request: Request) -> bool:
    """Return False and clear session if idle timeout exceeded."""
    from app.config import settings
    last = request.session.get(_SESSION_LAST_ACTIVE)
    if last is not None:
        elapsed = datetime.now(timezone.utc).timestamp() - last
        if elapsed > settings.session_idle_timeout:
            request.session.clear()
            return False
    request.session[_SESSION_LAST_ACTIVE] = datetime.now(timezone.utc).timestamp()
    return True


def rotate_session(request: Request, user_id: str) -> None:
    """Rotate session ID on privilege change (clears + re-sets user_id)."""
    request.session.clear()
    request.session[_SESSION_USER_ID] = user_id
    request.session[_SESSION_LAST_ACTIVE] = datetime.now(timezone.utc).timestamp()


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginWithMFARequest(LoginRequest):
    totp_token: Optional[str] = None
    recovery_code: Optional[str] = None


@router.post("/login", response_model=LoginResponse)
def login(body: LoginWithMFARequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    # Determine if MFA is required for any of the user's roles
    mfa_needed = user.mfa_enabled
    if not mfa_needed:
        roles = (
            db.query(Role)
            .join(Permission, Permission.role_id == Role.id)
            .filter(Permission.user_id == user.id)
            .all()
        )
        mfa_needed = any(is_mfa_required(r.name) for r in roles)

    if mfa_needed:
        if not user.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MFA required but not enrolled. Contact an administrator.",
            )
        # Try TOTP token first, then recovery code
        if body.totp_token:
            if not verify_totp(user.mfa_secret, body.totp_token):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid TOTP token")
        elif body.recovery_code:
            hashes = list(user.mfa_recovery_hashes or [])
            idx = verify_recovery_code(hashes, body.recovery_code)
            if idx is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery code")
            # Consume the recovery code
            hashes.pop(idx)
            user.mfa_recovery_hashes = hashes
            db.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA required: provide totp_token or recovery_code",
            )

    request.session[_SESSION_USER_ID] = user.id
    request.session[_SESSION_LAST_ACTIVE] = datetime.now(timezone.utc).timestamp()
    return LoginResponse(id=user.id, email=user.email, full_name=user.full_name)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request):
    request.session.clear()


@router.get("/me", response_model=UserOut)
def me(request: Request, current_user: User = Depends(get_current_user)):
    _check_and_refresh_session(request)
    return current_user
