from enum import Enum
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, Enum as SqlEnum, ForeignKey, UniqueConstraint, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class DocumentType(str, Enum):
    """Type of dicuments that can be attached to a client file"""
    INVOICE = "INVOICE"
    CONTRACT = "CONTRACT"
    INSURANCE = "INSURANCE"
    REGISTRATION = "REGISTRATION"
    IDENTITY_PROOF = "IDENTITY_PROOF"
    ADDRESS_PROOF = "ADDRESS_PROOF"
    INSPECTION = "INSPECTION"
    OTHER = "OTHER"

class Document(Base):
    """SQLAlchemy model for a document in the application M-Motors.

    Attributes:
        id: Unique identifier
        client_file_id: Foreign key to the associated client file
        document_type: Type of the document (e.g., "ID_PROOF", "ADDRESS_PROOF", etc.)
        file_name: Original name of the uploaded file
        file_path: Path to the stored document file
        file_size: Size of the file in bytes
        mime_type: MIME type of the file (e.g., "application/pdf", "image/jpeg")
        expiration_date: Optional expiration date for documents that have a validity period (e.g., insurance)
        created_at: Creation timestamp
        updated_at: Last modification update
    """

    __tablename__ = "documents"

    # Identifiers
    id = Column(Integer, primary_key=True, index=True)
    client_file_id = Column(Integer, ForeignKey("client_files.id"), nullable=False)

    # Document details
    document_type = Column(SqlEnum(DocumentType), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    expiration_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    client_file = relationship("ClientFile", back_populates="documents")
    documents = relationship("Document", back_populates="client_file")