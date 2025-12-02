from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from database.models.database import AsyncSessionLocal, SessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Obtener sesiones de la base de datos (Async)"""
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_db() -> Generator[Session, None, None]:
    """Obtener sesiones de la base de datos (Sync - Threadpool)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
