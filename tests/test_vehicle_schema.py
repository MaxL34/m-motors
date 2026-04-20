import pytest
from pydantic import ValidationError
from app.schemas.vehicle_schema import VehicleCreate
from app.models.vehicle import FuelType, TransmissionType


def test_vehicle_create_valid():
    """Un véhicule avec tous les champs requis passe la validation."""
    vehicle = VehicleCreate(
        vin="VF1RFB00X57123456",
        licence_plate="GH-234-AB",
        brand="Renault",
        model="Clio V",
        year=2022,
        fuel_type=FuelType.PETROL,
        transmission_type=TransmissionType.MANUAL,
        mileage=23000,
        engine_power=100,
        is_for_sale=True,
        selling_price=14500.00,
    )
    assert vehicle.brand == "Renault"
    assert vehicle.vin == "VF1RFB00X57123456"


def test_vehicle_create_vin_too_short():
    """Un VIN de moins de 17 caractères est rejeté."""
    with pytest.raises(ValidationError):
        VehicleCreate(
            vin="ABC123",
            licence_plate="GH-234-AB",
            brand="Renault",
            model="Clio",
            year=2022,
            fuel_type=FuelType.PETROL,
            transmission_type=TransmissionType.MANUAL,
            mileage=23000,
            engine_power=100,
            is_for_sale=True,
            selling_price=14500.00,
        )


def test_vehicle_create_negative_price():
    """Un prix négatif est rejeté."""
    with pytest.raises(ValidationError):
        VehicleCreate(
            vin="VF1RFB00X57123456",
            licence_plate="GH-234-AB",
            brand="Renault",
            model="Clio",
            year=2022,
            fuel_type=FuelType.PETROL,
            transmission_type=TransmissionType.MANUAL,
            mileage=23000,
            engine_power=100,
            is_for_sale=True,
            selling_price=-500,
        )


def test_vehicle_create_empty_brand():
    """Une marque vide est rejetée."""
    with pytest.raises(ValidationError):
        VehicleCreate(
            vin="VF1RFB00X57123456",
            licence_plate="GH-234-AB",
            brand="",
            model="Clio",
            year=2022,
            fuel_type=FuelType.PETROL,
            transmission_type=TransmissionType.MANUAL,
            mileage=23000,
            engine_power=100,
            is_for_sale=True,
            selling_price=14500.00,
        )