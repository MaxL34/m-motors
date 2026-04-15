"""This module imports all the models used in the application M-Motors."""

from app.models.user import User
from app.models import Vehicle
from app.models.client_file import ClientFile, ClientFileStatus, ClientFileType
from app.models.document import Document, DocumentType

__all__ = [
    "User",
    "Vehicle",
    "ClientFile",
    "ClientFileStatus",
    "ClientFileType",
    "Document",
    "DocumentType"
]