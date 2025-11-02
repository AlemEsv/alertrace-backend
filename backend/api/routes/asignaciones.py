from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

from database.connection import get_db
from database.models.database import Trabajador, Sensor, AsignacionSensor
from api.auth.dependencies import get_current_user

router = APIRouter(
    tags=["Asignaciones Sensor-Trabajador"]
)


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
async def asignar_sensor(
    asignacion_data: AsignacionCreate,
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    sensor = db.query(Sensor).filter(
        Sensor.id_sensor == asignacion_data.id_sensor,
        Sensor.id_empresa == current_user.id_empresa
    ).first()
    
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor no encontrado o no pertenece a tu empresa"
        )
    
    # Verificar que el trabajador existe y pertenece a la empresa
    trabajador = db.query(Trabajador).filter(
        Trabajador.id_trabajador == asignacion_data.id_trabajador,
        Trabajador.id_empresa == current_user.id_empresa
    ).first()
    
    if not trabajador:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado o no pertenece a tu empresa"
        )
    
    # Verificar que no exista ya una asignación activa
    asignacion_existente = db.query(AsignacionSensor).filter(
        AsignacionSensor.id_sensor == asignacion_data.id_sensor,
        AsignacionSensor.id_trabajador == asignacion_data.id_trabajador,
        AsignacionSensor.fecha_desasignacion.is_(None)
    ).first()
    
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
        db.commit()
        db.refresh(nueva_asignacion)
        
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
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear asignación: {str(e)}"
        )


@router.delete("/{asignacion_id}")
async def desasignar_sensor(
    asignacion_id: int,
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    asignacion = db.query(AsignacionSensor).filter(
        AsignacionSensor.id_asignacion == asignacion_id
    ).first()
    
    if not asignacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asignación no encontrada"
        )
    
    # Verificar que el sensor pertenece a la empresa del usuario
    sensor = db.query(Sensor).filter(
        Sensor.id_sensor == asignacion.id_sensor,
        Sensor.id_empresa == current_user.id_empresa
    ).first()
    
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
        db.commit()
        
        return {
            "message": "Sensor desasignado exitosamente",
            "asignacion_id": asignacion_id
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al desasignar sensor: {str(e)}"
        )


@router.get("/trabajador/{trabajador_id}")
async def listar_asignaciones_trabajador(
    trabajador_id: int,
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db),
    activas_solo: bool = True
):
    """Listar todas las asignaciones de un trabajador específico"""
    # Verificar que el trabajador pertenece a la empresa
    trabajador = db.query(Trabajador).filter(
        Trabajador.id_trabajador == trabajador_id,
        Trabajador.id_empresa == current_user.id_empresa
    ).first()
    
    if not trabajador:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Consultar asignaciones
    query = db.query(AsignacionSensor).filter(
        AsignacionSensor.id_trabajador == trabajador_id
    )
    
    if activas_solo:
        query = query.filter(AsignacionSensor.fecha_desasignacion.is_(None))
    
    asignaciones = query.all()
    
    resultado = []
    for asig in asignaciones:
        sensor = db.query(Sensor).filter(Sensor.id_sensor == asig.id_sensor).first()
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
async def listar_asignaciones_sensor(
    sensor_id: int,
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db),
    activas_solo: bool = True
):
    """Listar todas las asignaciones de un sensor específico"""
    sensor = db.query(Sensor).filter(
        Sensor.id_sensor == sensor_id,
        Sensor.id_empresa == current_user.id_empresa
    ).first()
    
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor no encontrado"
        )
    
    # Consultar asignaciones
    query = db.query(AsignacionSensor).filter(
        AsignacionSensor.id_sensor == sensor_id
    )
    
    if activas_solo:
        query = query.filter(AsignacionSensor.fecha_desasignacion.is_(None))
    
    asignaciones = query.all()
    
    resultado = []
    for asig in asignaciones:
        trabajador = db.query(Trabajador).filter(
            Trabajador.id_trabajador == asig.id_trabajador
        ).first()
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
async def listar_todas_asignaciones(
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db),
    activas_solo: bool = True
):
    """Listar todas las asignaciones de la empresa"""
    # Obtener todos los sensores de la empresa
    sensores_empresa = db.query(Sensor.id_sensor).filter(
        Sensor.id_empresa == current_user.id_empresa
    ).all()
    
    sensor_ids = [s[0] for s in sensores_empresa]
    
    if not sensor_ids:
        return []
    
    # Consultar asignaciones de estos sensores
    query = db.query(AsignacionSensor).filter(
        AsignacionSensor.id_sensor.in_(sensor_ids)
    )
    
    if activas_solo:
        query = query.filter(AsignacionSensor.fecha_desasignacion.is_(None))
    
    asignaciones = query.all()
    
    resultado = []
    for asig in asignaciones:
        sensor = db.query(Sensor).filter(Sensor.id_sensor == asig.id_sensor).first()
        trabajador = db.query(Trabajador).filter(
            Trabajador.id_trabajador == asig.id_trabajador
        ).first()
        
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
