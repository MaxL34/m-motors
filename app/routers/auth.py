from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user_schema import UserCreate
from app.services.auth_service import authenticate_user, create_user_with_hash, get_user_by_email
from app.services.otp_service import create_registration_otp, send_otp_sms, verify_registration_otp
from app.utils.security import create_access_token, hash_password

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

COOKIE_NAME = "access_token"
PENDING_COOKIE_NAME = "pending_otp_token"


# ── Inscription ───────────────────────────────────────────────────────────────

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


# ── Vérification OTP (inscription) ───────────────────────────────────────────

@router.get("/register/verify", response_class=HTMLResponse)
async def get_verify_registration(request: Request):
    if not request.cookies.get(PENDING_COOKIE_NAME):
        return RedirectResponse("/register", status_code=303)
    return templates.TemplateResponse(name="auth/verify_otp.html", request=request)


@router.post("/register/verify", response_class=HTMLResponse)
async def post_verify_registration(
    request: Request,
    db: Session = Depends(get_db),
    code: str = Form(...),
):
    pending_token = request.cookies.get(PENDING_COOKIE_NAME)
    if not pending_token:
        return RedirectResponse("/register", status_code=303)

    success, error_msg, registration_data = verify_registration_otp(db, pending_token, code)

    if not success:
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
        create_user_with_hash(db, registration_data)
    except Exception as e:
        response = RedirectResponse("/register", status_code=303)
        response.delete_cookie(PENDING_COOKIE_NAME)
        return response

    response = RedirectResponse(
        "/login?success=Compte+créé+avec+succès.+Connectez-vous.",
        status_code=303,
    )
    response.delete_cookie(PENDING_COOKIE_NAME)
    return response


# ── Connexion utilisateur ─────────────────────────────────────────────────────

@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
):
    user = authenticate_user(db, email, password)
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
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return response


# ── Connexion admin ───────────────────────────────────────────────────────────

@router.post("/admin/login", response_class=HTMLResponse)
async def admin_login(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
):
    user = authenticate_user(db, email, password)
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


# ── Déconnexion ───────────────────────────────────────────────────────────────

@router.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
