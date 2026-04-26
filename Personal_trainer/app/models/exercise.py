from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Exercise(Base):
    """Cached exercise data from ExerciseDB API."""

    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    body_part: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    equipment: Mapped[str] = mapped_column(String(100), nullable=False)
    target_muscle: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    secondary_muscles: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, default=list)
    gif_url: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, default=list)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
