from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.models.vehicle import FuelType, TransmissionType, VehicleStatus

class VehicleCreate(BaseModel):
    """Pydantic model for creating a new vehicle."""
    # Identifiers
    vin: str = Field(min_length=17, max_length=17)
    licence_plate: str = Field(min_length=2, max_length=20)

    # Vehicle details
    brand: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=50)
    year: int = Field(ge=2000, le=2100, description="Manufacturing year")
    fuel_type: FuelType = Field(description="Fuel type of the vehicle")
    transmission_type: TransmissionType = Field(description="Transmission type of the vehicle")
    mileage: int = Field(ge=0, description="Current mileage in km")
    engine_power: int = Field(ge=0, description="Engine power in horsepower (HP)")
    description: Optional[str] = Field(default=None, max_length=1000, description="Detailed description of the vehicle")

    # Commercial information
    is_for_sale: bool = Field(description="Whether the vehicle is for sale (True) or for rent (False)")
    selling_price: Optional[float] = Field(default=None, gt=0, description="Selling price must be greater than zero.")
    monthly_rental_price: Optional[float] = Field(default=None, gt=0, description="Monthly rental price must be greater than zero if provided.")


class VehicleUpdate(BaseModel):
    """Pydantic model for updating an existing vehicle. All fields are optional."""
    licence_plate: Optional[str] = Field(default=None, min_length=2,max_length=20)
    brand: Optional[str] = Field(default=None, min_length=1, max_length=50)                                             
    model: Optional[str] = Field(default=None, min_length=1, max_length=50)
    year: Optional[int] = Field(default=None, ge=2000, le=2100)                                                         
    fuel_type: Optional[FuelType] = None
    transmission_type: Optional[TransmissionType] = None                                                                
    color: Optional[str] = Field(default=None, max_length=30)
    mileage: Optional[int] = Field(default=None, ge=0)                                                                  
    engine_power: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = Field(default=None, max_length=500)                                                    
    is_for_sale: Optional[bool] = None                                                                                  
    selling_price: Optional[float] = Field(default=None, gt=0)
    monthly_rental_price: Optional[float] = Field(default=None, gt=0)


class VehicleDeactivate(BaseModel): 
    """Payload pour désactiver un véhicule."""
    deactivation_reason: str = Field(min_length=1, max_length=255)


class VehicleResponse(BaseModel):
    """Pydantic model for the response returned by the API for a vehicle."""
    id: int     
    vin: str
    licence_plate: str
    brand: str
    model: str
    year: int
    fuel_type: Optional[FuelType]
    transmission_type: Optional[TransmissionType]                                                                       
    color: Optional[str]
    mileage: int                                                                                                        
    engine_power: Optional[int]
    description: Optional[str]
    is_for_sale: bool
    selling_price: Optional[float]
    monthly_rental_price: Optional[float]                                                                               
    status: VehicleStatus
    deactivation_reason: Optional[str]                                                                                  
    deactivated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


    model_config = {"from_attributes": True}