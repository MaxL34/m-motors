from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client_file import ClientFileType
from app.models.document import DocumentType
from app.models.user import User
from app.schemas.client_file_schema import ClientFileCreate
from app.services.client_file_service import (
    compute_progress,
    get_client_file_by_user,
    get_or_create_client_file,
)
from app.services.document_service import upload_document
from app.utils.deps import require_user

router = APIRouter(tags=["client_files"])
templates = Jinja2Templates(directory="app/templates")

DOCUMENT_LABELS = {
    DocumentType.CNI: "Carte nationale d'identité",
    DocumentType.DRIVING_LICENSE: "Permis de conduire",
    DocumentType.PROOF_OF_ADDRESS: "Justificatif de domicile",
    DocumentType.PAY_SLIP_1: "Bulletin de salaire (1/3)",
    DocumentType.PAY_SLIP_2: "Bulletin de salaire (2/3)",
    DocumentType.PAY_SLIP_3: "Bulletin de salaire (3/3)",
    DocumentType.TAX_NOTICE: "Avis d'imposition",
    DocumentType.RIB: "RIB",
}

STATUS_LABELS = {
    "PENDING": "En attente",
    "PROCESSING": "En cours de traitement",
    "VALIDATED": "Validé",
    "REFUSED": "Refusé",
}

FILE_STATUS_LABELS = {
    "PENDING": "En attente",
    "IN_PROGRESS": "En cours de traitement",
    "APPROVED": "Approuvé",
    "REJECTED": "Refusé",
    "CANCELLED": "Annulé",
    "COMPLETED": "Finalisé",
}


def _ctx(**kwargs):
    return {
        "document_labels": DOCUMENT_LABELS,
        "document_types": list(DocumentType),
        "status_labels": STATUS_LABELS,
        "file_status_labels": FILE_STATUS_LABELS,
        **kwargs,
    }


@router.get("/my-file", response_class=HTMLResponse)
def my_file(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    success: str = None,
    error: str = None,
):
    client_file = get_client_file_by_user(db, current_user.id)
    progress = compute_progress(client_file) if client_file else 0
    docs_by_type = {}
    if client_file:
        docs_by_type = {d.document_type: d for d in client_file.documents}

    return templates.TemplateResponse(
        name="customer_file/index.html",
        request=request,
        context=_ctx(
            current_user=current_user,
            client_file=client_file,
            progress=progress,
            docs_by_type=docs_by_type,
            success=success,
            error=error,
        ),
    )


@router.post("/my-file/open", response_class=HTMLResponse)
def open_file(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    vehicle_id: int = Form(...),
    file_type: str = Form(...),
):
    data = ClientFileCreate(vehicle_id=vehicle_id, file_type=ClientFileType(file_type))
    get_or_create_client_file(db, current_user.id, data)
    return RedirectResponse("/my-file?success=Dossier+ouvert+avec+succès", status_code=303)


@router.post("/my-file/documents/{doc_type}", response_class=HTMLResponse)
async def upload_doc(
    request: Request,
    doc_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    file: UploadFile = File(...),
):
    client_file = get_client_file_by_user(db, current_user.id)
    if not client_file:
        return RedirectResponse("/my-file?error=Aucun+dossier+ouvert", status_code=303)
    try:
        await upload_document(db, client_file.id, DocumentType(doc_type), file)
        return RedirectResponse("/my-file?success=Document+envoyé+avec+succès", status_code=303)
    except Exception as e:
        from urllib.parse import quote
        detail = e.detail if hasattr(e, "detail") else str(e)
        return RedirectResponse(f"/my-file?error={quote(str(detail))}", status_code=303)
