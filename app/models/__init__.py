"""This module imports all the models used in the application M-Motors."""

from app.database import Base
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleStatusHistory, StatusAction
from app.models.client_file import ClientFile, ClientFileStatus, ClientFileType
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.favorite import Favorite

__all__ = [
    "Base",
    "User",
    "Vehicle",
    "VehicleStatusHistory",
    "StatusAction",
    "ClientFile",
    "ClientFileStatus",
    "ClientFileType",
    "Document",
    "DocumentType",
    "DocumentStatus",
    "Favorite",
]
