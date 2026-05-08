from pathlib import Path
from unittest.mock import patch

import pytest

from app.models.client_file import ClientFile, ClientFileStatus, ClientFileType
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.user import User
from app.models.vehicle import FuelType, TransmissionType, Vehicle, VehicleStatus
from app.utils.security import create_access_token, hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_admin(db, email="admin@test.com") -> User:
    user = User(
        first_name="Admin", last_name="Test", email=email,
        password_hash=hash_password("adminpass"), is_admin=True, is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_user(db, email="user@test.com") -> User:
    user = User(
        first_name="Jean", last_name="Dupont", email=email,
        password_hash=hash_password("userpass"), is_admin=False, is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_vehicle(db, vin="VF3ADMIN000000001", licence_plate="AD-001-AD",
                 status=VehicleStatus.ACTIVE) -> Vehicle:
    v = Vehicle(
        vin=vin, licence_plate=licence_plate,
        brand="Renault", model="Clio", year=2022,
        fuel_type=FuelType.PETROL, transmission_type=TransmissionType.MANUAL,
        mileage=10000, is_for_sale=True, selling_price=15000.0,
        status=status,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def make_client_file(db, user_id, vehicle_id, status=ClientFileStatus.PENDING,
                     file_type=ClientFileType.SALE) -> ClientFile:
    cf = ClientFile(
        user_id=user_id, vehicle_id=vehicle_id,
        file_type=file_type, status=status,
    )
    db.add(cf)
    db.commit()
    db.refresh(cf)
    return cf


def soft_delete_file(db, cf) -> ClientFile:
    from datetime import datetime, timezone
    cf.deleted_at = datetime.now(timezone.utc)
    cf.deleted_by_admin_id = 1
    cf.deleted_reason = "Test suppression"
    db.commit()
    db.refresh(cf)
    return cf


def make_document(db, client_file_id, doc_type=DocumentType.CNI,
                  status=DocumentStatus.PENDING, is_locked=False,
                  file_path=None) -> Document:
    doc = Document(
        client_file_id=client_file_id, document_type=doc_type,
        status=status, is_locked=is_locked,
        file_name="test.pdf",
        file_path=file_path or f"uploads/{client_file_id}/{doc_type.value}.pdf",
        file_size=1024, mime_type="application/pdf",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def admin_cookie(user_id: int) -> str:
    return create_access_token({"sub": str(user_id), "is_admin": True})


VALID_VEHICLE_FORM = {
    "vin": "VF3FORM000000001A",
    "licence_plate": "FO-001-FM",
    "brand": "Renault",
    "model": "Clio",
    "year": "2022",
    "fuel_type": "PETROL",
    "transmission_type": "MANUAL",
    "mileage": "10000",
    "engine_power": "",
    "is_for_sale": "true",
    "selling_price": "15000",
    "monthly_rental_price": "",
    "color": "",
    "description": "",
}


# ── TestAdminVehicleList ──────────────────────────────────────────────────────


class TestAdminVehicleList:

    def test_list_requires_auth(self, client):
        response = client.get("/admin/vehicles", follow_redirects=False)
        assert response.status_code == 303
        assert "/admin/login" in response.headers["location"]

    def test_list_returns_200_for_admin(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/vehicles")
        assert response.status_code == 200

    def test_list_with_invalid_sort_by_falls_back(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/vehicles?sort_by=invalid")
        assert response.status_code == 200

    def test_list_with_invalid_sort_order_falls_back(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/vehicles?sort_order=random")
        assert response.status_code == 200

    def test_list_with_status_filter(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        make_vehicle(db, vin="VF3LIST00000000A1", licence_plate="LI-001-LI", status=VehicleStatus.ACTIVE)
        make_vehicle(db, vin="VF3LIST00000000A2", licence_plate="LI-002-LI", status=VehicleStatus.INACTIVE)
        response = client.get("/admin/vehicles?status_filter=ACTIVE")
        assert response.status_code == 200


# ── TestAdminVehicleCreate ────────────────────────────────────────────────────


class TestAdminVehicleCreate:

    def test_get_new_form_returns_200(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/vehicles/new")
        assert response.status_code == 200

    def test_post_creates_vehicle_and_redirects(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post("/admin/vehicles", data=VALID_VEHICLE_FORM, follow_redirects=False)
        assert response.status_code == 303
        assert "/admin/vehicles/" in response.headers["location"]

    def test_post_with_empty_optional_fields_covers_parse_helpers(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        form = {**VALID_VEHICLE_FORM, "vin": "VF3FORM000000002B", "licence_plate": "FO-002-FM",
                "engine_power": "", "selling_price": "", "monthly_rental_price": "",
                "is_for_sale": "false"}
        response = client.post("/admin/vehicles", data=form, follow_redirects=False)
        assert response.status_code == 303

    def test_post_invalid_vin_returns_422(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        form = {**VALID_VEHICLE_FORM, "vin": "TOOSHORT"}
        response = client.post("/admin/vehicles", data=form)
        assert response.status_code == 422


# ── TestAdminVehicleDetail ────────────────────────────────────────────────────


class TestAdminVehicleDetail:

    def test_detail_returns_200(self, client, db):
        admin = make_admin(db)
        vehicle = make_vehicle(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get(f"/admin/vehicles/{vehicle.id}")
        assert response.status_code == 200

    def test_detail_shows_vin(self, client, db):
        admin = make_admin(db)
        vehicle = make_vehicle(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get(f"/admin/vehicles/{vehicle.id}")
        assert vehicle.vin in response.text


# ── TestAdminVehicleEdit ──────────────────────────────────────────────────────


class TestAdminVehicleEdit:

    def test_get_edit_form_returns_200(self, client, db):
        admin = make_admin(db)
        vehicle = make_vehicle(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get(f"/admin/vehicles/{vehicle.id}/edit")
        assert response.status_code == 200

    def test_post_edit_invalid_year_returns_422(self, client, db):
        admin = make_admin(db, email="admin_edit2@test.com")
        vehicle = make_vehicle(db, vin="VF3EDIT000000002A", licence_plate="ED-002-ED")
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/vehicles/{vehicle.id}/edit", data={
            "licence_plate": "ED-002-ED",
            "year": "1990",
            "mileage": "10000",
        })
        assert response.status_code == 422

    def test_post_edit_valid_redirects(self, client, db):
        admin = make_admin(db)
        vehicle = make_vehicle(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/vehicles/{vehicle.id}/edit", data={
            "licence_plate": "AD-001-AD",
            "brand": "Peugeot", "model": "208", "year": "2021",
            "fuel_type": "DIESEL", "transmission_type": "AUTOMATIC",
            "mileage": "30000", "engine_power": "110",
            "is_for_sale": "true", "selling_price": "12000",
            "monthly_rental_price": "", "color": "", "description": "",
        }, follow_redirects=False)
        assert response.status_code == 303
        assert f"/admin/vehicles/{vehicle.id}" in response.headers["location"]


# ── TestAdminActivateDeactivate ───────────────────────────────────────────────


class TestAdminActivateDeactivate:

    def test_activate_inactive_vehicle_redirects_success(self, client, db):
        admin = make_admin(db)
        vehicle = make_vehicle(db, vin="VF3ACT000000001A", licence_plate="AC-001-AC",
                               status=VehicleStatus.INACTIVE)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/vehicles/{vehicle.id}/activate", follow_redirects=False)
        assert response.status_code == 303
        assert "success" in response.headers["location"]

    def test_activate_already_active_redirects_error(self, client, db):
        admin = make_admin(db)
        vehicle = make_vehicle(db, vin="VF3ACT000000002A", licence_plate="AC-002-AC",
                               status=VehicleStatus.ACTIVE)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/vehicles/{vehicle.id}/activate", follow_redirects=False)
        assert response.status_code == 303
        assert "error" in response.headers["location"]

    def test_deactivate_active_vehicle_redirects_success(self, client, db):
        admin = make_admin(db)
        vehicle = make_vehicle(db, vin="VF3DCT000000001A", licence_plate="DC-001-DC",
                               status=VehicleStatus.ACTIVE)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/vehicles/{vehicle.id}/deactivate",
                               data={"deactivation_reason": "Vendu"},
                               follow_redirects=False)
        assert response.status_code == 303
        assert "success" in response.headers["location"]

    def test_deactivate_already_inactive_redirects_error(self, client, db):
        admin = make_admin(db, email="admin_dea@test.com")
        vehicle = make_vehicle(db, vin="VF3DCT000000002A", licence_plate="DC-002-DC",
                               status=VehicleStatus.INACTIVE)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/vehicles/{vehicle.id}/deactivate",
                               data={"deactivation_reason": "Raison"},
                               follow_redirects=False)
        assert response.status_code == 303
        assert "error" in response.headers["location"]


# ── TestAdminCustomerFiles ────────────────────────────────────────────────────


class TestAdminCustomerFiles:

    def test_list_returns_200(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/customer-files")
        assert response.status_code == 200

    def test_detail_returns_200(self, client, db):
        admin = make_admin(db)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get(f"/admin/customer-files/{cf.id}")
        assert response.status_code == 200

    def test_update_status_success(self, client, db):
        admin = make_admin(db)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/customer-files/{cf.id}/status", data={
            "new_status": "IN_PROGRESS",
            "cancellation_reason": "",
            "rejection_reason": "",
        }, follow_redirects=False)
        assert response.status_code == 303
        assert "success" in response.headers["location"]

    def test_update_status_approved_without_all_docs_redirects_error(self, client, db):
        admin = make_admin(db)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        make_document(db, cf.id, DocumentType.CNI, status=DocumentStatus.VALIDATED)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/customer-files/{cf.id}/status", data={
            "new_status": "APPROVED",
            "cancellation_reason": "",
            "rejection_reason": "",
        }, follow_redirects=False)
        assert response.status_code == 303
        assert "error" in response.headers["location"]


# ── TestAdminDocuments ────────────────────────────────────────────────────────


class TestAdminDocuments:

    def _setup(self, db):
        admin = make_admin(db)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        doc = make_document(db, cf.id)
        return admin, cf, doc

    def test_lock_document_redirects(self, client, db):
        admin, cf, doc = self._setup(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/documents/{doc.id}/lock", follow_redirects=False)
        assert response.status_code == 303
        assert f"/admin/customer-files/{cf.id}" in response.headers["location"]

    def test_unlock_document_redirects(self, client, db):
        admin, cf, doc = self._setup(db)
        doc.is_locked = True
        db.commit()
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/documents/{doc.id}/unlock", follow_redirects=False)
        assert response.status_code == 303

    def test_validate_document_redirects(self, client, db):
        admin, cf, doc = self._setup(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/documents/{doc.id}/validate", follow_redirects=False)
        assert response.status_code == 303
        assert "success" in response.headers["location"]

    def test_refuse_document_redirects(self, client, db):
        admin, cf, doc = self._setup(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/documents/{doc.id}/refuse",
                               data={"rejection_reason": "Document illisible"},
                               follow_redirects=False)
        assert response.status_code == 303
        assert "success" in response.headers["location"]

    def test_view_document_file_not_found_returns_404(self, client, db):
        admin, cf, doc = self._setup(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get(f"/admin/documents/{doc.id}/view")
        assert response.status_code == 404

    def test_view_document_success(self, client, db, tmp_path):
        admin = make_admin(db, email="admin2@test.com")
        user = make_user(db, email="user2@test.com")
        vehicle = make_vehicle(db, vin="VF3VIEW00000001A", licence_plate="VI-001-VI")
        cf = make_client_file(db, user.id, vehicle.id)
        fake_file = tmp_path / "test.pdf"
        fake_file.write_bytes(b"%PDF-1.4 fake content")
        doc = make_document(db, cf.id, file_path=str(fake_file))
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get(f"/admin/documents/{doc.id}/view")
        assert response.status_code == 200


# ── TestAdminTrashRestore ─────────────────────────────────────────────────────


class TestAdminTrashRestore:

    def test_restore_requires_admin(self, client, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = soft_delete_file(db, make_client_file(db, user.id, vehicle.id))
        response = client.post(f"/admin/trash/{cf.id}/restore", follow_redirects=False)
        assert response.status_code == 303
        assert "/admin/login" in response.headers["location"]

    def test_restore_redirects_with_success(self, client, db):
        admin = make_admin(db)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = soft_delete_file(db, make_client_file(db, user.id, vehicle.id))
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post(f"/admin/trash/{cf.id}/restore", follow_redirects=False)
        assert response.status_code == 303
        assert "success" in response.headers["location"]

    def test_restore_clears_deletion_fields(self, client, db):
        admin = make_admin(db)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = soft_delete_file(db, make_client_file(db, user.id, vehicle.id))
        client.cookies.set("access_token", admin_cookie(admin.id))
        client.post(f"/admin/trash/{cf.id}/restore")
        db.refresh(cf)
        assert cf.deleted_at is None
        assert cf.deleted_reason is None
        assert cf.deleted_by_admin_id is None

    def test_restore_preserves_original_status(self, client, db):
        admin = make_admin(db)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = soft_delete_file(db, make_client_file(db, user.id, vehicle.id, status=ClientFileStatus.IN_PROGRESS))
        client.cookies.set("access_token", admin_cookie(admin.id))
        client.post(f"/admin/trash/{cf.id}/restore")
        db.refresh(cf)
        assert cf.status == ClientFileStatus.IN_PROGRESS

    def test_restored_file_appears_in_customer_files_list(self, client, db):
        admin = make_admin(db)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = soft_delete_file(db, make_client_file(db, user.id, vehicle.id))
        client.cookies.set("access_token", admin_cookie(admin.id))
        client.post(f"/admin/trash/{cf.id}/restore")
        response = client.get("/admin/customer-files")
        assert response.status_code == 200
        assert "Renault" in response.text

    def test_restore_nonexistent_file_returns_404(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.post("/admin/trash/9999/restore", follow_redirects=False)
        assert response.status_code == 404


# ── TestAdminCustomerFilesFilters ─────────────────────────────────────────────


class TestAdminCustomerFilesFilters:

    def test_filter_by_sale_shows_only_sale_files(self, client, db):
        admin = make_admin(db)
        user = make_user(db)
        v1 = make_vehicle(db, vin="VF3FL100000001A", licence_plate="FL-001-FL")
        v2 = make_vehicle(db, vin="VF3FL200000001A", licence_plate="FL-002-FL")
        make_client_file(db, user.id, v1.id, file_type=ClientFileType.SALE)
        make_client_file(db, user.id, v2.id, file_type=ClientFileType.RENTAL)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/customer-files?file_type=SALE")
        assert response.status_code == 200
        assert response.text.count("Vente") >= 1

    def test_filter_by_rental_shows_only_rental_files(self, client, db):
        admin = make_admin(db)
        user = make_user(db)
        v1 = make_vehicle(db, vin="VF3FL300000001A", licence_plate="FL-003-FL")
        v2 = make_vehicle(db, vin="VF3FL400000001A", licence_plate="FL-004-FL")
        make_client_file(db, user.id, v1.id, file_type=ClientFileType.SALE)
        make_client_file(db, user.id, v2.id, file_type=ClientFileType.RENTAL)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/customer-files?file_type=RENTAL")
        assert response.status_code == 200
        assert response.text.count("Location") >= 1

    def test_filter_by_status(self, client, db):
        admin = make_admin(db)
        user = make_user(db)
        v1 = make_vehicle(db, vin="VF3FS100000001A", licence_plate="FS-001-FS")
        v2 = make_vehicle(db, vin="VF3FS200000001A", licence_plate="FS-002-FS")
        make_client_file(db, user.id, v1.id, status=ClientFileStatus.PENDING)
        make_client_file(db, user.id, v2.id, status=ClientFileStatus.IN_PROGRESS)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/customer-files?status_filter=PENDING")
        assert response.status_code == 200

    def test_sort_by_date_asc_returns_200(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/customer-files?sort_by=created_at&sort_order=asc")
        assert response.status_code == 200

    def test_sort_by_progress_desc_returns_200(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/customer-files?sort_by=progress&sort_order=desc")
        assert response.status_code == 200

    def test_invalid_sort_by_falls_back_gracefully(self, client, db):
        admin = make_admin(db)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/customer-files?sort_by=invalid_field")
        assert response.status_code == 200

    def test_soft_deleted_files_excluded_from_list(self, client, db):
        admin = make_admin(db)
        user = make_user(db)
        vehicle = make_vehicle(db, vin="VF3EXC00000001A", licence_plate="EX-001-EX")
        cf = make_client_file(db, user.id, vehicle.id)
        soft_delete_file(db, cf)
        client.cookies.set("access_token", admin_cookie(admin.id))
        response = client.get("/admin/customer-files")
        assert response.status_code == 200
        assert "EX-001-EX" not in response.text
