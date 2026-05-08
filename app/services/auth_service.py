from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user_schema import UserCreate, UserUpdate, PasswordChange
from app.utils.security import hash_password, verify_password

# Lockout policy constants — kept here so router and service share the same values.
MAX_LOGIN_ATTEMPTS = 3
LOCK_DURATION_MINUTES = 10


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return the user matching the given email, or None if not found."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Return the user matching the given primary key, or None if not found."""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, data: UserCreate) -> User:
    """Create and persist a new user from validated registration data.

    Raises HTTP 409 if the email is already taken.
    The plain-text password is hashed before storage.
    """
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


def create_user_with_hash(db: Session, data: dict) -> User:
    """Create a user from a dict that already contains a bcrypt password_hash.

    Used after OTP verification during registration, where the hash was
    computed before the OTP was sent and stored in the OTP JSON payload.
    """
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


def update_user(db: Session, user: User, data: UserUpdate) -> User:
    """Apply profile changes to an existing user.

    Raises HTTP 409 if the new email or phone number is already used by
    another account.
    """
    if data.email != user.email and get_user_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse e-mail est déjà utilisée",
        )
    if data.phone_number and data.phone_number != user.phone_number:
        existing = db.query(User).filter(User.phone_number == data.phone_number).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ce numéro de téléphone est déjà utilisé",
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
    """Update the user's password after verifying the current one.

    Raises HTTP 400 if the current password is wrong or the new passwords
    do not match.
    """
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


def authenticate_user(db: Session, email: str, password: str) -> tuple[User | None, str | None]:
    """Verify credentials and apply the account lockout policy.

    Returns (user, error) where error is one of:
      None           — success, user may log in
      "invalid"      — wrong credentials or inactive account
      "locked"       — account locked, lockout window not yet elapsed
      "unlock_ready" — locked but LOCK_DURATION_MINUTES have passed;
                       the caller should trigger an SMS OTP unlock flow
    """
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return None, "invalid"

    if user.is_locked:
        if user.locked_at:
            # Normalise to UTC in case the column lacks tzinfo (legacy rows).
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
    """Clear the lockout state after a successful SMS OTP verification."""
    user.is_locked = False
    user.failed_login_attempts = 0
    user.locked_at = None
    db.commit()


def reset_password(db: Session, user: User, new_password: str) -> None:
    """Replace the user's password hash and clear any active lockout.

    The lockout is cleared because the SMS OTP already proved identity;
    leaving the account locked after a successful reset would block the user.
    """
    user.password_hash = hash_password(new_password)
    user.is_locked = False
    user.failed_login_attempts = 0
    user.locked_at = None
    db.commit()


def delete_user(db: Session, user: User) -> None:
    """Soft-delete a user by marking the account inactive.

    The row is kept so that related records (client files, etc.) remain
    intact. An inactive account cannot log in.
    """
    user.is_active = False
    db.commit()
