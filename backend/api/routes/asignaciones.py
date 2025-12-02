from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Annotated

from database.connection import get_db
from database.models.database import Trabajador, Sensor, AsignacionSensor
from api.auth.dependencies import get_current_user

router = APIRouter(
    tags=["Asignaciones Sensor-Trabajador"]
)

DbSession = Annotated[AsyncSession, Depends(get_db)]


# Schemas
class AsignacionCreate(BaseModel):
    id_sensor: int
    id_trabajador: int


class AsignacionResponse(BaseModel):
    id_asignacion: int
    id_sensor: int
    id_trabajador: int
    fecha_asignacion: datetime
    sensor_nombre: str
    trabajador_nombre: str


@router.post("/", status_code=status.HTTP_201_CREATED)
async def assign_sensor(
    asignacion_data: AsignacionCreate,
    db: DbSession,
    current_user: Trabajador = Depends(get_current_user)
):
    """
    Asignar un sensor a un trabajador.
    """
    # Verificar que el usuario actual es admin de empresa
    if current_user.rol != "admin_empresa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores de empresa pueden asignar sensores"
        )
    
    # Verificar que el sensor existe y pertenece a la empresa
    result_sensor = await db.execute(select(Sensor).where(
        Sensor.id_sensor == asignacion_data.id_sensor,
        Sensor.id_empresa == current_user.id_empresa
    ))
    sensor = result_sensor.scalars().first()
    
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor no encontrado o no pertenece a tu empresa"
        )
    
    # Verificar que el trabajador existe y pertenece a la empresa
    result_trabajador = await db.execute(select(Trabajador).where(
        Trabajador.id_trabajador == asignacion_data.id_trabajador,
        Trabajador.id_empresa == current_user.id_empresa
    ))
    trabajador = result_trabajador.scalars().first()
    
    if not trabajador:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado o no pertenece a tu empresa"
        )
    
    # Verificar que no exista ya una asignación activa
    result_asignacion = await db.execute(select(AsignacionSensor).where(
        AsignacionSensor.id_sensor == asignacion_data.id_sensor,
        AsignacionSensor.id_trabajador == asignacion_data.id_trabajador,
        AsignacionSensor.fecha_desasignacion.is_(None)
    ))
    asignacion_existente = result_asignacion.scalars().first()
    
    if asignacion_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este sensor ya está asignado a este trabajador"
        )
    
    try:
        # Crear la asignación
        nueva_asignacion = AsignacionSensor(
            id_sensor=asignacion_data.id_sensor,
            id_trabajador=asignacion_data.id_trabajador,
            fecha_asignacion=datetime.utcnow()
        )
        
        db.add(nueva_asignacion)
        await db.commit()
        await db.refresh(nueva_asignacion)
        
        return {
            "message": "Sensor asignado exitosamente",
            "asignacion": {
                "id_asignacion": nueva_asignacion.id_asignacion,
                "id_sensor": nueva_asignacion.id_sensor,
                "id_trabajador": nueva_asignacion.id_trabajador,
                "fecha_asignacion": nueva_asignacion.fecha_asignacion,
                "sensor_nombre": sensor.nombre_sensor,
                "trabajador_nombre": f"{trabajador.nombre} {trabajador.apellido}"
            }
        }
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear asignación: {str(e)}"
        )


@router.delete("/{asignacion_id}")
async def unassign_sensor(
    asignacion_id: int,
    db: DbSession,
    current_user: Trabajador = Depends(get_current_user)
):
    """
    Desasignar un sensor de un trabajador.
    """
    if current_user.rol != "admin_empresa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores de empresa pueden desasignar sensores"
        )
    
    # Buscar la asignación
    result_asignacion = await db.execute(select(AsignacionSensor).where(
        AsignacionSensor.id_asignacion == asignacion_id
    ))
    asignacion = result_asignacion.scalars().first()
    
    if not asignacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asignación no encontrada"
        )
    
    # Verificar que el sensor pertenece a la empresa del usuario
    result_sensor = await db.execute(select(Sensor).where(
        Sensor.id_sensor == asignacion.id_sensor,
        Sensor.id_empresa == current_user.id_empresa
    ))
    sensor = result_sensor.scalars().first()
    
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para desasignar este sensor"
        )
    
    # Verificar que la asignación está activa
    if asignacion.fecha_desasignacion is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta asignación ya fue desactivada"
        )
    
    try:
        # Marcar fecha de desasignación
        asignacion.fecha_desasignacion = datetime.utcnow()
        await db.commit()
        
        return {
            "message": "Sensor desasignado exitosamente",
            "asignacion_id": asignacion_id
        }
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al desasignar sensor: {str(e)}"
        )


