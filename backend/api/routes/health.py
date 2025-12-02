from fastapi import APIRouter, Depends
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from database.connection import get_db
from api.monitoring.health_check import HealthMonitor, HealthCheckResponse

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]

@router.get("/health", response_model=HealthCheckResponse)
async def health_check(db: DbSession):
    """Verificación de salud del servicio"""
    return await HealthMonitor.get_health_check(version="1.1.0", db_session=db)
