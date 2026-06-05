"""Web-layer dependency: returns current user or None (redirect instead of 401)."""
from typing import Optional

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.users import User


def get_web_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    uid: Optional[str] = request.session.get("user_id")
    if not uid:
        return None
    user = db.get(User, uid)
    return user if (user and user.is_active) else None


LOGIN_REDIRECT = RedirectResponse("/ui/login", status_code=302)
