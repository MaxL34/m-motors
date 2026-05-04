from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client_file import ClientFileType
from app.models.document import DocumentType
from app.models.user import User
from app.schemas.client_file_schema import ClientFileCreate
from app.services.client_file_service import (
    compute_progress,
    get_all_active_client_files_by_user,
    get_client_file,
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

FILE_STATUS_COLORS = {
    "APPROVED": "bg-green-50 text-green-700",
    "COMPLETED": "bg-green-50 text-green-700",
    "IN_PROGRESS": "bg-blue-50 text-blue-700",
    "REJECTED": "bg-red-50 text-red-700",
    "CANCELLED": "bg-red-50 text-red-700",
    "PENDING": "bg-gray-100 text-gray-600",
}


def _ctx(**kwargs):
    return {
        "document_labels": DOCUMENT_LABELS,
        "document_types": list(DocumentType),
        "status_labels": STATUS_LABELS,
        "file_status_labels": FILE_STATUS_LABELS,
        "file_status_colors": FILE_STATUS_COLORS,
        **kwargs,
    }


@router.get("/my-file", response_class=HTMLResponse)
def my_file_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    success: str = None,
    error: str = None,
):
    client_files = get_all_active_client_files_by_user(db, current_user.id)
    files_with_progress = [
        {"file": cf, "progress": compute_progress(cf)}
        for cf in client_files
    ]
    return templates.TemplateResponse(
        name="customer_file/index.html",
        request=request,
        context=_ctx(
            current_user=current_user,
            files_with_progress=files_with_progress,
            success=success,
            error=error,
        ),
    )


@router.get("/my-file/{file_id}", response_class=HTMLResponse)
def my_file_detail(
    request: Request,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    success: str = None,
    error: str = None,
):
    client_file = get_client_file(db, file_id)
    if client_file.user_id != current_user.id:
        return RedirectResponse("/my-file", status_code=303)
    progress = compute_progress(client_file)
    docs_by_type = {d.document_type: d for d in client_file.documents}
    return templates.TemplateResponse(
        name="customer_file/detail.html",
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


@router.get("/api/my-file/{file_id}/status")
def my_file_status(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    client_file = get_client_file(db, file_id)
    if client_file.user_id != current_user.id:
        return JSONResponse({"status": None, "label": None}, status_code=403)
    return JSONResponse({
        "status": client_file.status.value,
        "label": FILE_STATUS_LABELS[client_file.status.value],
        "updated_at": client_file.updated_at.isoformat() if client_file.updated_at else None,
    })


@router.post("/my-file/open", response_class=HTMLResponse)
def open_file(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    vehicle_id: int = Form(...),
    file_type: str = Form(...),
):
    from fastapi import HTTPException as _HTTPException
    try:
        data = ClientFileCreate(vehicle_id=vehicle_id, file_type=ClientFileType(file_type))
        get_or_create_client_file(db, current_user.id, data)
        return RedirectResponse("/my-file?success=Dossier+ouvert+avec+succès", status_code=303)
    except _HTTPException as e:
        return RedirectResponse(f"/vehicles/{vehicle_id}?error={quote(e.detail)}", status_code=303)


@router.post("/my-file/{file_id}/documents/{doc_type}", response_class=HTMLResponse)
async def upload_doc(
    request: Request,
    file_id: int,
    doc_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    file: UploadFile = File(...),
):
    client_file = get_client_file(db, file_id)
    if client_file.user_id != current_user.id:
        return RedirectResponse("/my-file", status_code=303)
    try:
        await upload_document(db, client_file.id, DocumentType(doc_type), file)
        return RedirectResponse(f"/my-file/{file_id}?success=Document+envoyé+avec+succès", status_code=303)
    except Exception as e:
        detail = e.detail if hasattr(e, "detail") else str(e)
        return RedirectResponse(f"/my-file/{file_id}?error={quote(str(detail))}", status_code=303)
