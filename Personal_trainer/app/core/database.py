from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=not settings.is_production,
    poolclass=NullPool,
    connect_args={"statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def create_tables() -> None:
    """Create all tables on startup. create_all is idempotent — safe to run every boot."""
    try:
        async with engine.begin() as conn:
            from app.models import user, profile, schedule, workout, nutrition, exercise, conversation  # noqa: F401
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Could not connect to database on startup: {e}\n"
            "Check DATABASE_URL in your .env file."
        )


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
