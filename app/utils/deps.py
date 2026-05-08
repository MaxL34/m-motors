"""FastAPI dependency functions for authentication guards."""
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.security import decode_access_token

COOKIE_NAME = "access_token"


def get_current_user(
    db: Session = Depends(get_db),
    access_token: Optional[str] = Cookie(default=None),
) -> Optional[User]:
    """Return the authenticated user or None — never raises.

    Used on public pages that optionally personalise content when a user
    is logged in (e.g. homepage, vehicle catalogue).
    """
    if not access_token:
        return None
    payload = decode_access_token(access_token)
    if not payload:
        return None
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    return user if user and user.is_active is not False else None


def require_user(
    db: Session = Depends(get_db),
    access_token: Optional[str] = Cookie(default=None),
) -> User:
    """Return the authenticated non-admin user or redirect to /login.

    Raises HTTP 303 instead of 401/403 so the browser follows the redirect
    directly rather than showing a bare error page.
    Admin tokens are explicitly rejected — admins must use require_admin.
    """
    if not access_token:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    payload = decode_access_token(access_token)
    if not payload or payload.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or user.is_active is False:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


def require_admin(
    db: Session = Depends(get_db),
    access_token: Optional[str] = Cookie(default=None),
) -> User:
    """Return the authenticated admin user or redirect to /admin/login.

    Checks both the is_admin JWT claim and the database flag to prevent
    privilege escalation via a forged token payload.
    """
    if not access_token:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})
    payload = decode_access_token(access_token)
    if not payload or not payload.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or user.is_admin is not True or user.is_active is False:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})
    return user
