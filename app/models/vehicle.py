from enum import Enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, Float, String, Boolean, Enum as SqlEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


class VehicleStatus(str, Enum):
    """Vehicle status : visible in catalog or deleted (not visible)."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    

class FuelType(str, Enum):
    """Fuel type of the vehicle"""
    PETROL = "PETROL"
    DIESEL = "DIESEL"
    HYBRID = "HYBRID"
    ELECTRIC = "ELECTRIC"
    LPG="LPG"


class TransmissionType(str, Enum):
    """Transmission type of the vehicle"""
    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"
    SEMI_AUTOMATIC = "SEMI_AUTOMATIC"

class Vehicle(Base):
    """SQLAlchemy model for a vehicle in the application M-Motors.
    
    A vehicle can be :
    - ACTIVE: visible in the customer catalog
    - INACTIVE: not visible in the customer catalog (removed by admin: sold, damages, etc.) but history preserved

    A vehicle can be offered for:
    - Sale (is_for_sale=True): using selling_price
    - Rental (is_for_sale=False): using monthly_rental_price

    Attributes:
        id: Unique identifier
        vin: Vehicle Identification Number (unique)
        licence_plate: Registration number (unique)
        brand: Vehicle brand
        model: Vehicle model
        year: Manufacturing year
        fuel_type: Fuel type (PETROL, DIESEL, etc.) (optional)
        transmission_type: Transmission type (MANUAL, AUTOMATIC, etc.) (optional)
        mileage: Current mileage in km
        engine_power: Engine power in horsepower (HP, optional)
        is_for_sale: Whether the vehicle is for sale (True) or for rent (False)
        selling_price: Selling price in euros
        monthly_rental_price: Monthly rental price in euros (optional)
        color: Vehicle color
        description: Detailed description of the vehicle
        status: ACTIVE or INACTIVE
        deactivation_reason: Why it was deactivated (SOLD, ACCIDENT, etc.)
        deactivated_at: When it was deactivated
        created_at: Creation timestamp
        updated_at: Last modification update
    """
    __tablename__ = "vehicles"

    # Identifiers
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    vin: Mapped[str] = mapped_column(String(17), unique=True, index=True)
    licence_plate: Mapped[str] = mapped_column(String(20), unique=True, index=True)

    # General informations
    brand: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    year: Mapped[int] = mapped_column(Integer)
    fuel_type: Mapped[Optional[FuelType]] = mapped_column(SqlEnum(FuelType), nullable=True)
    transmission_type: Mapped[Optional[TransmissionType]] = mapped_column(SqlEnum(TransmissionType), nullable=True)

    # Technical specifications
    mileage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engine_power: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Pricing
    selling_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monthly_rental_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Description
    color: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Commercial
    is_for_sale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Status and audit
    status: Mapped[VehicleStatus] = mapped_column(SqlEnum(VehicleStatus), nullable=False, default=VehicleStatus.INACTIVE, index=True)
    deactivation_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    deactivated_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())                                                                                                                                                                                           
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now()) 

    # Relations
    client_files: Mapped[list] = relationship("ClientFile", back_populates="vehicle")