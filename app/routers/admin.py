from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.vehicle import FuelType, TransmissionType, VehicleStatus
from app.schemas.vehicle_schema import VehicleCreate, VehicleDeactivate, VehicleUpdate
from app.services.vehicle_service import (
    activate_vehicle,
    create_vehicle,
    deactivate_vehicle,
    get_vehicle,
    get_vehicles,
    update_vehicle,
)
from app.utils.deps import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])
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
    return {
        "fuel_labels": FUEL_LABELS,
        "transmission_labels": TRANSMISSION_LABELS,
        "fuel_types": list(FuelType),
        "transmission_types": list(TransmissionType),
        **kwargs,
    }


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value and value.strip():
        return float(value)
    return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value and value.strip():
        return int(value)
    return None


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/vehicles", response_class=HTMLResponse)
def admin_vehicles_list(
    request: Request,
    db: Session = Depends(get_db),
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    current_admin: User = Depends(require_admin),
):
    if sort_by not in ("brand", "created_at"):
        sort_by = "created_at"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"
    status_enum = VehicleStatus(status_filter) if status_filter in VehicleStatus._value2member_map_ else None
    vehicles = get_vehicles(db, status=status_enum, search=search, sort_by=sort_by, sort_order=sort_order)
    all_vehicles = get_vehicles(db)
    counts = {
        "total": len(all_vehicles),
        "active": sum(1 for v in all_vehicles if v.status == VehicleStatus.ACTIVE),
        "inactive": sum(1 for v in all_vehicles if v.status == VehicleStatus.INACTIVE),
    }
    return templates.TemplateResponse(
        name="admin/vehicles/list.html",
        request=request,
        context=_ctx(
            vehicles=vehicles,
            status_filter=status_filter,
            search=search,
            counts=counts,
            sort_by=sort_by,
            sort_order=sort_order,
        ),
    )


# ── Create ────────────────────────────────────────────────────────────────────

@router.get("/vehicles/new", response_class=HTMLResponse)
def admin_vehicle_new(request: Request, current_admin: User = Depends(require_admin)):
    return templates.TemplateResponse(
        name="admin/vehicles/form.html",
        request=request,
        context=_ctx(vehicle=None, errors=[], form_data={}),
    )


