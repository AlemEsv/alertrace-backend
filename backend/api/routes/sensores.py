from datetime import datetime, timedelta, timezone
from typing import List, Optional, Annotated, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc, func

from database.connection import get_db, get_sync_db
from database.models.database import (
    Sensor, LecturaSensor, Alerta, ConfiguracionUmbral, 
    Empresa, Trabajador, AsignacionSensor
)
from api.models import (
    SensorData, SensorResponse, LecturaSensorResponse,
    SensorUpdate, SensorMoveRequest, SensorMoveResponse, DeleteAreaResponse,
    SensorCreate
)
from api.auth.dependencies import get_current_user
from api.services.sensors.service import verify_and_generate_alerts
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sensores"])

# Type aliases for dependencies
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[Union[Trabajador, Empresa], Depends(get_current_user)]

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_sensor(
    sensor_data: SensorCreate,
    db: DbSession,
    current_user: CurrentUser
):
    """
    Crear un nuevo sensor en la empresa.
    Solo accesible para admin_empresa.
    """
    # Verificar que el usuario actual es admin de empresa
    if not hasattr(current_user, 'rol') or current_user.rol != "admin_empresa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores de empresa pueden crear sensores"
        )
    
    # Verificar que el device_id no esté en uso
    result = await db.execute(select(Sensor).where(Sensor.device_id == sensor_data.device_id))
    sensor_existente = result.scalars().first()
    
    if sensor_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un sensor con device_id {sensor_data.device_id}"
        )
    
    try:
        # Crear el sensor
        nuevo_sensor = Sensor(
            id_empresa=current_user.id_empresa,
            nombre_sensor=sensor_data.nombre,
            tipo_sensor=sensor_data.tipo,
            device_id=sensor_data.device_id,
            latitud=sensor_data.coordenadas_lat,
            longitud=sensor_data.coordenadas_lng,
            ubicacion_sensor=sensor_data.ubicacion_sensor,
            estado='activo',
            fecha_instalacion=datetime.utcnow()
        )
        
        db.add(nuevo_sensor)
        await db.commit()
        await db.refresh(nuevo_sensor)
        
        return {
            "message": "Sensor creado exitosamente",
            "sensor": {
                "id_sensor": nuevo_sensor.id_sensor,
                "nombre_sensor": nuevo_sensor.nombre_sensor,
                "tipo_sensor": nuevo_sensor.tipo_sensor,
                "device_id": nuevo_sensor.device_id,
                "estado": nuevo_sensor.estado,
                "latitud": float(nuevo_sensor.latitud) if nuevo_sensor.latitud else None,
                "longitud": float(nuevo_sensor.longitud) if nuevo_sensor.longitud else None
            }
        }
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear sensor: {str(e)}"
        )

@router.get("/", response_model=List[SensorResponse])
async def get_sensors(
    db: DbSession,
    current_user: CurrentUser,
    activo: Optional[bool] = None
):
    """Obtener lista de sensores según el tipo de usuario"""
    if isinstance(current_user, Trabajador):
        if current_user.rol == 'admin_empresa':
            # Admin ve todos los sensores de la empresa
            query = select(Sensor).where(Sensor.id_empresa == current_user.id_empresa)
        else:
            # Para trabajadores: solo sensores asignados
            query = select(Sensor).join(AsignacionSensor).where(
                AsignacionSensor.id_trabajador == current_user.id_trabajador,
                AsignacionSensor.fecha_desasignacion.is_(None)
            )
    elif isinstance(current_user, Empresa):
        # Para empresas: todos los sensores de sus trabajadores
        # Wait, sensors belong to Empresa directly.
        query = select(Sensor).where(
            Sensor.id_empresa == current_user.id_empresa
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tipo de usuario no válido"
        )
    
    if activo is not None:
        query = query.where(Sensor.estado == ('activo' if activo else 'inactivo')) # Assuming 'activo'/'inactivo' strings based on other code
    
    result = await db.execute(query)
    sensores = result.scalars().all()
    return sensores


