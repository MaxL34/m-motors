from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.vehicle import FuelType, TransmissionType
from app.services.favorite_service import get_favorites, toggle_favorite
from app.utils.deps import require_user

router = APIRouter(tags=["favorites"])
templates = Jinja2Templates(directory="app/templates")

FUEL_LABELS = {
    FuelType.PETROL: "Essence",
    FuelType.DIESEL: "Diesel",
    FuelType.HYBRID: "Hybride",
    FuelType.ELECTRIC: "Électrique",
    FuelType.LPG: "GPL",
}

TRANSMISSION_LABELS = {
    TransmissionType.MANUAL: "Manuelle",
    TransmissionType.AUTOMATIC: "Automatique",
    TransmissionType.SEMI_AUTOMATIC: "Semi-automatique",
}


@router.get("/favorites", response_class=HTMLResponse)
def favorites_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    favorites = get_favorites(db, current_user.id)
    return templates.TemplateResponse(
        name="favorites/index.html",
        request=request,
        context={
            "current_user": current_user,
            "favorites": favorites,
            "fuel_labels": FUEL_LABELS,
            "transmission_labels": TRANSMISSION_LABELS,
        },
    )


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
