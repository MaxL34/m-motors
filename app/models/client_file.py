from enum import Enum
from sqlalchemy import Column, Integer, Float, DateTime, Enum as SqlEnum, ForeignKey, UniqueConstraint, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class ClientFileStatus(str, Enum):
    """Status of the client file."""
    PENDING = "PENDING"         # dossier ouvert, en attente de traitement
    IN_PROGRESS = "IN_PROGRESS" # en cours de traitement par un agent
    APPROVED = "APPROVED"       # dossier validé
    REJECTED = "REJECTED"       # dossier refusé
    CANCELLED = "CANCELLED"     # dossier annulé
    COMPLETED = "COMPLETED"     # transaction finalisée


class ClientFileType(str, Enum):
    """Type of the client file."""
    SALE = "SALE"
    RENTAL = "RENTAL"

class ClientFile(Base):
    """SQLAlchemy model for a client file in the application M-Motors.

    Attributes:
        id: Unique identifier
        user_id: Foreign key to the user who created the file
        vehicle_id: Foreign key to the vehicle associated with the file
        file_type: Type of the file (SALE or RENTAL)
        status: Status of the file (PENDING, APPROVED, REJECTED, etc.)
        agreed_price: The price agreed at the time of client file creation (for sale or rental)
        notes: Optional notes or comments about the file (admin only)
        created_at: Creation timestamp
        updated_at: Last modification update
    """

    __tablename__ = "client_files"

    # Identifiers
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)

    # File details
    agreed_price = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    file_type = Column(SqlEnum(ClientFileType), nullable=False)

    # Status
    status = Column(SqlEnum(ClientFileStatus), default=ClientFileStatus.PENDING, nullable=False)
    cancellation_reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'vehicle_id', name='unique_user_vehicle_file'),
    )

    # Relationships
    user = relationship("User", back_populates="client_files")
    vehicle = relationship("Vehicle", back_populates="client_files")
    documents = relationship("Document", back_populates="client_file")