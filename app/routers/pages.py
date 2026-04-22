from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.vehicle import FuelType, TransmissionType, VehicleStatus
from app.services.vehicle_service import get_vehicles

router = APIRouter(tags=["pages"])

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


@router.get("/", response_class=HTMLResponse)
def homepage(request: Request, db: Session = Depends(get_db)):
    vehicles = get_vehicles(db, status=VehicleStatus.ACTIVE)
    return templates.TemplateResponse(
        name="index.html",
        request=request,
        context={
            "vehicles": vehicles,
            "fuel_labels": FUEL_LABELS,
            "transmission_labels": TRANSMISSION_LABELS,
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(name="auth/login.html", request=request, context={})


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(name="auth/register.html", request=request, context={})
