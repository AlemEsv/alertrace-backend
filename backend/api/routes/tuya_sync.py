from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.connection import get_db
from database.models.database import Sensor, Empresa, Trabajador
from api.auth.dependencies import get_current_user
from api.services.tuya_integration_service import TuyaIntegrationService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tuya-sync"])


class SyncResponse(BaseModel):
    """Respuesta de sincronización"""
    success: bool
    message: str
    total: int
    synced: int
    failed: int
    errors: list = []


class SyncSensorRequest(BaseModel):
    """Request para sincronizar sensor específico"""
    sensor_id: int
    create_alerts: bool = True


@router.post("/sync/sensor/{sensor_id}", response_model=SyncResponse)
async def sync_single_sensor(
    sensor_id: int,
    create_alerts: bool = True,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Sincronizar datos de un sensor específico desde Tuya Cloud a Supabase
    
    - **sensor_id**: ID del sensor a sincronizar
    - **create_alerts**: Si se deben crear alertas automáticamente (default: true)
    """
    try:
        # Verificar que el sensor existe
        sensor = db.query(Sensor).filter(Sensor.id_sensor == sensor_id).first()
        
        if not sensor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sensor con ID {sensor_id} no encontrado"
            )
        
        # Verificar permisos: el usuario debe pertenecer a la empresa del sensor
        # o ser admin/empresa
        trabajador = db.query(Trabajador).filter(
            Trabajador.user_id == current_user.get("sub")
        ).first()
        
        if trabajador and trabajador.id_empresa != sensor.id_empresa:
            if trabajador.rol not in ["admin", "empresa"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para sincronizar este sensor"
                )
        
        # Inicializar servicio de Tuya
        tuya_service = TuyaIntegrationService()
        
        # Sincronizar sensor
        lectura = tuya_service.sync_sensor_data(db, sensor, create_alert=create_alerts)
        
        if lectura:
            return SyncResponse(
                success=True,
                message=f"Sensor {sensor.nombre_sensor} sincronizado exitosamente",
                total=1,
                synced=1,
                failed=0
            )
        else:
            return SyncResponse(
                success=False,
                message=f"Error al sincronizar sensor {sensor.nombre_sensor}",
                total=1,
                synced=0,
                failed=1,
                errors=[{
                    "sensor_id": sensor.id_sensor,
                    "sensor_name": sensor.nombre_sensor,
                    "error": "No se pudieron obtener datos de Tuya Cloud"
                }]
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al sincronizar sensor {sensor_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar sensor: {str(e)}"
        )


@router.post("/sync/empresa/{empresa_id}", response_model=SyncResponse)
async def sync_empresa_sensors(
    empresa_id: int,
    only_active: bool = True,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Sincronizar todos los sensores de una empresa desde Tuya Cloud
    
    - **empresa_id**: ID de la empresa
    - **only_active**: Solo sincronizar sensores activos (default: true)
    """
    try:
        # Verificar que la empresa existe
        empresa = db.query(Empresa).filter(Empresa.id_empresa == empresa_id).first()
        
        if not empresa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Empresa con ID {empresa_id} no encontrada"
            )
        
        # Verificar permisos
        trabajador = db.query(Trabajador).filter(
            Trabajador.user_id == current_user.get("sub")
        ).first()
        
        if trabajador and trabajador.id_empresa != empresa_id:
            if trabajador.rol not in ["admin", "empresa"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para sincronizar sensores de esta empresa"
                )
        
        # Inicializar servicio de Tuya
        tuya_service = TuyaIntegrationService()
        
        # Sincronizar todos los sensores
        stats = tuya_service.sync_all_sensors(db, empresa_id=empresa_id, only_active=only_active)
        
        return SyncResponse(
            success=stats['failed'] == 0,
            message=f"Sincronización completada: {stats['success']}/{stats['total']} sensores",
            total=stats['total'],
            synced=stats['success'],
            failed=stats['failed'],
            errors=stats['errors']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al sincronizar sensores de empresa {empresa_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar sensores: {str(e)}"
        )


@router.post("/sync/all", response_model=SyncResponse)
async def sync_all_sensors(
    only_active: bool = True,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Sincronizar TODOS los sensores del sistema desde Tuya Cloud
    
    **Requiere permisos de administrador**
    
    - **only_active**: Solo sincronizar sensores activos (default: true)
    """
    try:
        # Verificar que el usuario es admin
        trabajador = db.query(Trabajador).filter(
            Trabajador.user_id == current_user.get("sub")
        ).first()
        
        if not trabajador or trabajador.rol not in ["admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Se requieren permisos de administrador para esta acción"
            )
        
        # Inicializar servicio de Tuya
        tuya_service = TuyaIntegrationService()
        
        # Sincronizar todos los sensores
        stats = tuya_service.sync_all_sensors(db, only_active=only_active)
        
        return SyncResponse(
            success=stats['failed'] == 0,
            message=f"Sincronización global completada: {stats['success']}/{stats['total']} sensores",
            total=stats['total'],
            synced=stats['success'],
            failed=stats['failed'],
            errors=stats['errors']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al sincronizar todos los sensores: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar sensores: {str(e)}"
        )


@router.get("/device/{device_id}/info")
async def get_device_info(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Obtener información de un dispositivo directamente desde Tuya Cloud
    
    - **device_id**: Device ID en Tuya Cloud
    """
    try:
        # Verificar que el sensor existe y el usuario tiene acceso
        sensor = db.query(Sensor).filter(Sensor.device_id == device_id).first()
        
        if not sensor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sensor con device_id {device_id} no encontrado"
            )
        
        # Verificar permisos
        trabajador = db.query(Trabajador).filter(
            Trabajador.user_id == current_user.get("sub")
        ).first()
        
        if trabajador and trabajador.id_empresa != sensor.id_empresa:
            if trabajador.rol not in ["admin", "empresa"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para acceder a este dispositivo"
                )
        
        # Obtener información del dispositivo
        tuya_service = TuyaIntegrationService()
        device_info = tuya_service.get_device_info(device_id)
        
        if not device_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se pudo obtener información del dispositivo desde Tuya Cloud"
            )
        
        return {
            "success": True,
            "device_id": device_id,
            "sensor_name": sensor.nombre_sensor,
            "tuya_info": device_info
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener info de dispositivo {device_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener información: {str(e)}"
        )


@router.get("/device/{device_id}/status")
async def get_device_status(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Obtener estado actual de un dispositivo desde Tuya Cloud (sin guardar en BD)
    
    - **device_id**: Device ID en Tuya Cloud
    """
    try:
        # Verificar que el sensor existe y el usuario tiene acceso
        sensor = db.query(Sensor).filter(Sensor.device_id == device_id).first()
        
        if not sensor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sensor con device_id {device_id} no encontrado"
            )
        
        # Verificar permisos
        trabajador = db.query(Trabajador).filter(
            Trabajador.user_id == current_user.get("sub")
        ).first()
        
        if trabajador and trabajador.id_empresa != sensor.id_empresa:
            if trabajador.rol not in ["admin", "empresa"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para acceder a este dispositivo"
                )
        
        # Obtener estado del dispositivo
        tuya_service = TuyaIntegrationService()
        status_data = tuya_service.get_device_status(device_id)
        
        if not status_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se pudo obtener el estado del dispositivo desde Tuya Cloud"
            )
        
        # Parsear datos
        parsed_data = tuya_service.parse_sensor_data(status_data, sensor.tipo_sensor)
        
        return {
            "success": True,
            "device_id": device_id,
            "sensor_name": sensor.nombre_sensor,
            "raw_status": status_data,
            "parsed_data": {
                "temperatura": float(parsed_data['temperatura']),
                "humedad_aire": float(parsed_data['humedad_aire']),
                "humedad_suelo": float(parsed_data['humedad_suelo']),
                "ph_suelo": float(parsed_data['ph_suelo']),
                "radiacion_solar": float(parsed_data['radiacion_solar'])
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener estado de dispositivo {device_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estado: {str(e)}"
        )
