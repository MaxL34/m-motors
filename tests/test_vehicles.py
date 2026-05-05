import pytest
from typing import Optional

from app.models.vehicle import FuelType, TransmissionType, Vehicle, VehicleStatus
from app.schemas.vehicle_schema import VehicleCreate, VehicleDeactivate, VehicleUpdate
from app.services.vehicle_service import (
    activate_vehicle,
    create_vehicle,
    deactivate_vehicle,
    update_vehicle,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_vehicle(
    db,
    *,
    vin,
    licence_plate,
    brand="Renault",
    model="Clio",
    year=2022,
    fuel_type=FuelType.PETROL,
    transmission_type=TransmissionType.MANUAL,
    mileage=20000,
    is_for_sale=True,
    selling_price: Optional[float] = 15000.0,
    monthly_rental_price: Optional[float] = None,
    engine_power=100,
    color="Rouge",
    description=None,
    status=VehicleStatus.ACTIVE,
):
    v = Vehicle(
        vin=vin,
        licence_plate=licence_plate,
        brand=brand,
        model=model,
        year=year,
        fuel_type=fuel_type,
        transmission_type=transmission_type,
        mileage=mileage,
        is_for_sale=is_for_sale,
        selling_price=selling_price,
        monthly_rental_price=monthly_rental_price,
        engine_power=engine_power,
        color=color,
        description=description,
        status=status,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


# ── GET /vehicles — catalogue ─────────────────────────────────────────────────


class TestCatalog:

    def test_catalog_returns_200(self, client):
        response = client.get("/vehicles")
        assert response.status_code == 200

    def test_catalog_shows_active_vehicles(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000001",
            licence_plate="AA-001-AA",
            brand="Peugeot",
            model="208",
            status=VehicleStatus.ACTIVE,
        )
        response = client.get("/vehicles")
        assert "Peugeot" in response.text
        assert "208" in response.text

    def test_catalog_hides_inactive_vehicles(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000002",
            licence_plate="AA-002-AA",
            brand="Citroën",
            model="C3",
            status=VehicleStatus.INACTIVE,
        )
        response = client.get("/vehicles")
        assert "Citroën" not in response.text

    def test_catalog_empty_state(self, client):
        response = client.get("/vehicles")
        assert response.status_code == 200
        assert "Aucun véhicule disponible" in response.text

    def test_catalog_shows_vehicle_count(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000003",
            licence_plate="AA-003-AA",
            brand="Renault",
            model="Clio",
        )
        make_vehicle(
            db,
            vin="VF1000000000000004",
            licence_plate="AA-004-AA",
            brand="Renault",
            model="Megane",
        )
        response = client.get("/vehicles")
        assert "2 véhicule" in response.text

    def test_catalog_shows_sale_badge(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000005",
            licence_plate="AA-005-AA",
            is_for_sale=True,
            selling_price=12000,
        )
        response = client.get("/vehicles")
        assert "Vente" in response.text

    def test_catalog_shows_rental_badge(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000006",
            licence_plate="AA-006-AA",
            is_for_sale=False,
            selling_price=None,
            monthly_rental_price=450,
        )
        response = client.get("/vehicles")
        assert "Location" in response.text

    def test_catalog_shows_french_fuel_label(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000007",
            licence_plate="AA-007-AA",
            fuel_type=FuelType.ELECTRIC,
        )
        response = client.get("/vehicles")
        assert "Électrique" in response.text
        assert "ELECTRIC" not in response.text

    def test_catalog_shows_french_transmission_label(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000008",
            licence_plate="AA-008-AA",
            transmission_type=TransmissionType.AUTOMATIC,
        )
        response = client.get("/vehicles")
        assert "Automatique" in response.text
        assert "AUTOMATIC" not in response.text

    def test_catalog_link_to_detail(self, client, db):
        v = make_vehicle(db, vin="VF1000000000000009", licence_plate="AA-009-AA")
        response = client.get("/vehicles")
        assert f"/vehicles/{v.id}" in response.text

    # ── Filtres ───────────────────────────────────────────────────────────────

    def test_search_filter_by_brand(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000010",
            licence_plate="AA-010-AA",
            brand="BMW",
            model="Série 3",
        )
        make_vehicle(
            db,
            vin="VF1000000000000011",
            licence_plate="AA-011-AA",
            brand="Audi",
            model="A4",
        )
        response = client.get("/vehicles?search=BMW")
        assert "BMW" in response.text
        assert "Audi" not in response.text

    def test_search_filter_by_model(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000012",
            licence_plate="AA-012-AA",
            brand="Renault",
            model="Zoe",
        )
        make_vehicle(
            db,
            vin="VF1000000000000013",
            licence_plate="AA-013-AA",
            brand="Renault",
            model="Twingo",
        )
        response = client.get("/vehicles?search=Zoe")
        assert "Zoe" in response.text
        assert "Twingo" not in response.text

    def test_search_no_result_shows_empty_state(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000014",
            licence_plate="AA-014-AA",
            brand="Toyota",
            model="Yaris",
        )
        response = client.get("/vehicles?search=inexistant")
        assert "Aucun véhicule disponible" in response.text

    def test_type_filter_sale_only(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000015",
            licence_plate="AA-015-AA",
            brand="Ford",
            model="Fiesta",
            is_for_sale=True,
            selling_price=9000,
        )
        make_vehicle(
            db,
            vin="VF1000000000000016",
            licence_plate="AA-016-AA",
            brand="Ford",
            model="Focus",
            is_for_sale=False,
            selling_price=None,
            monthly_rental_price=300,
        )
        response = client.get("/vehicles?type_filter=sale")
        assert "Fiesta" in response.text
        assert "Focus" not in response.text

    def test_type_filter_rental_only(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000017",
            licence_plate="AA-017-AA",
            brand="Seat",
            model="Ibiza",
            is_for_sale=True,
            selling_price=11000,
        )
        make_vehicle(
            db,
            vin="VF1000000000000018",
            licence_plate="AA-018-AA",
            brand="Seat",
            model="Leon",
            is_for_sale=False,
            selling_price=None,
            monthly_rental_price=350,
        )
        response = client.get("/vehicles?type_filter=rental")
        assert "Leon" in response.text
        assert "Ibiza" not in response.text

    def test_invalid_type_filter_returns_all(self, client, db):
        make_vehicle(
            db,
            vin="VF1000000000000019",
            licence_plate="AA-019-AA",
            brand="Opel",
            model="Corsa",
        )
        response = client.get("/vehicles?type_filter=invalid")
        assert response.status_code == 200
        assert "Opel" in response.text


# ── GET /vehicles/{id} — détail ───────────────────────────────────────────────


class TestVehicleDetail:

    def test_detail_returns_200(self, client, db):
        v = make_vehicle(db, vin="VF2000000000000001", licence_plate="BB-001-BB")
        response = client.get(f"/vehicles/{v.id}")
        assert response.status_code == 200

    def test_detail_404_unknown_vehicle(self, client):
        response = client.get("/vehicles/99999")
        assert response.status_code == 404

    def test_detail_shows_brand_and_model(self, client, db):
        v = make_vehicle(
            db,
            vin="VF2000000000000002",
            licence_plate="BB-002-BB",
            brand="Mercedes",
            model="Classe A",
        )
        response = client.get(f"/vehicles/{v.id}")
        assert "Mercedes" in response.text
        assert "Classe A" in response.text

    def test_detail_shows_year_and_mileage(self, client, db):
        v = make_vehicle(
            db,
            vin="VF2000000000000003",
            licence_plate="BB-003-BB",
            year=2020,
            mileage=45000,
        )
        response = client.get(f"/vehicles/{v.id}")
        assert "2020" in response.text
        assert "45" in response.text

    def test_detail_shows_selling_price(self, client, db):
        v = make_vehicle(
            db,
            vin="VF2000000000000004",
            licence_plate="BB-004-BB",
            is_for_sale=True,
            selling_price=18500,
        )
        response = client.get(f"/vehicles/{v.id}")
        assert "18" in response.text
        assert "500" in response.text

    def test_detail_shows_monthly_rental_price(self, client, db):
        v = make_vehicle(
            db,
            vin="VF2000000000000005",
            licence_plate="BB-005-BB",
            is_for_sale=False,
            selling_price=None,
            monthly_rental_price=399,
        )
        response = client.get(f"/vehicles/{v.id}")
        assert "399" in response.text
        assert "/mois" in response.text

    def test_detail_shows_price_on_request_when_no_price(self, client, db):
        v = make_vehicle(
            db,
            vin="VF2000000000000006",
            licence_plate="BB-006-BB",
            is_for_sale=True,
            selling_price=None,
        )
        response = client.get(f"/vehicles/{v.id}")
        assert "Prix sur demande" in response.text

    def test_detail_shows_french_fuel_label(self, client, db):
        v = make_vehicle(
            db,
            vin="VF2000000000000007",
            licence_plate="BB-007-BB",
            fuel_type=FuelType.DIESEL,
        )
        response = client.get(f"/vehicles/{v.id}")
        assert "Diesel" in response.text
        assert "DIESEL" not in response.text

    def test_detail_shows_french_transmission_label(self, client, db):
        v = make_vehicle(
            db,
            vin="VF2000000000000008",
            licence_plate="BB-008-BB",
            transmission_type=TransmissionType.MANUAL,
        )
        response = client.get(f"/vehicles/{v.id}")
        assert "Manuelle" in response.text
        assert "MANUAL" not in response.text

    def test_detail_shows_engine_power(self, client, db):
        v = make_vehicle(
            db, vin="VF2000000000000009", licence_plate="BB-009-BB", engine_power=130
        )
        response = client.get(f"/vehicles/{v.id}")
        assert "130" in response.text
        assert "ch" in response.text

    def test_detail_shows_color(self, client, db):
        v = make_vehicle(
            db, vin="VF2000000000000010", licence_plate="BB-010-BB", color="Bleu nuit"
        )
        response = client.get(f"/vehicles/{v.id}")
        assert "Bleu nuit" in response.text

    def test_detail_shows_description(self, client, db):
        v = make_vehicle(
            db,
            vin="VF2000000000000011",
            licence_plate="BB-011-BB",
            description="Très bon état, première main.",
        )
        response = client.get(f"/vehicles/{v.id}")
        assert "Très bon état, première main." in response.text

    def test_detail_shows_licence_plate(self, client, db):
        v = make_vehicle(db, vin="VF2000000000000012", licence_plate="BB-012-BB")
        response = client.get(f"/vehicles/{v.id}")
        assert "BB-012-BB" in response.text

    def test_detail_back_link_to_catalog(self, client, db):
        v = make_vehicle(db, vin="VF2000000000000013", licence_plate="BB-013-BB")
        response = client.get(f"/vehicles/{v.id}")
        assert "/vehicles" in response.text


# ── vehicle_service ───────────────────────────────────────────────────────────


class TestVehicleService:

    def _create_data(self, vin="VF3SVC00000000001", licence_plate="SV-001-SV"):
        return VehicleCreate(
            vin=vin,
            licence_plate=licence_plate,
            brand="Renault",
            model="Clio",
            year=2022,
            fuel_type=FuelType.PETROL,
            transmission_type=TransmissionType.MANUAL,
            mileage=10000,
            is_for_sale=True,
            selling_price=15000.0,
        )

    def test_create_vehicle_returns_vehicle(self, db):
        vehicle = create_vehicle(db, self._create_data())
        assert vehicle.id is not None
        assert vehicle.brand == "Renault"

    def test_create_vehicle_starts_inactive(self, db):
        vehicle = create_vehicle(db, self._create_data(vin="VF3SVC00000000002", licence_plate="SV-002-SV"))
        assert vehicle.status == VehicleStatus.INACTIVE

    def test_update_vehicle_changes_fields(self, db):
        v = make_vehicle(db, vin="VF3SVC00000000003", licence_plate="SV-003-SV")
        updated = update_vehicle(db, v.id, VehicleUpdate(brand="Peugeot", mileage=25000))
        assert updated.brand == "Peugeot"
        assert updated.mileage == 25000

    def test_activate_inactive_vehicle(self, db):
        v = make_vehicle(db, vin="VF3SVC00000000004", licence_plate="SV-004-SV", status=VehicleStatus.INACTIVE)
        activated = activate_vehicle(db, v.id)
        assert activated.status == VehicleStatus.ACTIVE

    def test_activate_already_active_raises_409(self, db):
        from fastapi import HTTPException
        v = make_vehicle(db, vin="VF3SVC00000000005", licence_plate="SV-005-SV", status=VehicleStatus.ACTIVE)
        with pytest.raises(HTTPException) as exc:
            activate_vehicle(db, v.id)
        assert exc.value.status_code == 409

    def test_deactivate_active_vehicle(self, db):
        v = make_vehicle(db, vin="VF3SVC00000000006", licence_plate="SV-006-SV", status=VehicleStatus.ACTIVE)
        deactivated = deactivate_vehicle(db, v.id, VehicleDeactivate(deactivation_reason="Vendu"))
        assert deactivated.status == VehicleStatus.INACTIVE
        assert deactivated.deactivation_reason == "Vendu"

    def test_deactivate_already_inactive_raises_409(self, db):
        from fastapi import HTTPException
        v = make_vehicle(db, vin="VF3SVC00000000007", licence_plate="SV-007-SV", status=VehicleStatus.INACTIVE)
        with pytest.raises(HTTPException) as exc:
            deactivate_vehicle(db, v.id, VehicleDeactivate(deactivation_reason="Raison"))
        assert exc.value.status_code == 409
