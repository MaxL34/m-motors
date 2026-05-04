import json
import random
import uuid
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.models.otp_code import OtpCode

_OTP_EXPIRY_MINUTES = 10
_MAX_ATTEMPTS = 3


def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def create_registration_otp(db: Session, registration_data: dict) -> OtpCode:
    otp = OtpCode(
        registration_json=json.dumps(registration_data),
        code=_generate_code(),
        pending_token=uuid.uuid4().hex,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=_OTP_EXPIRY_MINUTES),
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp


def send_otp_sms(phone_number: str, code: str) -> None:
    logger.warning(f"[DEV] OTP for {phone_number}: {code}")


def verify_registration_otp(
    db: Session, pending_token: str, code: str
) -> tuple[bool, str, dict | None]:
    """Validate a submitted registration OTP code.

    Returns (success, error_message, registration_data).
    """
    otp = db.query(OtpCode).filter(OtpCode.pending_token == pending_token).first()

    if not otp or otp.used:
        return False, "Session invalide. Veuillez recommencer l'inscription.", None

    if datetime.now(timezone.utc) > otp.expires_at.replace(tzinfo=timezone.utc):
        return False, "Le code a expiré. Veuillez recommencer l'inscription.", None

    if otp.attempts >= _MAX_ATTEMPTS:
        return False, "Trop de tentatives. Veuillez recommencer l'inscription.", None

    otp.attempts += 1

    if otp.code != code.strip():
        db.commit()
        remaining = _MAX_ATTEMPTS - otp.attempts
        if remaining > 0:
            return False, f"Code incorrect. {remaining} tentative(s) restante(s).", None
        return False, "Trop de tentatives. Veuillez recommencer l'inscription.", None

    otp.used = True
    db.commit()
    return True, "", json.loads(otp.registration_json)


def create_unlock_otp(db: Session, user_id: int) -> OtpCode:
    from sqlalchemy import or_
    db.query(OtpCode).filter(
        OtpCode.user_id == user_id,
        OtpCode.used.is_(False),
        or_(OtpCode.purpose == "unlock", OtpCode.purpose.is_(None)),
    ).delete(synchronize_session=False)
    otp = OtpCode(
        user_id=user_id,
        purpose="unlock",
        code=_generate_code(),
        pending_token=uuid.uuid4().hex,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=_OTP_EXPIRY_MINUTES),
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp


def verify_unlock_otp(
    db: Session, pending_token: str, code: str
) -> tuple[bool, str, int | None]:
    """Validate a submitted unlock OTP code.

    Returns (success, error_message, user_id).
    """
    from sqlalchemy import or_
    otp = (
        db.query(OtpCode)
        .filter(
            OtpCode.pending_token == pending_token,
            or_(OtpCode.purpose == "unlock", OtpCode.purpose.is_(None)),
        )
        .first()
    )

    if not otp or otp.used:
        return False, "Session invalide. Veuillez vous reconnecter.", None

    if datetime.now(timezone.utc) > otp.expires_at.replace(tzinfo=timezone.utc):
        return False, "Le code a expiré. Veuillez vous reconnecter.", None

    if otp.attempts >= _MAX_ATTEMPTS:
        return False, "Trop de tentatives. Veuillez vous reconnecter.", None

    otp.attempts += 1

    if otp.code != code.strip():
        db.commit()
        remaining = _MAX_ATTEMPTS - otp.attempts
        if remaining > 0:
            return False, f"Code incorrect. {remaining} tentative(s) restante(s).", None
        return False, "Trop de tentatives. Veuillez vous reconnecter.", None

    otp.used = True
    db.commit()
    return True, "", otp.user_id


def create_reset_otp(db: Session, user_id: int) -> OtpCode:
    db.query(OtpCode).filter(
        OtpCode.user_id == user_id,
        OtpCode.used.is_(False),
        OtpCode.purpose == "reset",
    ).delete(synchronize_session=False)
    otp = OtpCode(
        user_id=user_id,
        purpose="reset",
        code=_generate_code(),
        pending_token=uuid.uuid4().hex,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=_OTP_EXPIRY_MINUTES),
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp


def verify_reset_otp(
    db: Session, pending_token: str, code: str
) -> tuple[bool, str, int | None]:
    """Validate a submitted password-reset OTP code.

    Returns (success, error_message, user_id).
    """
    otp = (
        db.query(OtpCode)
        .filter(
            OtpCode.pending_token == pending_token,
            OtpCode.purpose == "reset",
        )
        .first()
    )

    if not otp or otp.used:
        return False, "Session invalide. Veuillez recommencer.", None

    if datetime.now(timezone.utc) > otp.expires_at.replace(tzinfo=timezone.utc):
        return False, "Le code a expiré. Veuillez recommencer.", None

    if otp.attempts >= _MAX_ATTEMPTS:
        return False, "Trop de tentatives. Veuillez recommencer.", None

    otp.attempts += 1

    if otp.code != code.strip():
        db.commit()
        remaining = _MAX_ATTEMPTS - otp.attempts
        if remaining > 0:
            return False, f"Code incorrect. {remaining} tentative(s) restante(s).", None
        return False, "Trop de tentatives. Veuillez recommencer.", None

    otp.used = True
    db.commit()
    return True, "", otp.user_id
