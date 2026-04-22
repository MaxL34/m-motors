from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user_schema import UserCreate
from app.services.auth_service import authenticate_user, create_user
from app.utils.security import create_access_token

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

COOKIE_NAME = "access_token"


# ── Inscription ───────────────────────────────────────────────────────────────

@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    db: Session = Depends(get_db),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone_number: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
):
    form_data = {
        "first_name": first_name, "last_name": last_name,
        "email": email, "phone_number": phone_number, "address": address,
    }
    try:
        data = UserCreate(
            first_name=first_name, last_name=last_name, email=email,
            password=password, phone_number=phone_number or None,
            address=address or None,
        )
        create_user(db, data)
        return RedirectResponse(
            "/login?success=Compte+créé+avec+succès.+Connectez-vous.",
            status_code=303,
        )
    except ValidationError as e:
        errors = [err["msg"].replace("Value error, ", "") for err in e.errors()]
        return templates.TemplateResponse(
            name="auth/register.html",
            request=request,
            context={"errors": errors, "form_data": form_data},
            status_code=422,
        )
    except Exception as e:
        return templates.TemplateResponse(
            name="auth/register.html",
            request=request,
            context={"errors": [str(e.detail) if hasattr(e, "detail") else str(e)], "form_data": form_data},
            status_code=422,
        )


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
