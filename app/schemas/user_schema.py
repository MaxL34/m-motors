"""Pydantic schemas for user-related request validation."""
from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    """Validates the registration form payload.

    The password is validated here but stored only as a bcrypt hash —
    the plain-text value is never persisted.
    """

    first_name: str
    last_name: str
    email: EmailStr
    phone_number: str
    address: str | None = None
    password: str

    @field_validator("first_name", "last_name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Ce champ ne peut pas être vide")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caractères")
        return v


class UserLogin(BaseModel):
    """Credentials submitted on the login form."""

    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Validates the profile-update form payload.

    phone_number and address are optional — a user may clear them by
    submitting an empty string (the router converts "" to None before
    passing it here).
    """

    first_name: str
    last_name: str
    email: EmailStr
    phone_number: str | None = None
    address: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Ce champ ne peut pas être vide")
        return v.strip()


class PasswordChange(BaseModel):
    """Validates the change-password form payload.

    Matching between new_password and confirm_password is checked in
    auth_service.change_password rather than here, so the error message
    can be surfaced through the same HTTP exception path as other service
    errors.
    """

    current_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caractères")
        return v
