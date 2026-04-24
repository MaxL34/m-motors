import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus, DocumentType
from app.schemas.document_schema import DocumentRefuse

UPLOAD_DIR = Path("uploads/documents")
ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 Mo


def get_document(db: Session, doc_id: int) -> Document:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    return doc


def get_document_by_type(db: Session, client_file_id: int, doc_type: DocumentType) -> Document | None:
    return db.query(Document).filter(
        Document.client_file_id == client_file_id,
        Document.document_type == doc_type,
    ).first()


async def upload_document(
    db: Session,
    client_file_id: int,
    doc_type: DocumentType,
    file: UploadFile,
) -> Document:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Format non supporté. Utilisez PDF, JPG ou PNG.",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fichier trop volumineux (max 5 Mo).",
        )

    existing = get_document_by_type(db, client_file_id, doc_type)
    if existing and existing.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce document est verrouillé et ne peut pas être remplacé.",
        )

    dest_dir = UPLOAD_DIR / str(client_file_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix
    file_path = dest_dir / f"{doc_type.value}{ext}"
    file_path.write_bytes(contents)

    if existing:
        existing.file_name = file.filename
        existing.file_path = str(file_path)
        existing.file_size = len(contents)
        existing.mime_type = file.content_type
        existing.status = DocumentStatus.PENDING
        existing.rejection_reason = None
        db.commit()
        db.refresh(existing)
        return existing

    doc = Document(
        client_file_id=client_file_id,
        document_type=doc_type,
        status=DocumentStatus.PENDING,
        is_locked=False,
        file_name=file.filename,
        file_path=str(file_path),
        file_size=len(contents),
        mime_type=file.content_type,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def lock_document(db: Session, doc_id: int) -> Document:
    doc = get_document(db, doc_id)
    doc.is_locked = True
    doc.status = DocumentStatus.PROCESSING
    db.commit()
    db.refresh(doc)
    return doc


def unlock_document(db: Session, doc_id: int) -> Document:
    doc = get_document(db, doc_id)
    doc.is_locked = False
    doc.status = DocumentStatus.PENDING
    db.commit()
    db.refresh(doc)
    return doc


def validate_document(db: Session, doc_id: int) -> Document:
    doc = get_document(db, doc_id)
    doc.status = DocumentStatus.VALIDATED
    doc.is_locked = True
    doc.rejection_reason = None
    db.commit()
    db.refresh(doc)
    return doc


def refuse_document(db: Session, doc_id: int, data: DocumentRefuse) -> Document:
    doc = get_document(db, doc_id)
    doc.status = DocumentStatus.REFUSED
    doc.is_locked = False
    doc.rejection_reason = data.rejection_reason
    db.commit()
    db.refresh(doc)
    return doc
