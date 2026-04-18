import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base


class EmailLogORM(Base):
    __tablename__ = "email_sent_logs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    car_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("inventory.id"), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    template_used: Mapped[str] = mapped_column(String(100), nullable=False, default="car_specs")
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
