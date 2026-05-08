from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class OtpCode(Base):
    """A single-use 6-digit OTP code sent by SMS.

    Three flows share this table, distinguished by the purpose field:
    - "registration": user_id is NULL, registration_json holds the pending
      account data serialised as JSON. The user row is only created after
      the code is verified.
    - "unlock": user_id references the locked account. Issued when the
      lockout window has elapsed and the user attempts to log in again.
    - "reset": user_id references the account whose password is being reset.

    A code expires after OTP_EXPIRY_MINUTES and is blocked after
    MAX_ATTEMPTS wrong guesses. Once verified, used is set to True so the
    same code cannot be replayed.
    """

    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # NULL for registration OTPs — the user does not exist yet at that point.
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Populated only for registration OTPs; NULL for unlock and reset.
    registration_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    # UUID token stored in a short-lived cookie to tie the browser session
    # to this specific OTP row without exposing the numeric code in the URL.
    pending_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # "registration" | "unlock" | "reset" — NULL for legacy rows (treated as "unlock").
    purpose: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
