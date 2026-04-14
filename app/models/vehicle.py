from enum import Enum
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, Enum as SqlEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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
        description: Detailed description pf the vehicle
        status: ACTIVE or INACTIVE
        deactivation_reason: Why it was deactivated (SOLD, ACCIDENT, etc.)
        deactivated_at: When it was deactivated
        created_at: Creation timestamp
        updated_at: Last modification update
    """
    __tablename__="vehicles"

# Identifiers
id = Column(Integer, primary_key=True, index=True)
vin = Column(String(17), unique=True, index=True, nullable=False)
licence_plate = Column(String(20), unique=True, index=True, nullable=False)

# General informations
brand = Column(String(50), nullable=False)
model = Column(String(50), nullable=False)
year = Column(Integer, nullable=False)
fuel_type = Column(SqlEnum(FuelType), nullable=True, default=FuelType.PETROL)
transmission_type = Column(SqlEnum(TransmissionType), nullable=True, default=TransmissionType.MANUAL)

# Technical specifications
mileage = Column(Integer, nullable=False, default=0)
engine_power = Column(Integer, nullable=True)

# Pricing
selling_price = Column(Float, nullable=False)
monthly_rental_price = Column(Float, nullable=True)

# Description
color = Column(String(30), nullable=True)
description = Column(String(500), nullable=False)

# Status and audit
status = Column(SqlEnum(VehicleStatus), nullable=False, default=VehicleStatus.INACTIVE, index=True)
deactivation_reason = Column(String(255), nullable=False)
deactivated_at = Column(DateTime, nullable=False)
created_at = Column(DateTime, server_default=func.now(), nullable=False)
updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
is_for_sale = Column(Boolean, nullable=False, default=True)

#Relations - will be completed when the other models are created
client_files = relationship("ClientFile", back_populates="vehicle")