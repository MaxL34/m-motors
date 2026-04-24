from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.vehicle import FuelType, TransmissionType, VehicleStatus
from app.services.favorite_service import is_favorite
from app.services.vehicle_service import get_vehicle, get_vehicles
from app.utils.deps import get_current_user

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

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


def _ctx(**kwargs):
    return {"fuel_labels": FUEL_LABELS, "transmission_labels": TRANSMISSION_LABELS, **kwargs}


@router.get("", response_class=HTMLResponse)
def catalog(
    request: Request,
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    type_filter: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user),
):
    is_for_sale = None
    if type_filter == "sale":
        is_for_sale = True
    elif type_filter == "rental":
        is_for_sale = False

    vehicles = get_vehicles(db, status=VehicleStatus.ACTIVE, search=search, is_for_sale=is_for_sale)
    return templates.TemplateResponse(
        name="vehicles/catalog.html",
        request=request,
        context=_ctx(vehicles=vehicles, search=search, type_filter=type_filter, current_user=current_user),
    )


@router.get("/{vehicle_id}", response_class=HTMLResponse)
def vehicle_detail(
    request: Request,
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    vehicle = get_vehicle(db, vehicle_id)
    fav = is_favorite(db, current_user.id, vehicle_id) if current_user else False
    return templates.TemplateResponse(
        name="vehicles/detail.html",
        request=request,
        context=_ctx(vehicle=vehicle, current_user=current_user, is_favorite=fav),
    )