@router.get("/with-readings")
async def get_sensors_with_readings(
    db: DbSession,
    current_user: CurrentUser,
    activo: Optional[bool] = None
):
    """Obtener lista de sensores con sus lecturas más recientes"""
    # Obtener sensores según tipo de usuario
    if isinstance(current_user, Trabajador):
        query = select(Sensor).join(AsignacionSensor).where(
            AsignacionSensor.id_trabajador == current_user.id_trabajador,
            AsignacionSensor.fecha_desasignacion.is_(None)
        )
    elif isinstance(current_user, Empresa):
        query = select(Sensor).where(
            Sensor.id_empresa == current_user.id_empresa
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tipo de usuario no válido"
        )
    
    if activo is not None:
        query = query.where(Sensor.estado == ('activo' if activo else 'inactivo'))
    
    result_sensores = await db.execute(query)
    sensores = result_sensores.scalars().all()
    
    # Para cada sensor, obtener la lectura más reciente
    result = []
    for sensor in sensores:
        result_lectura = await db.execute(select(LecturaSensor).where(
            LecturaSensor.id_sensor == sensor.id_sensor
        ).order_by(LecturaSensor.timestamp.desc()).limit(1))
        lectura_reciente = result_lectura.scalars().first()
        
        sensor_data = {
            "id_sensor": sensor.id_sensor,
            "device_id": sensor.device_id,
            "nombre": sensor.nombre_sensor,
            "tipo": sensor.tipo_sensor,
            "id_empresa": sensor.id_empresa,
            "activo": sensor.estado == 'activo',
            "estado": sensor.estado,
            "latitud": float(sensor.latitud) if sensor.latitud else None,
            "longitud": float(sensor.longitud) if sensor.longitud else None,
            "fecha_instalacion": sensor.fecha_instalacion.isoformat() if sensor.fecha_instalacion else None
        }
        
        # Agregar datos de la lectura más reciente si existe
        if lectura_reciente:
            sensor_data.update({
                "temperatura": round(float(lectura_reciente.temperatura), 1) if lectura_reciente.temperatura is not None else 0.0,
                "humedad_aire": round(float(lectura_reciente.humedad_aire), 1) if lectura_reciente.humedad_aire is not None else 0.0,
                "humedad_suelo": round(float(lectura_reciente.humedad_suelo), 1) if lectura_reciente.humedad_suelo is not None else 0.0,
                "ph": round(float(lectura_reciente.ph_suelo), 1) if lectura_reciente.ph_suelo is not None else 7.0,
                "radiacion_solar": round(float(lectura_reciente.radiacion_solar), 1) if lectura_reciente.radiacion_solar is not None else 0.0,
                "timestamp_lectura": lectura_reciente.timestamp.isoformat()
            })
        else:
            sensor_data.update({
                "temperatura": 25.0,
                "humedad_aire": 60.0,
                "humedad_suelo": 70.0,
                "ph": 6.5,
                "radiacion_solar": 0.0,
                "timestamp_lectura": None
            })
        
        result.append(sensor_data)
    
    return result

@router.patch("/{sensor_id}", response_model=SensorResponse)
async def update_sensor(
    sensor_id: int,
    sensor_data: SensorUpdate,
    db: DbSession,
    current_user: CurrentUser
):
    """Actualizar propiedades de un sensor"""
    # Verificar que el sensor existe
    result = await db.execute(select(Sensor).where(Sensor.id_sensor == sensor_id))
    sensor = result.scalars().first()
    
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor {sensor_id} no encontrado"
        )
    
    # Verificar permisos de la empresa
    if hasattr(current_user, 'id_empresa'):
        user_empresa_id = current_user.id_empresa
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario sin empresa asignada"
        )
    
    if sensor.id_empresa != user_empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para modificar este sensor"
        )
    
    # Actualizar solo los campos proporcionados
    update_data = sensor_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(sensor, field, value)
    
    try:
        await db.commit()
        await db.refresh(sensor)
        
        # Log para auditoría
        user_id = getattr(current_user, 'id_trabajador', getattr(current_user, 'id_empresa', 'unknown'))
        logger.info(
            f"Sensor {sensor_id} actualizado por usuario {user_id}. "
            f"Campos: {list(update_data.keys())}"
        )
        
        return sensor
    
    except Exception as e:
        await db.rollback()
        logger.error(f"Error actualizando sensor {sensor_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar sensor: {str(e)}"
        )


