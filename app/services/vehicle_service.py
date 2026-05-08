from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.vehicle import Vehicle, VehicleStatus, VehicleStatusHistory, StatusAction
from app.schemas.vehicle_schema import VehicleCreate, VehicleUpdate, VehicleDeactivate


def create_vehicle(db: Session, data: VehicleCreate) -> Vehicle:
    vehicle = Vehicle(
        **data.model_dump(),
        status=VehicleStatus.INACTIVE,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def get_vehicle(db: Session, vehicle_id: int) -> Vehicle:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Véhicule introuvable")
    return vehicle


def get_vehicles(
    db: Session,
    status: VehicleStatus | None = None,
    is_for_sale: bool | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> list[Vehicle]:
    query = db.query(Vehicle)
    if status is not None:
        query = query.filter(Vehicle.status == status)
    if is_for_sale is not None:
        query = query.filter(Vehicle.is_for_sale == is_for_sale)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Vehicle.brand.ilike(term),
                Vehicle.model.ilike(term),
                Vehicle.vin.ilike(term),
                Vehicle.licence_plate.ilike(term),
            )
        )
    sort_col = Vehicle.brand if sort_by == "brand" else Vehicle.created_at
    query = query.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())
    return query.all()


def update_vehicle(db: Session, vehicle_id: int, data: VehicleUpdate) -> Vehicle:
    vehicle = get_vehicle(db, vehicle_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def activate_vehicle(db: Session, vehicle_id: int) -> Vehicle:
    vehicle = get_vehicle(db, vehicle_id)
    if vehicle.status == VehicleStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Le véhicule est déjà actif")
    vehicle.status = VehicleStatus.ACTIVE
    vehicle.deactivation_reason = None
    vehicle.deactivated_at = None
    db.add(VehicleStatusHistory(vehicle_id=vehicle_id, action=StatusAction.ACTIVATED))
    db.commit()
    db.refresh(vehicle)
    return vehicle


def deactivate_vehicle(db: Session, vehicle_id: int, data: VehicleDeactivate) -> Vehicle:
    vehicle = get_vehicle(db, vehicle_id)
    if vehicle.status == VehicleStatus.INACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Le véhicule est déjà inactif")
    vehicle.status = VehicleStatus.INACTIVE
    vehicle.deactivation_reason = data.deactivation_reason
    vehicle.deactivated_at = datetime.now(timezone.utc)
    db.add(VehicleStatusHistory(vehicle_id=vehicle_id, action=StatusAction.DEACTIVATED, reason=data.deactivation_reason))
    db.commit()
    db.refresh(vehicle)
    return vehicle
