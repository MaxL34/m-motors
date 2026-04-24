import asyncio
from pathlib import Path

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
    get_client_file,
    get_client_file_by_user,
    get_or_create_client_file,
    update_status,
    TOTAL_DOCUMENT_TYPES,
)
from app.services.document_service import (
    lock_document,
    refuse_document,
    unlock_document,
    upload_document,
    validate_document,
)
from app.services.favorite_service import get_favorites, is_favorite, toggle_favorite
from app.utils.security import hash_password


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

    def test_all_statuses_are_applicable(self, db):
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)

        for s in [ClientFileStatus.IN_PROGRESS, ClientFileStatus.APPROVED, ClientFileStatus.REJECTED]:
            update_status(db, cf.id, s)
            db.refresh(cf)
            assert cf.status == s


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
        file = MockUploadFile(b"pdf content", "cni.pdf", "application/pdf")

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
        file = MockUploadFile(b"pdf content", "cni.pdf", "application/pdf")

        doc = asyncio.run(upload_document(db, cf.id, DocumentType.CNI, file))

        assert Path(doc.file_path).exists()

    def test_replaces_existing_unlocked_document(self, db, tmp_path, monkeypatch):
        import app.services.document_service as svc
        monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        make_document(db, cf.id, DocumentType.CNI, status=DocumentStatus.REFUSED, is_locked=False)
        file = MockUploadFile(b"new content", "cni_v2.pdf", "application/pdf")

        asyncio.run(upload_document(db, cf.id, DocumentType.CNI, file))

        assert db.query(Document).filter(Document.client_file_id == cf.id).count() == 1

    def test_replaced_document_resets_to_pending(self, db, tmp_path, monkeypatch):
        import app.services.document_service as svc
        monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        make_document(db, cf.id, DocumentType.CNI, status=DocumentStatus.REFUSED)
        file = MockUploadFile(b"new content", "cni_v2.pdf", "application/pdf")

        doc = asyncio.run(upload_document(db, cf.id, DocumentType.CNI, file))

        assert doc.status == DocumentStatus.PENDING
        assert doc.rejection_reason is None

    def test_rejects_unsupported_mime_type(self, db, tmp_path, monkeypatch):
        import app.services.document_service as svc
        from fastapi import HTTPException
        monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
        user = make_user(db)
        vehicle = make_vehicle(db)
        cf = make_client_file(db, user.id, vehicle.id)
        file = MockUploadFile(b"data", "doc.docx", "application/msword")

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
        file = MockUploadFile(b"content", "cni.pdf", "application/pdf")

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
