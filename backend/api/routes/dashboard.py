from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, text
from database.connection import get_db
from database.models.database import Trabajador, Sensor, Alerta, LecturaSensor
from api.auth.dependencies import get_current_user

router = APIRouter(tags=["Dashboard y Estadísticas"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/health")
async def health_check():
    """Endpoint de health check para verificar estado del servicio"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.1.0",
        "environment": "development",
    }


@router.get("/")
async def get_dashboard(
    db: DbSession, current_user: Trabajador = Depends(get_current_user)
):
    """Obtener datos del dashboard del usuario"""

    # Obtener ID de empresa del usuario actual
    id_empresa = current_user.id_empresa

    # Usar consultas SQL directas para evitar problemas de ORM
    result = await db.execute(
        text("SELECT COUNT(*) FROM sensores WHERE id_empresa = :empresa_id"),
        {"empresa_id": id_empresa},
    )
    total_sensores = result.scalar()

    result = await db.execute(
        text(
            "SELECT COUNT(*) FROM sensores WHERE id_empresa = :empresa_id AND activo = true"
        ),
        {"empresa_id": id_empresa},
    )
    sensores_activos = result.scalar()

    result = await db.execute(
        text(
            "SELECT COUNT(*) FROM alertas WHERE id_empresa = :empresa_id AND resuelta = false"
        ),
        {"empresa_id": id_empresa},
    )
    alertas_pendientes = result.scalar()

    return {
        "total_cultivos": total_sensores,
        "cultivos_activos": sensores_activos,
        "alertas_pendientes": alertas_pendientes,
    }


@router.get("/sensores")
async def get_dashboard_sensors(
    db: DbSession, current_user: Trabajador = Depends(get_current_user), horas: int = 24
):
    """Obtener dashboard completo de sensores IoT"""
    return {"message": "Dashboard de sensores no implementado aún"}


@router.get("/sensores/estadisticas")
async def get_sensor_statistics(
    db: DbSession, current_user: Trabajador = Depends(get_current_user)
):
    """Obtener estadísticas generales de sensores"""
    return {"message": "Estadísticas de sensores no implementadas aún"}


@router.get("/kpis")
async def get_dashboard_kpis(
    db: DbSession, current_user: Trabajador = Depends(get_current_user)
):
    """Obtener KPIs principales del dashboard"""
    from api.models import DashboardKPIs
    from datetime import timedelta

    # Obtener ID de empresa del usuario actual
    id_empresa = current_user.id_empresa

    # Contar sensores activos de la empresa
    result_activos = await db.execute(
        select(func.count())
        .select_from(Sensor)
        .where(Sensor.id_empresa == id_empresa, Sensor.estado == "activo")
    )
    sensores_activos = result_activos.scalar()

    # Contar sensores totales como "cultivos monitoreados"
    result_totales = await db.execute(
        select(func.count()).select_from(Sensor).where(Sensor.id_empresa == id_empresa)
    )
    cultivos_monitoreados = result_totales.scalar()

    # Contar alertas pendientes (mediante join con Sensor para filtrar por empresa)
    result_alertas = await db.execute(
        select(func.count())
        .select_from(Alerta)
        .join(Sensor)
        .where(Sensor.id_empresa == id_empresa, Alerta.estado == "pendiente")
    )
    alertas_pendientes = result_alertas.scalar()

    # Calcular promedios de temperatura y humedad (últimas 24 horas)
    fecha_limite = datetime.utcnow() - timedelta(hours=24)

    result_temp = await db.execute(
        select(func.avg(LecturaSensor.temperatura))
        .join(Sensor)
        .where(
            Sensor.id_empresa == id_empresa,
            LecturaSensor.timestamp >= fecha_limite,
            LecturaSensor.temperatura.isnot(None),
        )
    )
    temp_promedio = result_temp.scalar()

    result_humedad = await db.execute(
        select(func.avg(LecturaSensor.humedad_aire))
        .join(Sensor)
        .where(
            Sensor.id_empresa == id_empresa,
            LecturaSensor.timestamp >= fecha_limite,
            LecturaSensor.humedad_aire.isnot(None),
        )
    )
    humedad_promedio = result_humedad.scalar()

    # Calcular áreas bajo monitoreo (10 hectáreas por sensor como aproximación)
    areas_monitoreadas = cultivos_monitoreados * 10.0

    # Estimar producción (1000 kg por sensor como aproximación)
    produccion_estimada = cultivos_monitoreados * 1000.0

    return DashboardKPIs(
        sensores_activos=sensores_activos,
        cultivos_monitoreados=cultivos_monitoreados,
        alertas_pendientes=alertas_pendientes,
        ultima_actualizacion=datetime.utcnow().isoformat(),
        temperaturas_promedio=round(float(temp_promedio), 1) if temp_promedio else None,
        humedad_promedio=round(float(humedad_promedio), 1)
        if humedad_promedio
        else None,
        areas_bajo_monitoreo=areas_monitoreadas,
        produccion_estimada=produccion_estimada,
    )


@router.get("/sensor-data/{sensor_id}")
async def get_sensor_data(
    sensor_id: int,
    db: DbSession,
    days: int = 7,
    current_user: Trabajador = Depends(get_current_user),
):
    """Obtener datos históricos de un sensor"""
    # Verificar que el sensor pertenece a la empresa
    result = await db.execute(
        select(Sensor).where(
            Sensor.id_sensor == sensor_id, Sensor.id_empresa == current_user.id_empresa
        )
    )
    sensor = result.scalars().first()

    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sensor no encontrado"
        )

    # Retornar datos mock por ahora
    return {
        "sensor_id": sensor_id,
        "data": [],
        "message": "Datos históricos no implementados aún",
    }


@router.get("/trabajadores")
async def get_workers(
    db: DbSession, current_user: Trabajador = Depends(get_current_user)
):
    """Obtener lista de trabajadores de la empresa del usuario actual"""
    # Obtener todos los trabajadores de la misma empresa
    result = await db.execute(
        select(Trabajador).where(Trabajador.id_empresa == current_user.id_empresa)
    )
    trabajadores = result.scalars().all()

    # Formatear datos
    trabajadores_data = []
    for trabajador in trabajadores:
        trabajadores_data.append(
            {
                "id": str(trabajador.id_trabajador),
                "name": f"{trabajador.nombre} {trabajador.apellido}",
                "dni": trabajador.dni,
                "email": trabajador.email,
                "phone": trabajador.telefono or "N/A",
                "role": trabajador.rol,
                "department": "Producción"
                if trabajador.rol == "worker"
                else "Administración",
                "assignedSensors": [],  # TODO: Implementar asignaciones reales
                "status": "active" if trabajador.activo else "inactive",
                "lastActive": trabajador.fecha_contratacion.strftime("%Y-%m-%d")
                if trabajador.fecha_contratacion
                else "N/A",
            }
        )

    return trabajadores_data


@router.get("/produccion")
async def get_production_data(
    db: DbSession, current_user: Trabajador = Depends(get_current_user)
):
    """Obtener datos de producción"""
    result = await db.execute(
        select(Sensor).where(Sensor.id_empresa == current_user.id_empresa)
    )
    sensores = result.scalars().all()

    return {
        "total_hectareas": len(sensores) * 10,  # Mock: 10 hectáreas por sensor
        "cultivos_por_tipo": {"maiz": 2, "soja": 1, "trigo": 1},  # Mock data
        "produccion_estimada": len(sensores) * 1000,  # Mock: 1000 kg por sensor
        "rendimiento_promedio": 85.5,  # Mock percentage
    }
