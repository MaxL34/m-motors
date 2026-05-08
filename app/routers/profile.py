"""Profile router — personal information, password change, account deletion."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user_schema import PasswordChange, UserUpdate
from app.services.auth_service import change_password, delete_user, update_user
from app.utils.deps import require_user

router = APIRouter(tags=["profile"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, current_user: User = Depends(require_user)):
    """Render the profile page with empty error/success state."""
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
    """Validate and apply profile changes. Re-render the form with errors on failure."""
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
    """Change the user's password after verifying the current one."""
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


@router.post("/profile/delete", response_class=HTMLResponse)
async def profile_delete(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Soft-delete the account, clear the session cookie, and redirect home."""
    delete_user(db, current_user)
    response = RedirectResponse("/?account_deleted=1", status_code=303)
    response.delete_cookie("access_token")
    return response
