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
    if not access_token:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})
    payload = decode_access_token(access_token)
    if not payload or not payload.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or user.is_admin is not True or user.is_active is False:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})
    return user
