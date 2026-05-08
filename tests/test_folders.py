import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.client_file import ClientFile, ClientFileStatus, ClientFileType
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.favorite import Favorite
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleStatus
from app.schemas.client_file_schema import ClientFileCreate
from app.schemas.document_schema import DocumentRefuse
from app.services.client_file_service import (
    compute_progress,
    get_all_client_files,
    get_client_file,
    get_client_file_by_user,
    get_or_create_client_file,
    restore_client_file,
    update_status,
    TOTAL_DOCUMENT_TYPES,
    MAX_ACTIVE_FILES,
)
from app.services.document_service import (
    lock_document,
    refuse_document,
    unlock_document,
    upload_document,
    validate_document,
)
from app.services.favorite_service import get_favorites, is_favorite, toggle_favorite
from app.utils.security import create_access_token, hash_password


def user_cookie(user_id: int) -> str:
    return create_access_token({"sub": str(user_id), "is_admin": False})


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user(db, email="user@test.com"):
    user = User(
        first_name="Jean", last_name="Dupont", email=email,
        password_hash=hash_password("password123"), is_admin=False, is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_vehicle(db, vin="VIN123456789012345"):
    vehicle = Vehicle(
        vin=vin, licence_plate=f"AA-001-AA-{vin[-4:]}",
        brand="Peugeot", model="308", year=2022,
        mileage=10000, is_for_sale=True, selling_price=18000.0,
        status=VehicleStatus.ACTIVE,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def make_client_file(db, user_id, vehicle_id, status=ClientFileStatus.PENDING):
    cf = ClientFile(
        user_id=user_id, vehicle_id=vehicle_id,
        file_type=ClientFileType.SALE, status=status,
    )
    db.add(cf)
    db.commit()
    db.refresh(cf)
    return cf


def make_document(db, client_file_id, doc_type=DocumentType.CNI, status=DocumentStatus.PENDING, is_locked=False):
    doc = Document(
        client_file_id=client_file_id,
        document_type=doc_type,
        status=status,
        is_locked=is_locked,
        file_name="test.pdf",
        file_path=f"uploads/documents/{client_file_id}/{doc_type.value}.pdf",
        file_size=1024,
        mime_type="application/pdf",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


FAKE_PDF = b"%PDF-1.4 fake pdf content"
FAKE_JPG = b"\xff\xd8\xff fake jpeg content"
FAKE_PNG = b"\x89PNG fake png content"


class MockUploadFile:
    """Simule un FastAPI UploadFile pour les tests."""
    def __init__(self, content: bytes, filename: str = "test.pdf", content_type: str = "application/pdf"):
        self.content = content
        self.filename = filename
        self.content_type = content_type

    async def read(self):
        return self.content


# ── client_file_service ───────────────────────────────────────────────────────

class TestGetOrCreateClientFile:

    def test_creates_file_when_none_exists(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        data = ClientFileCreate(vehicle_id=vehicle.id, file_type=ClientFileType.SALE)

        cf = get_or_create_client_file(db, user.id, data)

        assert cf.id is not None
        assert cf.user_id == user.id
        assert cf.vehicle_id == vehicle.id
        assert cf.status == ClientFileStatus.PENDING

    def test_returns_existing_file_if_active(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        existing = make_client_file(db, user.id, vehicle.id)
        data = ClientFileCreate(vehicle_id=vehicle.id, file_type=ClientFileType.SALE)

        cf = get_or_create_client_file(db, user.id, data)

        assert cf.id == existing.id

    def test_reopens_cancelled_file_instead_of_creating_new(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cancelled = make_client_file(db, user.id, vehicle.id, status=ClientFileStatus.CANCELLED)
        data = ClientFileCreate(vehicle_id=vehicle.id, file_type=ClientFileType.SALE)

        cf = get_or_create_client_file(db, user.id, data)

        assert cf.id == cancelled.id
        assert cf.status == ClientFileStatus.PENDING
        assert db.query(ClientFile).filter(ClientFile.user_id == user.id).count() == 1

    def test_reopens_rejected_file_instead_of_creating_new(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        rejected = make_client_file(db, user.id, vehicle.id, status=ClientFileStatus.REJECTED)
        data = ClientFileCreate(vehicle_id=vehicle.id, file_type=ClientFileType.SALE)

        cf = get_or_create_client_file(db, user.id, data)

        assert cf.id == rejected.id
        assert cf.status == ClientFileStatus.PENDING


class TestGetClientFile:

    def test_returns_file_by_id(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        created = make_client_file(db, user.id, vehicle.id)

        result = get_client_file(db, created.id)

        assert result.id == created.id

    def test_raises_404_when_not_found(self, db):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            get_client_file(db, 9999)
        assert exc.value.status_code == 404


class TestGetClientFileByUser:

    def test_returns_active_file(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)

        result = get_client_file_by_user(db, user.id)

        assert result.id == cf.id

    def test_ignores_cancelled_file(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        make_client_file(db, user.id, vehicle.id, status=ClientFileStatus.CANCELLED)

        result = get_client_file_by_user(db, user.id)

        assert result is None

    def test_returns_none_when_no_file(self, db):
        user = make_user(db)

        result = get_client_file_by_user(db, user.id)

        assert result is None


class TestUpdateStatus:

    def test_updates_status(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)

        updated = update_status(db, cf.id, ClientFileStatus.IN_PROGRESS)

        assert updated.status == ClientFileStatus.IN_PROGRESS

    def test_all_statuses_except_approved_are_applicable(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)

        for s in [ClientFileStatus.IN_PROGRESS, ClientFileStatus.REJECTED, ClientFileStatus.CANCELLED]:
            update_status(db, cf.id, s)
            db.refresh(cf)
            assert cf.status == s

    def test_approved_raises_if_documents_not_all_validated(self, db):
        from fastapi import HTTPException
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        make_document(db, cf.id, DocumentType.CNI, status=DocumentStatus.VALIDATED)

        with pytest.raises(HTTPException) as exc:
            update_status(db, cf.id, ClientFileStatus.APPROVED)
        assert exc.value.status_code == 400

    def test_approved_succeeds_when_all_documents_validated(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        for doc_type in DocumentType:
            make_document(db, cf.id, doc_type, status=DocumentStatus.VALIDATED)
        db.refresh(cf)

        updated = update_status(db, cf.id, ClientFileStatus.APPROVED)

        assert updated.status == ClientFileStatus.APPROVED

    def test_cancelled_saves_cancellation_reason(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)

        updated = update_status(db, cf.id, ClientFileStatus.CANCELLED, cancellation_reason="Doublon")

        assert updated.cancellation_reason == "Doublon"
        assert updated.rejection_reason is None

    def test_rejected_saves_rejection_reason(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)

        updated = update_status(db, cf.id, ClientFileStatus.REJECTED, rejection_reason="Pièces invalides")

        assert updated.rejection_reason == "Pièces invalides"
        assert updated.cancellation_reason is None

    def test_changing_status_clears_previous_reason(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        update_status(db, cf.id, ClientFileStatus.CANCELLED, cancellation_reason="Raison A")

        updated = update_status(db, cf.id, ClientFileStatus.PENDING)

        assert updated.cancellation_reason is None
        assert updated.rejection_reason is None


class TestActiveFilesLimit:

    def test_raises_when_max_active_files_reached(self, db):
        from fastapi import HTTPException
        user = make_user(db)
        for i in range(MAX_ACTIVE_FILES):
            v = make_vehicle(db, vin=f"VIN00000000000{i:04d}")
            make_client_file(db, user.id, v.id, status=ClientFileStatus.PENDING)
        extra_vehicle = make_vehicle(db, vin="VIN999999999EXTRA")
        data = ClientFileCreate(vehicle_id=extra_vehicle.id, file_type=ClientFileType.SALE)

        with pytest.raises(HTTPException) as exc:
            get_or_create_client_file(db, user.id, data)
        assert exc.value.status_code == 400

    def test_raises_when_reopening_with_max_active_files_reached(self, db):
        from fastapi import HTTPException
        user = make_user(db)
        vehicles = []
        for i in range(MAX_ACTIVE_FILES):
            v = make_vehicle(db, vin=f"VIN10000000000{i:04d}")
            make_client_file(db, user.id, v.id, status=ClientFileStatus.PENDING)
            vehicles.append(v)
        cancelled_v = make_vehicle(db, vin="VIN_CANCELLED_001")
        make_client_file(db, user.id, cancelled_v.id, status=ClientFileStatus.CANCELLED)
        data = ClientFileCreate(vehicle_id=cancelled_v.id, file_type=ClientFileType.SALE)

        with pytest.raises(HTTPException) as exc:
            get_or_create_client_file(db, user.id, data)
        assert exc.value.status_code == 400

    def test_allows_creating_up_to_max_active_files(self, db):
        user = make_user(db)
        for i in range(MAX_ACTIVE_FILES):
            v = make_vehicle(db, vin=f"VIN20000000000{i:04d}")
            data = ClientFileCreate(vehicle_id=v.id, file_type=ClientFileType.SALE)
            cf = get_or_create_client_file(db, user.id, data)
            assert cf.status == ClientFileStatus.PENDING


class TestComputeProgress:

    def test_returns_zero_with_no_documents(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)

        assert compute_progress(cf) == 0

    def test_returns_correct_percentage(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        make_document(db, cf.id, DocumentType.CNI, status=DocumentStatus.VALIDATED)
        make_document(db, cf.id, DocumentType.RIB, status=DocumentStatus.VALIDATED)
        db.refresh(cf)

        progress = compute_progress(cf)

        assert progress == int(2 / TOTAL_DOCUMENT_TYPES * 100)

    def test_returns_100_when_all_validated(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        for doc_type in DocumentType:
            make_document(db, cf.id, doc_type, status=DocumentStatus.VALIDATED)
        db.refresh(cf)

        assert compute_progress(cf) == 100

    def test_pending_docs_do_not_count(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        make_document(db, cf.id, DocumentType.CNI, status=DocumentStatus.PENDING)
        db.refresh(cf)

        assert compute_progress(cf) == 0


# ── document_service ──────────────────────────────────────────────────────────

class TestUploadDocument:

    def test_creates_document_record(self, db, tmp_path, monkeypatch):
        import app.services.document_service as svc
        monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        file = MockUploadFile(FAKE_PDF, "cni.pdf", "application/pdf")

        doc = asyncio.run(upload_document(db, cf.id, DocumentType.CNI, file))

        assert doc.id is not None
        assert doc.document_type == DocumentType.CNI
        assert doc.status == DocumentStatus.PENDING
        assert doc.is_locked is False

    def test_saves_file_to_disk(self, db, tmp_path, monkeypatch):
        import app.services.document_service as svc
        monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        file = MockUploadFile(FAKE_PDF, "cni.pdf", "application/pdf")

        doc = asyncio.run(upload_document(db, cf.id, DocumentType.CNI, file))

        assert Path(doc.file_path).exists()

    def test_replaces_existing_unlocked_document(self, db, tmp_path, monkeypatch):
        import app.services.document_service as svc
        monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        make_document(db, cf.id, DocumentType.CNI, status=DocumentStatus.REFUSED, is_locked=False)
        file = MockUploadFile(FAKE_PDF, "cni_v2.pdf", "application/pdf")

        asyncio.run(upload_document(db, cf.id, DocumentType.CNI, file))

        assert db.query(Document).filter(Document.client_file_id == cf.id).count() == 1

    def test_replaced_document_resets_to_pending(self, db, tmp_path, monkeypatch):
        import app.services.document_service as svc
        monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        make_document(db, cf.id, DocumentType.CNI, status=DocumentStatus.REFUSED)
        file = MockUploadFile(FAKE_PDF, "cni_v2.pdf", "application/pdf")

        doc = asyncio.run(upload_document(db, cf.id, DocumentType.CNI, file))

        assert doc.status == DocumentStatus.PENDING
        assert doc.rejection_reason is None

    def test_rejects_unsupported_extension(self, db, tmp_path, monkeypatch):
        import app.services.document_service as svc
        from fastapi import HTTPException
        monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        file = MockUploadFile(b"data", "doc.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with pytest.raises(HTTPException) as exc:
            asyncio.run(upload_document(db, cf.id, DocumentType.CNI, file))
        assert exc.value.status_code == 422

    def test_rejects_pdf_extension_with_non_pdf_content(self, db, tmp_path, monkeypatch):
        import app.services.document_service as svc
        from fastapi import HTTPException
        monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        # Contenu xlsx (ZIP) déguisé en .pdf
        file = MockUploadFile(b"PK\x03\x04fake xlsx content", "cni.pdf", "application/pdf")

        with pytest.raises(HTTPException) as exc:
            asyncio.run(upload_document(db, cf.id, DocumentType.CNI, file))
        assert exc.value.status_code == 422

    def test_rejects_file_too_large(self, db, tmp_path, monkeypatch):
        import app.services.document_service as svc
        from fastapi import HTTPException
        monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
        monkeypatch.setattr(svc, "MAX_FILE_SIZE", 10)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        file = MockUploadFile(b"x" * 100, "big.pdf", "application/pdf")

        with pytest.raises(HTTPException) as exc:
            asyncio.run(upload_document(db, cf.id, DocumentType.CNI, file))
        assert exc.value.status_code == 422

    def test_rejects_upload_on_locked_document(self, db, tmp_path, monkeypatch):
        import app.services.document_service as svc
        from fastapi import HTTPException
        monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        make_document(db, cf.id, DocumentType.CNI, is_locked=True)
        file = MockUploadFile(FAKE_PDF, "cni.pdf", "application/pdf")

        with pytest.raises(HTTPException) as exc:
            asyncio.run(upload_document(db, cf.id, DocumentType.CNI, file))
        assert exc.value.status_code == 403


class TestLockUnlockDocument:

    def test_lock_sets_status_processing(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        doc = make_document(db, cf.id)

        locked = lock_document(db, doc.id)

        assert locked.is_locked is True
        assert locked.status == DocumentStatus.PROCESSING

    def test_unlock_sets_status_pending(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        doc = make_document(db, cf.id, status=DocumentStatus.PROCESSING, is_locked=True)

        unlocked = unlock_document(db, doc.id)

        assert unlocked.is_locked is False
        assert unlocked.status == DocumentStatus.PENDING


class TestValidateRefuseDocument:

    def test_validate_sets_status_and_locks(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        doc = make_document(db, cf.id, status=DocumentStatus.PROCESSING, is_locked=True)

        validated = validate_document(db, doc.id)

        assert validated.status == DocumentStatus.VALIDATED
        assert validated.is_locked is True
        assert validated.rejection_reason is None

    def test_refuse_sets_status_and_unlocks(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        doc = make_document(db, cf.id, status=DocumentStatus.PROCESSING, is_locked=True)

        refused = refuse_document(db, doc.id, DocumentRefuse(rejection_reason="Document illisible"))

        assert refused.status == DocumentStatus.REFUSED
        assert refused.is_locked is False
        assert refused.rejection_reason == "Document illisible"

    def test_refuse_raises_404_on_missing_doc(self, db):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            refuse_document(db, 9999, DocumentRefuse(rejection_reason="raison"))
        assert exc.value.status_code == 404


# ── favorite_service ──────────────────────────────────────────────────────────

class TestToggleFavorite:

    def test_adds_favorite_returns_true(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)

        result = toggle_favorite(db, user.id, vehicle.id)

        assert result is True
        assert db.query(Favorite).filter(Favorite.user_id == user.id).count() == 1

    def test_removes_existing_favorite_returns_false(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        toggle_favorite(db, user.id, vehicle.id)

        result = toggle_favorite(db, user.id, vehicle.id)

        assert result is False
        assert db.query(Favorite).filter(Favorite.user_id == user.id).count() == 0

    def test_toggle_twice_restores_favorite(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        toggle_favorite(db, user.id, vehicle.id)
        toggle_favorite(db, user.id, vehicle.id)

        result = toggle_favorite(db, user.id, vehicle.id)

        assert result is True


class TestIsFavorite:

    def test_returns_true_when_favorited(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        toggle_favorite(db, user.id, vehicle.id)

        assert is_favorite(db, user.id, vehicle.id) is True

    def test_returns_false_when_not_favorited(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)

        assert is_favorite(db, user.id, vehicle.id) is False

    def test_returns_false_after_removal(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        toggle_favorite(db, user.id, vehicle.id)
        toggle_favorite(db, user.id, vehicle.id)

        assert is_favorite(db, user.id, vehicle.id) is False


class TestGetFavorites:

    def test_returns_favorited_vehicles(self, db):
        user = make_user(db)
        v1 = make_vehicle(db, vin="VIN000000000000001")
        v2 = make_vehicle(db, vin="VIN000000000000002")
        toggle_favorite(db, user.id, v1.id)
        toggle_favorite(db, user.id, v2.id)

        favorites = get_favorites(db, user.id)

        assert len(favorites) == 2
        ids = {v.id for v in favorites}
        assert v1.id in ids and v2.id in ids

    def test_returns_empty_list_when_no_favorites(self, db):
        user = make_user(db)

        assert get_favorites(db, user.id) == []

    def test_does_not_return_other_users_favorites(self, db):
        user1 = make_user(db, email="user1@test.com")
        user2 = make_user(db, email="user2@test.com")
        vehicle = make_vehicle(db)
        toggle_favorite(db, user1.id, vehicle.id)

        assert get_favorites(db, user2.id) == []


# ── client_files router ───────────────────────────────────────────────────────


class TestClientFilesRouter:

    def test_my_file_list_requires_auth(self, client):
        response = client.get("/my-file", follow_redirects=False)
        assert response.status_code == 303

    def test_my_file_list_returns_200(self, client, db):
        user = make_user(db)
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.get("/my-file")
        assert response.status_code == 200

    def test_my_file_list_shows_client_file(self, client, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        make_client_file(db, user.id, vehicle.id)
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.get("/my-file")
        assert "Peugeot" in response.text

    def test_my_file_detail_requires_auth(self, client, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        response = client.get(f"/my-file/{cf.id}", follow_redirects=False)
        assert response.status_code == 303

    def test_my_file_detail_returns_200(self, client, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.get(f"/my-file/{cf.id}")
        assert response.status_code == 200

    def test_my_file_detail_shows_intro_modal_with_new_param(self, client, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.get(f"/my-file/{cf.id}?new=1")
        assert "intro-modal" in response.text

    def test_my_file_detail_wrong_user_redirects(self, client, db):
        owner = make_user(db)
        other = make_user(db, email="other@test.com")
        vehicle = make_vehicle(db)
        cf = make_client_file(db, owner.id, vehicle.id)
        client.cookies.set("access_token", user_cookie(other.id))
        response = client.get(f"/my-file/{cf.id}", follow_redirects=False)
        assert response.status_code == 303
        assert "/my-file" in response.headers["location"]

    def test_my_file_status_returns_json(self, client, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.get(f"/api/my-file/{cf.id}/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "PENDING"

    def test_my_file_status_wrong_user_returns_403(self, client, db):
        owner = make_user(db)
        other = make_user(db, email="other2@test.com")
        vehicle = make_vehicle(db)
        cf = make_client_file(db, owner.id, vehicle.id)
        client.cookies.set("access_token", user_cookie(other.id))
        response = client.get(f"/api/my-file/{cf.id}/status")
        assert response.status_code == 403

    def test_open_file_creates_and_redirects(self, client, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.post("/my-file/open", data={
            "vehicle_id": vehicle.id, "file_type": "SALE",
        }, follow_redirects=False)
        assert response.status_code == 303
        assert "/my-file/" in response.headers["location"]
        assert "new=1" in response.headers["location"]

    def test_upload_doc_success_redirects(self, client, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        client.cookies.set("access_token", user_cookie(user.id))
        mock_doc = MagicMock()
        mock_doc.client_file_id = cf.id
        with patch("app.routers.client_files.upload_document", new=AsyncMock(return_value=mock_doc)):
            response = client.post(
                f"/my-file/{cf.id}/documents/CNI",
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
                follow_redirects=False,
            )
        assert response.status_code == 303
        assert "success" in response.headers["location"]

    def test_upload_doc_error_redirects_with_error(self, client, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        client.cookies.set("access_token", user_cookie(user.id))
        with patch("app.routers.client_files.upload_document", new=AsyncMock(side_effect=Exception("Upload failed"))):
            response = client.post(
                f"/my-file/{cf.id}/documents/CNI",
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
                follow_redirects=False,
            )
        assert response.status_code == 303
        assert "error" in response.headers["location"]

    def test_upload_doc_wrong_user_redirects(self, client, db):
        owner = make_user(db)
        other = make_user(db, email="other3@test.com")
        vehicle = make_vehicle(db)
        cf = make_client_file(db, owner.id, vehicle.id)
        client.cookies.set("access_token", user_cookie(other.id))
        response = client.post(
            f"/my-file/{cf.id}/documents/CNI",
            files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/my-file" in response.headers["location"]


# ── restore_client_file ───────────────────────────────────────────────────────

class TestRestoreClientFile:

    def _soft_delete(self, db, cf):
        from datetime import datetime, timezone
        cf.deleted_at = datetime.now(timezone.utc)
        cf.deleted_by_admin_id = 1
        cf.deleted_reason = "Test suppression"
        db.commit()

    def test_clears_deletion_fields(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        self._soft_delete(db, cf)

        restored = restore_client_file(db, cf.id)

        assert restored.deleted_at is None
        assert restored.deleted_by_admin_id is None
        assert restored.deleted_reason is None

    def test_preserves_original_status(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id, status=ClientFileStatus.IN_PROGRESS)
        self._soft_delete(db, cf)

        restored = restore_client_file(db, cf.id)

        assert restored.status == ClientFileStatus.IN_PROGRESS

    def test_raises_404_when_file_not_soft_deleted(self, db):
        from fastapi import HTTPException
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)

        with pytest.raises(HTTPException) as exc:
            restore_client_file(db, cf.id)
        assert exc.value.status_code == 404

    def test_raises_404_when_permanently_deleted(self, db):
        from datetime import datetime, timezone
        from fastapi import HTTPException
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        cf.deleted_at = datetime.now(timezone.utc)
        cf.permanently_deleted_at = datetime.now(timezone.utc)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            restore_client_file(db, cf.id)
        assert exc.value.status_code == 404

    def test_raises_404_for_unknown_id(self, db):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            restore_client_file(db, 9999)
        assert exc.value.status_code == 404


# ── get_all_client_files filters ──────────────────────────────────────────────

class TestGetAllClientFilesFilters:

    def test_returns_all_when_no_filter(self, db):
        user = make_user(db)
        v1 = make_vehicle(db, vin="VIN000000000ALL1")
        v2 = make_vehicle(db, vin="VIN000000000ALL2")
        make_client_file(db, user.id, v1.id)
        make_client_file(db, user.id, v2.id)

        result = get_all_client_files(db)

        assert len(result) == 2

    def test_filters_by_file_type_sale(self, db):
        user = make_user(db)
        v1 = make_vehicle(db, vin="VIN000000000SL01")
        v2 = make_vehicle(db, vin="VIN000000000RT01")
        sale = ClientFile(user_id=user.id, vehicle_id=v1.id, file_type=ClientFileType.SALE, status=ClientFileStatus.PENDING)
        rental = ClientFile(user_id=user.id, vehicle_id=v2.id, file_type=ClientFileType.RENTAL, status=ClientFileStatus.PENDING)
        db.add_all([sale, rental])
        db.commit()

        result = get_all_client_files(db, file_type=ClientFileType.SALE)

        assert len(result) == 1
        assert result[0].file_type == ClientFileType.SALE

    def test_filters_by_file_type_rental(self, db):
        user = make_user(db)
        v1 = make_vehicle(db, vin="VIN000000000SL02")
        v2 = make_vehicle(db, vin="VIN000000000RT02")
        sale = ClientFile(user_id=user.id, vehicle_id=v1.id, file_type=ClientFileType.SALE, status=ClientFileStatus.PENDING)
        rental = ClientFile(user_id=user.id, vehicle_id=v2.id, file_type=ClientFileType.RENTAL, status=ClientFileStatus.PENDING)
        db.add_all([sale, rental])
        db.commit()

        result = get_all_client_files(db, file_type=ClientFileType.RENTAL)

        assert len(result) == 1
        assert result[0].file_type == ClientFileType.RENTAL

    def test_filters_by_status(self, db):
        user = make_user(db)
        v1 = make_vehicle(db, vin="VIN000000000ST01")
        v2 = make_vehicle(db, vin="VIN000000000ST02")
        make_client_file(db, user.id, v1.id, status=ClientFileStatus.PENDING)
        make_client_file(db, user.id, v2.id, status=ClientFileStatus.IN_PROGRESS)

        result = get_all_client_files(db, status=ClientFileStatus.PENDING)

        assert len(result) == 1
        assert result[0].status == ClientFileStatus.PENDING

    def test_excludes_soft_deleted_files(self, db):
        from datetime import datetime, timezone
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        cf.deleted_at = datetime.now(timezone.utc)
        db.commit()

        result = get_all_client_files(db)

        assert len(result) == 0

    def test_sort_created_at_desc(self, db):
        from datetime import datetime, timezone, timedelta
        user = make_user(db)
        v1 = make_vehicle(db, vin="VIN000000000DT01")
        v2 = make_vehicle(db, vin="VIN000000000DT02")
        cf_old = make_client_file(db, user.id, v1.id)
        cf_new = make_client_file(db, user.id, v2.id)
        cf_old.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        cf_new.created_at = datetime.now(timezone.utc)
        db.commit()

        result = get_all_client_files(db, sort_by="created_at", sort_order="desc")

        assert result[0].id == cf_new.id
        assert result[1].id == cf_old.id

    def test_sort_created_at_asc(self, db):
        from datetime import datetime, timezone, timedelta
        user = make_user(db)
        v1 = make_vehicle(db, vin="VIN000000000DT03")
        v2 = make_vehicle(db, vin="VIN000000000DT04")
        cf_old = make_client_file(db, user.id, v1.id)
        cf_new = make_client_file(db, user.id, v2.id)
        cf_old.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        cf_new.created_at = datetime.now(timezone.utc)
        db.commit()

        result = get_all_client_files(db, sort_by="created_at", sort_order="asc")

        assert result[0].id == cf_old.id
        assert result[1].id == cf_new.id

    def test_combined_file_type_and_status_filter(self, db):
        user = make_user(db)
        v1 = make_vehicle(db, vin="VIN000000000CB01")
        v2 = make_vehicle(db, vin="VIN000000000CB02")
        v3 = make_vehicle(db, vin="VIN000000000CB03")
        sale_pending = ClientFile(user_id=user.id, vehicle_id=v1.id, file_type=ClientFileType.SALE, status=ClientFileStatus.PENDING)
        sale_in_progress = ClientFile(user_id=user.id, vehicle_id=v2.id, file_type=ClientFileType.SALE, status=ClientFileStatus.IN_PROGRESS)
        rental_pending = ClientFile(user_id=user.id, vehicle_id=v3.id, file_type=ClientFileType.RENTAL, status=ClientFileStatus.PENDING)
        db.add_all([sale_pending, sale_in_progress, rental_pending])
        db.commit()

        result = get_all_client_files(db, file_type=ClientFileType.SALE, status=ClientFileStatus.PENDING)

        assert len(result) == 1
        assert result[0].file_type == ClientFileType.SALE
        assert result[0].status == ClientFileStatus.PENDING
