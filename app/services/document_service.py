from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus, DocumentType
from app.schemas.document_schema import DocumentRefuse

UPLOAD_DIR = Path("uploads/documents")
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 Mo

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

# Signatures magic bytes → (mime_type, extensions autorisées)
MAGIC_SIGNATURES: list[tuple[bytes, str, set[str]]] = [
    (b"%PDF",        "application/pdf", {".pdf"}),
    (b"\xff\xd8\xff", "image/jpeg",     {".jpg", ".jpeg"}),
    (b"\x89PNG",     "image/png",       {".png"}),
]


def _validate_file(filename: str, content: bytes) -> str:
    """Vérifie l'extension et les magic bytes. Retourne le mime_type détecté."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Extension '{ext}' non supportée. Utilisez PDF, JPG ou PNG.",
        )
    for signature, mime_type, valid_exts in MAGIC_SIGNATURES:
        if content.startswith(signature):
            if ext not in valid_exts:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Le contenu du fichier ne correspond pas à son extension.",
                )
            return mime_type
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Format non supporté. Utilisez PDF, JPG ou PNG.",
    )


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
    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fichier trop volumineux (max 5 Mo).",
        )

    detected_mime = _validate_file(file.filename, contents)

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
        existing.mime_type = detected_mime
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
        mime_type=detected_mime,
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
