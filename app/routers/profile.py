from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user_schema import PasswordChange, UserUpdate
from app.services.auth_service import change_password, update_user
from app.utils.deps import require_user

router = APIRouter(tags=["profile"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, current_user: User = Depends(require_user)):
    return templates.TemplateResponse(
        name="profile/index.html",
        request=request,
        context={"current_user": current_user, "success": None, "errors": [], "pwd_errors": [], "pwd_success": None},
    )


@router.post("/profile", response_class=HTMLResponse)
async def profile_update(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone_number: str = Form(""),
    address: str = Form(""),
):
    try:
        data = UserUpdate(
            first_name=first_name, last_name=last_name, email=email,
            phone_number=phone_number or None, address=address or None,
        )
        update_user(db, current_user, data)
        return templates.TemplateResponse(
            name="profile/index.html",
            request=request,
            context={"current_user": current_user, "success": "Profil mis à jour.", "errors": [], "pwd_errors": [], "pwd_success": None},
        )
    except ValidationError as e:
        errors = [err["msg"].replace("Value error, ", "") for err in e.errors()]
    except Exception as e:
        errors = [str(e.detail) if hasattr(e, "detail") else str(e)]
    return templates.TemplateResponse(
        name="profile/index.html",
        request=request,
        context={"current_user": current_user, "success": None, "errors": errors, "pwd_errors": [], "pwd_success": None},
        status_code=422,
    )


@router.post("/profile/password", response_class=HTMLResponse)
async def profile_password(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    try:
        data = PasswordChange(
            current_password=current_password,
            new_password=new_password,
            confirm_password=confirm_password,
        )
        change_password(db, current_user, data)
        return templates.TemplateResponse(
            name="profile/index.html",
            request=request,
            context={"current_user": current_user, "success": None, "errors": [], "pwd_errors": [], "pwd_success": "Mot de passe modifié."},
        )
    except ValidationError as e:
        pwd_errors = [err["msg"].replace("Value error, ", "") for err in e.errors()]
    except Exception as e:
        pwd_errors = [str(e.detail) if hasattr(e, "detail") else str(e)]
    return templates.TemplateResponse(
        name="profile/index.html",
        request=request,
        context={"current_user": current_user, "success": None, "errors": [], "pwd_errors": pwd_errors, "pwd_success": None},
        status_code=422,
    )