@router.post("/move", response_model=SensorMoveResponse)
async def move_sensors(
    move_data: SensorMoveRequest,
    db: DbSession,
    current_user: CurrentUser
):
    """
    Mover sensores entre áreas (renombrar ubicación).
    """
    updated_count = 0
    errors = []
    updated_sensors = []
    
    try:
        # Obtener id_empresa del usuario
        if hasattr(current_user, 'id_empresa'):
            user_empresa_id = current_user.id_empresa
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario sin empresa asignada"
            )
        
        # Construir query base
        query = select(Sensor).where(
            Sensor.id_empresa == user_empresa_id,
            Sensor.ubicacion_sensor == move_data.from_ubicacion
        )
        
        # Filtrar por IDs específicos si se proporcionan
        if move_data.sensor_ids:
            query = query.where(Sensor.id_sensor.in_(move_data.sensor_ids))
        
        result = await db.execute(query)
        sensores = result.scalars().all()
        
        if not sensores:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontraron sensores en '{move_data.from_ubicacion}'"
            )
        
        # Actualizar cada sensor
        for sensor in sensores:
            try:
                sensor.ubicacion_sensor = move_data.to_ubicacion
                updated_sensors.append(sensor)
                updated_count += 1
            except Exception as e:
                errors.append({
                    "sensor_id": sensor.id_sensor,
                    "error": str(e)
                })
        
        await db.commit()
        
        return SensorMoveResponse(
            updated=updated_count,
            errors=errors,
            sensors=[SensorResponse.model_validate(s) for s in updated_sensors]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error moviendo sensores: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al mover sensores: {str(e)}"
        )


@router.delete("/by-ubicacion/{ubicacion}", response_model=DeleteAreaResponse)
async def delete_area(
    ubicacion: str,
    db: DbSession,
    current_user: CurrentUser,
    move_to: Optional[str] = None
):
    """
    Eliminar un área y mover sus sensores a otra ubicación o dejarlos sin área.
    """
    try:
        # Obtener id_empresa del usuario
        if hasattr(current_user, 'id_empresa'):
            user_empresa_id = current_user.id_empresa
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario sin empresa asignada"
            )
        
        # Validar move_to si se proporciona
        if move_to:
            move_to = move_to.strip()
            if len(move_to) > 128:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="move_to no puede exceder 128 caracteres"
                )
        
        # Buscar todos los sensores del área
        result = await db.execute(select(Sensor).where(
            Sensor.id_empresa == user_empresa_id,
            Sensor.ubicacion_sensor == ubicacion
        ))
        sensores = result.scalars().all()
        
        if not sensores:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontraron sensores en el área '{ubicacion}'"
            )
        
        sensors_moved = len(sensores)
        
        # Actualizar ubicación de todos los sensores
        for sensor in sensores:
            sensor.ubicacion_sensor = move_to
        
        await db.commit()
        
        return DeleteAreaResponse(
            deleted_ubicacion=ubicacion,
            sensors_moved=sensors_moved,
            new_ubicacion=move_to
        )
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error eliminando área '{ubicacion}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar área: {str(e)}"
        )


@router.post("/data", status_code=status.HTTP_201_CREATED)
def receive_sensor_data(
    data: SensorData,
    db: Session = Depends(get_sync_db)
):
    """
    Recibir datos de sensores IoT.
    Este endpoint es público pero requiere validación del device_id.
    """
    # Verificar si el sensor existe
    result = db.execute(select(Sensor).where(Sensor.device_id == data.device_id))
    sensor = result.scalars().first()
    
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor con device_id {data.device_id} no encontrado"
        )
    
    try:
        # Crear nueva lectura
        nueva_lectura = LecturaSensor(
            id_sensor=sensor.id_sensor,
            temperatura=data.temperatura,
            humedad_aire=data.humedad_aire,
            humedad_suelo=data.humedad_suelo,
            ph_suelo=data.ph_suelo,
            radiacion_solar=data.radiacion_solar,
            timestamp=datetime.now(timezone.utc)
        )
        
        db.add(nueva_lectura)
        
        # Verificar alertas
        verify_and_generate_alerts(nueva_lectura, sensor, db)
        
        db.commit()
        
        return {"message": "Datos recibidos correctamente"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error procesando datos del sensor {data.device_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar datos: {str(e)}"
        )




