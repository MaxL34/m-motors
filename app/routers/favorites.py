from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.favorite_service import toggle_favorite
from app.utils.deps import require_user

router = APIRouter(tags=["favorites"])


@router.post("/vehicles/{vehicle_id}/favorite")
def toggle(
    vehicle_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    toggle_favorite(db, current_user.id, vehicle_id)
    referer = request.headers.get("referer", f"/vehicles/{vehicle_id}")
    return RedirectResponse(referer, status_code=303)
