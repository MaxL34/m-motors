from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.vehicle import VehicleStatus
from app.services.vehicle_service import get_vehicles

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def catalog(request: Request, db: Session = Depends(get_db)):
    vehicles = get_vehicles(db, status=VehicleStatus.ACTIVE)
    return templates.TemplateResponse(
        name="vehicles/catalog.html",
        request=request,
        context={"vehicles": vehicles}
)