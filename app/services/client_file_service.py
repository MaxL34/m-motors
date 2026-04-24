from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.client_file import ClientFile, ClientFileStatus
from app.models.document import DocumentStatus
from app.schemas.client_file_schema import ClientFileCreate

# Nombre total de types de pièces justificatives requis
TOTAL_DOCUMENT_TYPES = 8


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


def get_or_create_client_file(db: Session, user_id: int, data: ClientFileCreate) -> ClientFile:
    existing = db.query(ClientFile).filter(
        ClientFile.user_id == user_id,
        ClientFile.vehicle_id == data.vehicle_id,
    ).first()
    if existing:
        # Réouvrir un dossier annulé ou refusé plutôt que d'en créer un nouveau
        # (contrainte unique user_id + vehicle_id)
        if existing.status in (ClientFileStatus.CANCELLED, ClientFileStatus.REJECTED):
            existing.status = ClientFileStatus.PENDING
            existing.file_type = data.file_type
            db.commit()
            db.refresh(existing)
        return existing
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


def update_status(db: Session, file_id: int, new_status: ClientFileStatus) -> ClientFile:
    client_file = get_client_file(db, file_id)
    client_file.status = new_status
    db.commit()
    db.refresh(client_file)
    return client_file


def compute_progress(client_file: ClientFile) -> int:
    """Retourne le pourcentage d'avancement basé sur les documents validés."""
    if not client_file.documents:
        return 0
    validated = sum(1 for d in client_file.documents if d.status == DocumentStatus.VALIDATED)
    return int((validated / TOTAL_DOCUMENT_TYPES) * 100)
