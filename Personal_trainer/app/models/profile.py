import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserProfile(Base):
    """All health-sensitive fields are stored as AES-256-GCM encrypted base64 strings."""

    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, index=True)

    # Encrypted fields (stored as base64 ciphertext)
    weight_kg: Mapped[str] = mapped_column(Text, nullable=False)
    height_cm: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[str] = mapped_column(Text, nullable=False)
    injuries: Mapped[str | None] = mapped_column(Text, nullable=True)
    workout_level: Mapped[str] = mapped_column(Text, nullable=False)  # Beginner/Intermediate/Advanced
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    gender: Mapped[str | None] = mapped_column(Text, nullable=True)

    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
