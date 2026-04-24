from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SqlEnum, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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

    id = Column(Integer, primary_key=True, index=True)
    client_file_id = Column(Integer, ForeignKey("client_files.id"), nullable=False)

    document_type = Column(SqlEnum(DocumentType), nullable=False)
    status = Column(SqlEnum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)
    rejection_reason = Column(Text, nullable=True)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    client_file = relationship("ClientFile", back_populates="documents")