@router.get("/trabajador/{trabajador_id}")
async def list_worker_assignments(
    trabajador_id: int,
    db: DbSession,
    current_user: Trabajador = Depends(get_current_user),
    activas_solo: bool = True
):
    """Listar todas las asignaciones de un trabajador específico"""
    # Verificar que el trabajador pertenece a la empresa
    result_trabajador = await db.execute(select(Trabajador).where(
        Trabajador.id_trabajador == trabajador_id,
        Trabajador.id_empresa == current_user.id_empresa
    ))
    trabajador = result_trabajador.scalars().first()
    
    if not trabajador:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Consultar asignaciones
    query = select(AsignacionSensor).where(
        AsignacionSensor.id_trabajador == trabajador_id
    )
    
    if activas_solo:
        query = query.where(AsignacionSensor.fecha_desasignacion.is_(None))
    
    result_asignaciones = await db.execute(query)
    asignaciones = result_asignaciones.scalars().all()
    
    resultado = []
    for asig in asignaciones:
        result_sensor = await db.execute(select(Sensor).where(Sensor.id_sensor == asig.id_sensor))
        sensor = result_sensor.scalars().first()
        resultado.append({
            "id_asignacion": asig.id_asignacion,
            "id_sensor": asig.id_sensor,
            "sensor_nombre": sensor.nombre_sensor if sensor else "N/A",
            "sensor_tipo": sensor.tipo_sensor if sensor else "N/A",
            "fecha_asignacion": asig.fecha_asignacion,
            "fecha_desasignacion": asig.fecha_desasignacion,
            "activa": asig.fecha_desasignacion is None
        })
    
    return resultado


@router.get("/sensor/{sensor_id}")
async def list_sensor_assignments(
    sensor_id: int,
    db: DbSession,
    current_user: Trabajador = Depends(get_current_user),
    activas_solo: bool = True
):
    """Listar todas las asignaciones de un sensor específico"""
    result_sensor = await db.execute(select(Sensor).where(
        Sensor.id_sensor == sensor_id,
        Sensor.id_empresa == current_user.id_empresa
    ))
    sensor = result_sensor.scalars().first()
    
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor no encontrado"
        )
    
    # Consultar asignaciones
    query = select(AsignacionSensor).where(
        AsignacionSensor.id_sensor == sensor_id
    )
    
    if activas_solo:
        query = query.where(AsignacionSensor.fecha_desasignacion.is_(None))
    
    result_asignaciones = await db.execute(query)
    asignaciones = result_asignaciones.scalars().all()
    
    resultado = []
    for asig in asignaciones:
        result_trabajador = await db.execute(select(Trabajador).where(
            Trabajador.id_trabajador == asig.id_trabajador
        ))
        trabajador = result_trabajador.scalars().first()
        resultado.append({
            "id_asignacion": asig.id_asignacion,
            "id_trabajador": asig.id_trabajador,
            "trabajador_nombre": f"{trabajador.nombre} {trabajador.apellido}" if trabajador else "N/A",
            "trabajador_email": trabajador.email if trabajador else "N/A",
            "fecha_asignacion": asig.fecha_asignacion,
            "fecha_desasignacion": asig.fecha_desasignacion,
            "activa": asig.fecha_desasignacion is None
        })
    
    return resultado


@router.get("/")
async def list_all_assignments(
    db: DbSession,
    current_user: Trabajador = Depends(get_current_user),
    activas_solo: bool = True
):
    """Listar todas las asignaciones de la empresa"""
    # Obtener todos los sensores de la empresa
    result_sensores = await db.execute(select(Sensor.id_sensor).where(
        Sensor.id_empresa == current_user.id_empresa
    ))
    sensores_empresa = result_sensores.all()
    
    sensor_ids = [s[0] for s in sensores_empresa]
    
    if not sensor_ids:
        return []
    
    # Consultar asignaciones de estos sensores
    query = select(AsignacionSensor).where(
        AsignacionSensor.id_sensor.in_(sensor_ids)
    )
    
    if activas_solo:
        query = query.where(AsignacionSensor.fecha_desasignacion.is_(None))
    
    result_asignaciones = await db.execute(query)
    asignaciones = result_asignaciones.scalars().all()
    
    resultado = []
    for asig in asignaciones:
        result_sensor = await db.execute(select(Sensor).where(Sensor.id_sensor == asig.id_sensor))
        sensor = result_sensor.scalars().first()
        
        result_trabajador = await db.execute(select(Trabajador).where(
            Trabajador.id_trabajador == asig.id_trabajador
        ))
        trabajador = result_trabajador.scalars().first()
        
        resultado.append({
            "id_asignacion": asig.id_asignacion,
            "id_sensor": asig.id_sensor,
            "sensor_nombre": sensor.nombre_sensor if sensor else "N/A",
            "id_trabajador": asig.id_trabajador,
            "trabajador_nombre": f"{trabajador.nombre} {trabajador.apellido}" if trabajador else "N/A",
            "fecha_asignacion": asig.fecha_asignacion,
            "fecha_desasignacion": asig.fecha_desasignacion,
            "activa": asig.fecha_desasignacion is None
        })
    
    return resultado
