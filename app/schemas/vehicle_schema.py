from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

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

class VehicleCreate(BaseModel):
    """Pydantic model for creating a new vehicle."""
    # Identifiers
    vin: str = Field(min_length=17, max_length=17)
    
    # Vehicle details
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=2000, le=2100, description="Manufacturing year")
    fuel_type: FuelType = Field(description="Fuel type of the vehicle")
    transmission_type: TransmissionType = Field(description="Transmission type of the vehicle")
    mileage: int = Field(ge=0, description="Current mileage in km")
    engine_power: int = Field(ge=0, description="Engine power in horsepower (HP)")
    description: Optional[str] = Field(default=None, max_length=1000, description="Detailed description of the vehicle")

    # Commercial details
    is_for_sale: bool = Field(description="Whether the vehicle is for sale (True) or for rent (False)")
    selling_price: Optional[float] = Field(default=None, gt=0, description="Selling price must be greater than zero.")
    monthly_rental_price: Optional[float] = Field(gt=0, description="Monthly rental price must be greater than zero if provided.")