from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class DocumentType(str, Enum):
    CNI = "CNI"
    DRIVING_LICENSE = "DRIVING_LICENSE"
    PROOF_OF_ADDRESS = "PROOF_OF_ADDRESS"
    PAY_SLIP_1 = "PAY_SLIP_1"
    PAY_SLIP_2 = "PAY_SLIP_2"
    PAY_SLIP_3 = "PAY_SLIP_3"
    TAX_NOTICE = "TAX_NOTICE"
    RIB = "RIB"


class DocumentStatus(str, Enum):
    PENDING = "PENDING"       # à envoyer / en attente
    PROCESSING = "PROCESSING" # en cours de traitement (verrouillé)
    VALIDATED = "VALIDATED"   # validé
    REFUSED = "REFUSED"       # refusé (à renvoyer)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_file_id: Mapped[int] = mapped_column(ForeignKey("client_files.id"), nullable=False)

    document_type: Mapped[DocumentType]
    status: Mapped[DocumentStatus] = mapped_column(default=DocumentStatus.PENDING)
    is_locked: Mapped[bool] = mapped_column(default=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int]
    mime_type: Mapped[str] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    client_file = relationship("ClientFile", back_populates="documents")
