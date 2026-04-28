from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.client_file import ClientFile, ClientFileStatus
from app.models.document import DocumentStatus
from app.schemas.client_file_schema import ClientFileCreate

TOTAL_DOCUMENT_TYPES = 8
MAX_ACTIVE_FILES = 3

ACTIVE_STATUSES = [
    ClientFileStatus.PENDING,
    ClientFileStatus.IN_PROGRESS,
    ClientFileStatus.APPROVED,
]


def get_client_file(db: Session, file_id: int) -> ClientFile:
    file = db.query(ClientFile).filter(ClientFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")
    return file


def get_client_file_by_user(db: Session, user_id: int) -> ClientFile | None:
    return (
        db.query(ClientFile)
        .filter(ClientFile.user_id == user_id)
        .filter(ClientFile.status.notin_([ClientFileStatus.CANCELLED]))
        .order_by(ClientFile.created_at.desc())
        .first()
    )


def _count_active_files(db: Session, user_id: int) -> int:
    return db.query(ClientFile).filter(
        ClientFile.user_id == user_id,
        ClientFile.status.in_(ACTIVE_STATUSES),
    ).count()


def get_or_create_client_file(db: Session, user_id: int, data: ClientFileCreate) -> ClientFile:
    existing = db.query(ClientFile).filter(
        ClientFile.user_id == user_id,
        ClientFile.vehicle_id == data.vehicle_id,
    ).first()
    if existing:
        if existing.status in (ClientFileStatus.CANCELLED, ClientFileStatus.REJECTED):
            if _count_active_files(db, user_id) >= MAX_ACTIVE_FILES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vous ne pouvez pas avoir plus de {MAX_ACTIVE_FILES} dossiers actifs simultanément.",
                )
            existing.status = ClientFileStatus.PENDING
            existing.file_type = data.file_type
            db.commit()
            db.refresh(existing)
        return existing
    if _count_active_files(db, user_id) >= MAX_ACTIVE_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vous ne pouvez pas avoir plus de {MAX_ACTIVE_FILES} dossiers actifs simultanément.",
        )
    client_file = ClientFile(
        user_id=user_id,
        vehicle_id=data.vehicle_id,
        file_type=data.file_type,
        status=ClientFileStatus.PENDING,
    )
    db.add(client_file)
    db.commit()
    db.refresh(client_file)
    return client_file


def get_all_client_files(db: Session) -> list[ClientFile]:
    return db.query(ClientFile).order_by(ClientFile.created_at.desc()).all()


def update_status(
    db: Session,
    file_id: int,
    new_status: ClientFileStatus,
    cancellation_reason: str | None = None,
    rejection_reason: str | None = None,
) -> ClientFile:
    client_file = get_client_file(db, file_id)
    if new_status == ClientFileStatus.APPROVED:
        db.refresh(client_file)
        validated_count = sum(
            1 for d in client_file.documents if d.status == DocumentStatus.VALIDATED
        )
        if validated_count < TOTAL_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tous les documents doivent être validés avant d'approuver le dossier ({validated_count}/{TOTAL_DOCUMENT_TYPES} validés).",
            )
    client_file.status = new_status
    client_file.cancellation_reason = cancellation_reason or None if new_status == ClientFileStatus.CANCELLED else None
    client_file.rejection_reason = rejection_reason or None if new_status == ClientFileStatus.REJECTED else None
    db.commit()
    db.refresh(client_file)
    return client_file


def compute_progress(client_file: ClientFile) -> int:
    """Retourne le pourcentage d'avancement basé sur les documents validés."""
    if not client_file.documents:
        return 0
    validated = sum(1 for d in client_file.documents if d.status == DocumentStatus.VALIDATED)
    return int((validated / TOTAL_DOCUMENT_TYPES) * 100)