@router.post("/vehicles", response_class=HTMLResponse)
async def admin_vehicle_create(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
    vin: str = Form(...),
    licence_plate: str = Form(...),
    brand: str = Form(...),
    model: str = Form(...),
    year: str = Form(...),
    fuel_type: str = Form(...),
    transmission_type: str = Form(...),
    mileage: str = Form(...),
    engine_power: Optional[str] = Form(None),
    is_for_sale: str = Form(...),
    selling_price: Optional[str] = Form(None),
    monthly_rental_price: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    form_data = {
        "vin": vin, "licence_plate": licence_plate, "brand": brand,
        "model": model, "year": year, "fuel_type": fuel_type,
        "transmission_type": transmission_type, "mileage": mileage,
        "engine_power": engine_power, "is_for_sale": is_for_sale,
        "selling_price": selling_price, "monthly_rental_price": monthly_rental_price,
        "color": color, "description": description,
    }
    try:
        data = VehicleCreate(
            vin=vin,
            licence_plate=licence_plate,
            brand=brand,
            model=model,
            year=int(year),
            fuel_type=FuelType(fuel_type),
            transmission_type=TransmissionType(transmission_type),
            mileage=int(mileage),
            engine_power=_parse_int(engine_power),
            is_for_sale=is_for_sale == "true",
            selling_price=_parse_float(selling_price),
            monthly_rental_price=_parse_float(monthly_rental_price),
            color=color or None,
            description=description or None,
        )
        vehicle = create_vehicle(db, data)
        return RedirectResponse(
            f"/admin/vehicles/{vehicle.id}?success=Véhicule+créé+avec+succès",
            status_code=303,
        )
    except ValidationError as e:
        errors = [{"msg": err["msg"], "loc": " → ".join(str(l) for l in err["loc"])} for err in e.errors()]
        return templates.TemplateResponse(
            name = "admin/vehicles/form.html",
            request=request,
            context=_ctx(vehicle=None, errors=errors, form_data=form_data),
            status_code=422,
        )
    except Exception as e:
        return templates.TemplateResponse(
            name="admin/vehicles/form.html",
            request=request,
            context=_ctx(vehicle=None, errors=[{"msg": str(e), "loc": ""}], form_data=form_data),
            status_code=422,
        )


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/vehicles/{vehicle_id}", response_class=HTMLResponse)
def admin_vehicle_detail(
    request: Request,
    vehicle_id: int,
    db: Session = Depends(get_db),
    success: Optional[str] = None,
    error: Optional[str] = None,
    current_admin: User = Depends(require_admin),
):
    vehicle = get_vehicle(db, vehicle_id)
    return templates.TemplateResponse(
        name="admin/vehicles/detail.html",
        request=request,
        context=_ctx(vehicle=vehicle, success=success, error=error),
    )


# ── Edit ──────────────────────────────────────────────────────────────────────

@router.get("/vehicles/{vehicle_id}/edit", response_class=HTMLResponse)
def admin_vehicle_edit_form(
    request: Request,
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    vehicle = get_vehicle(db, vehicle_id)
    return templates.TemplateResponse(
        name="admin/vehicles/form.html",
        request=request,
        context=_ctx(vehicle=vehicle, errors=[], form_data={}),
    )


@router.post("/vehicles/{vehicle_id}/edit", response_class=HTMLResponse)
async def admin_vehicle_edit(
    request: Request,
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
    licence_plate: Optional[str] = Form(None),
    brand: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    fuel_type: Optional[str] = Form(None),
    transmission_type: Optional[str] = Form(None),
    mileage: Optional[str] = Form(None),
    engine_power: Optional[str] = Form(None),
    is_for_sale: Optional[str] = Form(None),
    selling_price: Optional[str] = Form(None),
    monthly_rental_price: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    vehicle = get_vehicle(db, vehicle_id)
    form_data = {
        "licence_plate": licence_plate, "brand": brand, "model": model,
        "year": year, "fuel_type": fuel_type, "transmission_type": transmission_type,
        "mileage": mileage, "engine_power": engine_power, "is_for_sale": is_for_sale,
        "selling_price": selling_price, "monthly_rental_price": monthly_rental_price,
        "color": color, "description": description,
    }
    try:
        data = VehicleUpdate(
            licence_plate=licence_plate or None,
            brand=brand or None,
            model=model or None,
            year=_parse_int(year),
            fuel_type=FuelType(fuel_type) if fuel_type else None,
            transmission_type=TransmissionType(transmission_type) if transmission_type else None,
            mileage=_parse_int(mileage),
            engine_power=_parse_int(engine_power),
            is_for_sale=is_for_sale == "true" if is_for_sale is not None else None,
            selling_price=_parse_float(selling_price),
            monthly_rental_price=_parse_float(monthly_rental_price),
            color=color or None,
            description=description or None,
        )
        update_vehicle(db, vehicle_id, data)
        return RedirectResponse(
            f"/admin/vehicles/{vehicle_id}?success=Véhicule+mis+à+jour",
            status_code=303,
        )
    except ValidationError as e:
        errors = [{"msg": err["msg"], "loc": " → ".join(str(l) for l in err["loc"])} for err in e.errors()]
        return templates.TemplateResponse(
            name="admin/vehicles/form.html",
            request=request,
            context=_ctx(vehicle=vehicle, errors=errors, form_data=form_data),
            status_code=422,
        )
    except Exception as e:
        return templates.TemplateResponse(
            name="admin/vehicles/form.html",
            request=request,
            context=_ctx(vehicle=vehicle, errors=[{"msg": str(e), "loc": ""}], form_data=form_data),
            status_code=422,
        )


# ── Activate / Deactivate ─────────────────────────────────────────────────────

@router.post("/vehicles/{vehicle_id}/activate")
def admin_vehicle_activate(vehicle_id: int, db: Session = Depends(get_db), current_admin: User = Depends(require_admin)):
    try:
        activate_vehicle(db, vehicle_id)
        return RedirectResponse(
            f"/admin/vehicles/{vehicle_id}?success=Véhicule+activé+avec+succès",
            status_code=303,
        )
    except Exception as e:
        return RedirectResponse(
            f"/admin/vehicles/{vehicle_id}?error={str(e)}",
            status_code=303,
        )


@router.post("/vehicles/{vehicle_id}/deactivate")
async def admin_vehicle_deactivate(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
    deactivation_reason: str = Form(...),
):
    try:
        deactivate_vehicle(db, vehicle_id, VehicleDeactivate(deactivation_reason=deactivation_reason))
        return RedirectResponse(
            f"/admin/vehicles/{vehicle_id}?success=Véhicule+désactivé",
            status_code=303,
        )
    except Exception as e:
        return RedirectResponse(
            f"/admin/vehicles/{vehicle_id}?error={str(e)}",
            status_code=303,
        )
