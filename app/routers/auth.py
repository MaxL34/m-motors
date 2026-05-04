"""Authentication router — registration, login, OTP flows, password reset."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user_schema import UserCreate
from app.services.auth_service import (
    authenticate_user,
    create_user_with_hash,
    get_user_by_email,
    get_user_by_id,
    reset_password,
    unlock_user,
)
from app.services.email_service import send_confirmation_email
from app.services.otp_service import (
    create_registration_otp,
    create_reset_otp,
    create_unlock_otp,
    send_otp_sms,
    verify_registration_otp,
    verify_reset_otp,
    verify_unlock_otp,
)
from app.utils.security import create_access_token, hash_password

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

# Cookie names — centralised here to avoid magic strings across handlers.
COOKIE_NAME = "access_token"
PENDING_COOKIE_NAME = "pending_otp_token"   # registration OTP session
UNLOCK_COOKIE_NAME = "unlock_otp_token"     # account-unlock OTP session
RESET_OTP_COOKIE = "reset_otp_token"        # password-reset OTP session
RESET_ACCESS_COOKIE = "reset_access_token"  # short-lived JWT after OTP verified


# ── Registration ──────────────────────────────────────────────────────────────

@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    db: Session = Depends(get_db),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone_number: str = Form(...),
    address: Optional[str] = Form(None),
):
    """Validate the registration form, create an OTP and redirect to verify.

    The user row is NOT created yet — it is held in the OTP payload until
    the SMS code is confirmed.
    """
    form_data = {
        "first_name": first_name, "last_name": last_name,
        "email": email, "phone_number": phone_number, "address": address,
    }
    try:
        data = UserCreate(
            first_name=first_name, last_name=last_name, email=email,
            password=password, phone_number=phone_number,
            address=address or None,
        )
    except ValidationError as e:
        errors = [err["msg"].replace("Value error, ", "") for err in e.errors()]
        return templates.TemplateResponse(
            name="auth/register.html",
            request=request,
            context={"errors": errors, "form_data": form_data},
            status_code=422,
        )

    if get_user_by_email(db, data.email):
        return templates.TemplateResponse(
            name="auth/register.html",
            request=request,
            context={"errors": ["Un compte existe déjà avec cette adresse e-mail"], "form_data": form_data},
            status_code=422,
        )

    if db.query(User).filter(User.phone_number == data.phone_number).first():
        return templates.TemplateResponse(
            name="auth/register.html",
            request=request,
            context={"errors": ["Ce numéro de téléphone est déjà associé à un compte"], "form_data": form_data},
            status_code=422,
        )

    # Hash the password now so it is never stored in plain text, even temporarily.
    registration_data = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "address": data.address,
        "password_hash": hash_password(data.password),
    }
    otp = create_registration_otp(db, registration_data)
    try:
        send_otp_sms(data.phone_number, otp.code)
    except Exception as exc:
        logger.error(f"OTP SMS send failed during registration: {exc}")
        return templates.TemplateResponse(
            name="auth/register.html",
            request=request,
            context={"errors": ["Impossible d'envoyer le SMS de vérification. Réessayez."], "form_data": form_data},
            status_code=503,
        )
    response = RedirectResponse("/register/verify", status_code=303)
    response.set_cookie(
        PENDING_COOKIE_NAME, otp.pending_token,
        httponly=True, samesite="lax", max_age=600,
    )
    return response


# ── Registration OTP verification ─────────────────────────────────────────────

@router.get("/register/verify", response_class=HTMLResponse)
async def get_verify_registration(request: Request):
    """Show the OTP form. Redirect to /register if the session cookie is missing."""
    if not request.cookies.get(PENDING_COOKIE_NAME):
        return RedirectResponse("/register", status_code=303)
    return templates.TemplateResponse(name="auth/verify_otp.html", request=request)


@router.post("/register/verify", response_class=HTMLResponse)
async def post_verify_registration(
    request: Request,
    db: Session = Depends(get_db),
    code: str = Form(...),
):
    """Verify the registration OTP and create the user account on success."""
    pending_token = request.cookies.get(PENDING_COOKIE_NAME)
    if not pending_token:
        return RedirectResponse("/register", status_code=303)

    success, error_msg, registration_data = verify_registration_otp(db, pending_token, code)

    if not success:
        # "recommencer" signals a terminal error (expired / exhausted) — restart the flow.
        if "recommencer" in error_msg:
            response = RedirectResponse(
                f"/register?error={error_msg.replace(' ', '+')}",
                status_code=303,
            )
            response.delete_cookie(PENDING_COOKIE_NAME)
            return response
        return templates.TemplateResponse(
            name="auth/verify_otp.html",
            request=request,
            context={"error": error_msg},
            status_code=422,
        )

    try:
        user = create_user_with_hash(db, registration_data)
        send_confirmation_email(user.email, user.first_name)
    except Exception as e:
        logger.error(f"User creation failed after OTP verification: {e}", exc_info=True)
        db.rollback()
        response = RedirectResponse(
            "/register?error=Une+erreur+est+survenue+lors+de+la+création+du+compte.+Veuillez+réessayer.",
            status_code=303,
        )
        response.delete_cookie(PENDING_COOKIE_NAME)
        return response

    response = RedirectResponse(
        "/login?success=Compte+créé+avec+succès.+Connectez-vous.",
        status_code=303,
    )
    response.delete_cookie(PENDING_COOKIE_NAME)
    return response


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
):
    """Authenticate a regular user and issue a session cookie.

    Handles three special cases before issuing the token:
    - locked + window elapsed → redirect to OTP unlock flow
    - locked + window not elapsed → show wait message
    - admin trying the user route → redirect to admin login
    """
    user, error = authenticate_user(db, email, password)
    if error == "unlock_ready":
        otp = create_unlock_otp(db, user.id)
        try:
            send_otp_sms(user.phone_number, otp.code)
        except Exception as exc:
            logger.error(f"OTP SMS send failed during unlock: {exc}")
        response = RedirectResponse("/login/unlock", status_code=303)
        response.set_cookie(
            UNLOCK_COOKIE_NAME, otp.pending_token,
            httponly=True, samesite="lax", max_age=600,
        )
        return response
    if error == "locked":
        remaining_minutes = 10
        if user and user.locked_at:
            locked_at = user.locked_at.replace(tzinfo=timezone.utc) if user.locked_at.tzinfo is None else user.locked_at
            elapsed = datetime.now(timezone.utc) - locked_at
            remaining = timedelta(minutes=10) - elapsed
            remaining_minutes = max(1, int(remaining.total_seconds() / 60) + 1)
        return templates.TemplateResponse(
            name="auth/login.html",
            request=request,
            context={
                "error": f"Votre compte est temporairement bloqué. Réessayez dans {remaining_minutes} minute(s).",
                "form_email": email,
            },
            status_code=403,
        )
    if not user:
        return templates.TemplateResponse(
            name="auth/login.html",
            request=request,
            context={"error": "E-mail ou mot de passe incorrect.", "form_email": email},
            status_code=401,
        )
    if user.is_admin:
        return templates.TemplateResponse(
            name="auth/login.html",
            request=request,
            context={"error": "Utilisez l'espace admin pour vous connecter.", "form_email": email},
            status_code=403,
        )

    token = create_access_token({"sub": str(user.id), "is_admin": False})
    response = RedirectResponse("/vehicles", status_code=303)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return response


# ── Account unlock via OTP ────────────────────────────────────────────────────

@router.get("/login/unlock", response_class=HTMLResponse)
async def get_unlock(request: Request):
    """Show the unlock OTP form. Redirect to /login if the session cookie is missing."""
    if not request.cookies.get(UNLOCK_COOKIE_NAME):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(name="auth/unlock_otp.html", request=request)


@router.post("/login/unlock", response_class=HTMLResponse)
async def post_unlock(
    request: Request,
    db: Session = Depends(get_db),
    code: str = Form(...),
):
    """Verify the unlock OTP and log the user in directly on success."""
    pending_token = request.cookies.get(UNLOCK_COOKIE_NAME)
    if not pending_token:
        return RedirectResponse("/login", status_code=303)

    success, error_msg, user_id = verify_unlock_otp(db, pending_token, code)

    if not success:
        # Errors without "restante(s)" are terminal — restart from login.
        if "restante(s)" not in error_msg:
            response = RedirectResponse("/login", status_code=303)
            response.delete_cookie(UNLOCK_COOKIE_NAME)
            return response
        return templates.TemplateResponse(
            name="auth/unlock_otp.html",
            request=request,
            context={"error": error_msg},
            status_code=422,
        )

    user = db.get(User, user_id)
    if not user:
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(UNLOCK_COOKIE_NAME)
        return response

    unlock_user(db, user)

    token = create_access_token({"sub": str(user.id), "is_admin": False})
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    response.delete_cookie(UNLOCK_COOKIE_NAME)
    return response


# ── Admin login ───────────────────────────────────────────────────────────────

@router.post("/admin/login", response_class=HTMLResponse)
async def admin_login(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
):
    """Authenticate an admin user. Rejects non-admin credentials."""
    user, error = authenticate_user(db, email, password)
    if not user or not user.is_admin:
        return templates.TemplateResponse(
            name="auth/admin_login.html",
            request=request,
            context={"error": "Identifiants invalides ou accès non autorisé.", "form_email": email},
            status_code=401,
        )
    token = create_access_token({"sub": str(user.id), "is_admin": True})
    response = RedirectResponse("/admin/vehicles", status_code=303)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return response


# ── Password reset ────────────────────────────────────────────────────────────

@router.get("/forgot-password", response_class=HTMLResponse)
async def get_forgot_password(request: Request):
    """Show the forgot-password email form."""
    return templates.TemplateResponse(name="auth/forgot_password.html", request=request, context={})


@router.post("/forgot-password", response_class=HTMLResponse)
async def post_forgot_password(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
):
    """Look up the account, send a reset OTP by SMS, and redirect to verification.

    Returns 404 for unknown / inactive emails and 422 when the account has
    no phone number on file (OTP cannot be delivered).
    """
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return templates.TemplateResponse(
            name="auth/forgot_password.html",
            request=request,
            context={"error": "Aucun compte actif n'est associé à cette adresse e-mail."},
            status_code=404,
        )
    if not user.phone_number:
        return templates.TemplateResponse(
            name="auth/forgot_password.html",
            request=request,
            context={"error": "Aucun numéro de téléphone n'est associé à ce compte. Contactez le support."},
            status_code=422,
        )

    otp = create_reset_otp(db, user.id)
    try:
        send_otp_sms(user.phone_number, otp.code)
    except Exception as exc:
        logger.error(f"OTP SMS send failed during password reset: {exc}")
        return templates.TemplateResponse(
            name="auth/forgot_password.html",
            request=request,
            context={"error": "Impossible d'envoyer le SMS de vérification. Réessayez."},
            status_code=503,
        )

    response = RedirectResponse("/forgot-password/verify", status_code=303)
    response.set_cookie(
        RESET_OTP_COOKIE, otp.pending_token,
        httponly=True, samesite="lax", max_age=600,
    )
    return response


@router.get("/forgot-password/verify", response_class=HTMLResponse)
async def get_reset_verify(request: Request):
    """Show the reset OTP form. Redirect if the session cookie is missing."""
    if not request.cookies.get(RESET_OTP_COOKIE):
        return RedirectResponse("/forgot-password", status_code=303)
    return templates.TemplateResponse(name="auth/reset_otp.html", request=request, context={})


@router.post("/forgot-password/verify", response_class=HTMLResponse)
async def post_reset_verify(
    request: Request,
    db: Session = Depends(get_db),
    code: str = Form(...),
):
    """Verify the reset OTP and issue a short-lived reset_access_token on success.

    The reset_access_token is a JWT (5 min TTL) carrying the user id and a
    purpose claim. It gates the final password-change step without relying on
    additional server-side state.
    """
    pending_token = request.cookies.get(RESET_OTP_COOKIE)
    if not pending_token:
        return RedirectResponse("/forgot-password", status_code=303)

    success, error_msg, user_id = verify_reset_otp(db, pending_token, code)

    if not success:
        # Errors without "restante" are terminal — restart the reset flow.
        if "restante" not in error_msg:
            response = RedirectResponse("/forgot-password", status_code=303)
            response.delete_cookie(RESET_OTP_COOKIE)
            return response
        return templates.TemplateResponse(
            name="auth/reset_otp.html",
            request=request,
            context={"error": error_msg},
            status_code=422,
        )

    reset_token = create_access_token(
        {"sub": str(user_id), "purpose": "password_reset"},
        expires_delta=timedelta(minutes=5),
    )
    response = RedirectResponse("/reset-password", status_code=303)
    response.set_cookie(
        RESET_ACCESS_COOKIE, reset_token,
        httponly=True, samesite="lax", max_age=300,
    )
    response.delete_cookie(RESET_OTP_COOKIE)
    return response


@router.get("/reset-password", response_class=HTMLResponse)
async def get_reset_password(request: Request):
    """Show the new-password form, guarded by the reset_access_token cookie."""
    from app.utils.security import decode_access_token
    token = request.cookies.get(RESET_ACCESS_COOKIE)
    if not token:
        return RedirectResponse("/forgot-password", status_code=303)
    payload = decode_access_token(token)
    if not payload or payload.get("purpose") != "password_reset":
        response = RedirectResponse("/forgot-password", status_code=303)
        response.delete_cookie(RESET_ACCESS_COOKIE)
        return response
    return templates.TemplateResponse(name="auth/reset_password.html", request=request, context={})


@router.post("/reset-password", response_class=HTMLResponse)
async def post_reset_password(
    request: Request,
    db: Session = Depends(get_db),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    """Apply the new password after validating the reset_access_token and inputs."""
    from app.utils.security import decode_access_token, hash_password
    token = request.cookies.get(RESET_ACCESS_COOKIE)
    if not token:
        return RedirectResponse("/forgot-password", status_code=303)

    payload = decode_access_token(token)
    if not payload or payload.get("purpose") != "password_reset":
        response = RedirectResponse("/forgot-password", status_code=303)
        response.delete_cookie(RESET_ACCESS_COOKIE)
        return response

    errors = []
    if len(new_password) < 8:
        errors.append("Le mot de passe doit contenir au moins 8 caractères.")
    if new_password != confirm_password:
        errors.append("Les mots de passe ne correspondent pas.")
    if errors:
        return templates.TemplateResponse(
            name="auth/reset_password.html",
            request=request,
            context={"errors": errors},
            status_code=422,
        )

    user = get_user_by_id(db, int(payload["sub"]))
    if not user or not user.is_active:
        response = RedirectResponse("/forgot-password", status_code=303)
        response.delete_cookie(RESET_ACCESS_COOKIE)
        return response

    reset_password(db, user, new_password)

    response = RedirectResponse(
        "/login?success=Mot+de+passe+réinitialisé.+Connectez-vous.",
        status_code=303,
    )
    response.delete_cookie(RESET_ACCESS_COOKIE)
    return response


# ── Logout ────────────────────────────────────────────────────────────────────

@router.get("/logout")
def logout():
    """Clear the session cookie and redirect to the homepage."""
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
