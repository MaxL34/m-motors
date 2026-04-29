from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user_schema import UserCreate, UserUpdate, PasswordChange
from app.utils.security import hash_password, verify_password


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, data: UserCreate) -> User:
    if get_user_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cette adresse e-mail",
        )
    user = User(
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone_number=data.phone_number or None,
        address=data.address or None,
        password_hash=hash_password(data.password),
        is_admin=False,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, data: UserUpdate) -> User:
    if data.email != user.email and get_user_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse e-mail est déjà utilisée",
        )
    user.first_name = data.first_name
    user.last_name = data.last_name
    user.email = data.email
    user.phone_number = data.phone_number or None
    user.address = data.address or None
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, data: PasswordChange) -> None:
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect",
        )
    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Les mots de passe ne correspondent pas",
        )
    user.password_hash = hash_password(data.new_password)
    db.commit()


def create_user_with_hash(db: Session, data: dict) -> User:
    user = User(
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data["email"],
        phone_number=data.get("phone_number"),
        address=data.get("address"),
        password_hash=data["password_hash"],
        is_admin=False,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


MAX_LOGIN_ATTEMPTS = 3
LOCK_DURATION_MINUTES = 10


def authenticate_user(db: Session, email: str, password: str) -> tuple[User | None, str | None]:
    """Returns (user, error).

    error values:
      None          → success
      "invalid"     → wrong credentials or inactive
      "locked"      → account locked, lock window not yet elapsed
      "unlock_ready"→ account locked but 10-minute window has passed, OTP required
    """
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return None, "invalid"

    if user.is_locked:
        if user.locked_at:
            locked_at = user.locked_at.replace(tzinfo=timezone.utc) if user.locked_at.tzinfo is None else user.locked_at
            if datetime.now(timezone.utc) >= locked_at + timedelta(minutes=LOCK_DURATION_MINUTES):
                return user, "unlock_ready"
        return user, "locked"

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.is_locked = True
            user.locked_at = datetime.now(timezone.utc)
        db.commit()
        return None, "invalid"

    user.failed_login_attempts = 0
    db.commit()
    return user, None


def unlock_user(db: Session, user: User) -> None:
    user.is_locked = False
    user.failed_login_attempts = 0
    user.locked_at = None
    db.commit()
