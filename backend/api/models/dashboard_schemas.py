from pydantic import BaseModel
from typing import Optional


class DashboardResponse(BaseModel):
    """Modelo para respuesta del dashboard"""

    total_cultivos: int
    cultivos_activos: int
    alertas_pendientes: int


class DashboardKPIs(BaseModel):
    """KPIs del dashboard"""

    sensores_activos: int
    cultivos_monitoreados: int
    alertas_pendientes: int
    ultima_actualizacion: str
    temperaturas_promedio: Optional[float] = None
    humedad_promedio: Optional[float] = None
    areas_bajo_monitoreo: Optional[float] = None
    produccion_estimada: Optional[float] = None
