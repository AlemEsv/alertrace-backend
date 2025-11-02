from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.connection import get_db
from database.models.database import Trabajador, Sensor, Alerta
from api.auth.dependencies import get_current_user

router = APIRouter(
    tags=["Dashboard y Estadísticas"]
)


@router.get("/health")
def health_check():
    """Endpoint de health check para verificar estado del servicio"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.1.0",
        "environment": "development"
    }


@router.get("/")
async def obtener_dashboard(
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener datos del dashboard del usuario"""
    from sqlalchemy import text
    
    # Obtener ID de empresa del usuario actual
    id_empresa = current_user.id_empresa
    
    # Usar consultas SQL directas para evitar problemas de ORM
    result = db.execute(text("SELECT COUNT(*) FROM sensores WHERE id_empresa = :empresa_id"), 
                        {"empresa_id": id_empresa})
    total_sensores = result.scalar()
    
    result = db.execute(text("SELECT COUNT(*) FROM sensores WHERE id_empresa = :empresa_id AND activo = true"), 
                        {"empresa_id": id_empresa})
    sensores_activos = result.scalar()
    
    result = db.execute(text("SELECT COUNT(*) FROM alertas WHERE id_empresa = :empresa_id AND resuelta = false"), 
                        {"empresa_id": id_empresa})
    alertas_pendientes = result.scalar()
    
    return {
        "total_cultivos": total_sensores,
        "cultivos_activos": sensores_activos,
        "alertas_pendientes": alertas_pendientes
    }


@router.get("/sensores")
async def obtener_dashboard_sensores(
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db),
    horas: int = 24
):
    """Obtener dashboard completo de sensores IoT"""
    return {"message": "Dashboard de sensores no implementado aún"}


@router.get("/sensores/estadisticas")
async def obtener_estadisticas_sensores(
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener estadísticas generales de sensores"""
    return {"message": "Estadísticas de sensores no implementadas aún"}


@router.get("/kpis")
async def get_dashboard_kpis(
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener KPIs principales del dashboard"""
    from api.models.schemas import DashboardKPIs
    from datetime import timedelta
    from database.models.database import LecturaSensor
    
    # Obtener ID de empresa del usuario actual
    id_empresa = current_user.id_empresa
    
    # Contar sensores activos de la empresa
    sensores_activos = db.query(Sensor).filter(
        Sensor.id_empresa == id_empresa,
        Sensor.estado == 'activo'
    ).count()
    
    # Contar sensores totales como "cultivos monitoreados"
    cultivos_monitoreados = db.query(Sensor).filter(
        Sensor.id_empresa == id_empresa
    ).count()
    
    # Contar alertas pendientes (mediante join con Sensor para filtrar por empresa)
    alertas_pendientes = db.query(Alerta).join(Sensor).filter(
        Sensor.id_empresa == id_empresa,
        Alerta.estado == 'pendiente'
    ).count()
    
    # Calcular promedios de temperatura y humedad (últimas 24 horas)
    fecha_limite = datetime.utcnow() - timedelta(hours=24)
    
    temp_promedio = db.query(func.avg(LecturaSensor.temperatura)).join(Sensor).filter(
        Sensor.id_empresa == id_empresa,
        LecturaSensor.timestamp >= fecha_limite,
        LecturaSensor.temperatura.isnot(None)
    ).scalar()
    
    humedad_promedio = db.query(func.avg(LecturaSensor.humedad_aire)).join(Sensor).filter(
        Sensor.id_empresa == id_empresa,
        LecturaSensor.timestamp >= fecha_limite,
        LecturaSensor.humedad_aire.isnot(None)
    ).scalar()
    
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
        humedad_promedio=round(float(humedad_promedio), 1) if humedad_promedio else None,
        areas_bajo_monitoreo=areas_monitoreadas,
        produccion_estimada=produccion_estimada
    )


@router.get("/sensor-data/{sensor_id}")
async def get_sensor_data(
    sensor_id: int,
    days: int = 7,
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener datos históricos de un sensor"""
    # Verificar que el sensor pertenece a la empresa
    sensor = db.query(Sensor).filter(
        Sensor.id_sensor == sensor_id,
        Sensor.id_empresa == current_user.id_empresa
    ).first()
    
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor no encontrado"
        )
    
    # Retornar datos mock por ahora
    return {
        "sensor_id": sensor_id,
        "data": [],
        "message": "Datos históricos no implementados aún"
    }


@router.get("/trabajadores")
async def get_trabajadores(
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener lista de trabajadores de la empresa del usuario actual"""
    # Obtener todos los trabajadores de la misma empresa
    trabajadores = db.query(Trabajador).filter(
        Trabajador.id_empresa == current_user.id_empresa
    ).all()
    
    # Formatear datos
    trabajadores_data = []
    for trabajador in trabajadores:
        trabajadores_data.append({
            "id": str(trabajador.id_trabajador),
            "name": f"{trabajador.nombre} {trabajador.apellido}",
            "dni": trabajador.dni,
            "email": trabajador.email,
            "phone": trabajador.telefono or "N/A",
            "role": trabajador.rol,
            "department": "Producción" if trabajador.rol == "worker" else "Administración",
            "assignedSensors": [],  # TODO: Implementar asignaciones reales
            "status": "active" if trabajador.activo else "inactive",
            "lastActive": trabajador.fecha_contratacion.strftime("%Y-%m-%d") if trabajador.fecha_contratacion else "N/A"
        })
    
    return trabajadores_data

@router.get("/produccion")
async def get_produccion_data(
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener datos de producción"""
    sensores = db.query(Sensor).filter(
        Sensor.id_empresa == current_user.id_empresa
    ).all()
    
    return {
        "total_hectareas": len(sensores) * 10,  # Mock: 10 hectáreas por sensor
        "cultivos_por_tipo": {"maiz": 2, "soja": 1, "trigo": 1},  # Mock data
        "produccion_estimada": len(sensores) * 1000,  # Mock: 1000 kg por sensor
        "rendimiento_promedio": 85.5  # Mock percentage
    }