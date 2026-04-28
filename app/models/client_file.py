from enum import Enum
from typing import Optional
from sqlalchemy import Float, DateTime, Enum as SqlEnum, ForeignKey, UniqueConstraint, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ClientFileStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class ClientFileType(str, Enum):
    SALE = "SALE"
    RENTAL = "RENTAL"


class ClientFile(Base):
    __tablename__ = "client_files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)

    agreed_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_type: Mapped[ClientFileType] = mapped_column(SqlEnum(ClientFileType), nullable=False)

    status: Mapped[ClientFileStatus] = mapped_column(
        SqlEnum(ClientFileStatus), default=ClientFileStatus.PENDING, nullable=False
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'vehicle_id', name='unique_user_vehicle_file'),
    )

    user = relationship("User", back_populates="client_files")
    vehicle = relationship("Vehicle", back_populates="client_files")
    documents = relationship("Document", back_populates="client_file")
