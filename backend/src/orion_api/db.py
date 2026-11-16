from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from orion_api.config import settings

if not settings.database_url:
    engine = None
    SessionLocal = None
else:
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def require_session_factory():
    if SessionLocal is None:
        raise RuntimeError("ORION_DATABASE_URL não foi configurada.")
    return SessionLocal
