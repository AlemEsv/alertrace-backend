#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv

# Agregar el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models.database import SessionLocal, Sensor
from api.services.tuya_integration_service import TuyaIntegrationService
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)


def sync_sensor_example(sensor_id: int):
    """
    Ejemplo de sincronización de un sensor
    """
    db = SessionLocal()
    
    try:
        # Buscar el sensor
        sensor = db.query(Sensor).filter(Sensor.id_sensor == sensor_id).first()
        
        if not sensor:
            logger.error(f"Sensor con ID {sensor_id} no encontrado")
            return
        
        logger.info(f"Sincronizando sensor: {sensor.nombre_sensor} (Device ID: {sensor.device_id})")
        
        # Inicializar servicio de Tuya
        tuya_service = TuyaIntegrationService()
        
        # Sincronizar datos
        lectura = tuya_service.sync_sensor_data(db, sensor, create_alert=True)
        
        if lectura:
            logger.info(f"Temperatura: {lectura.temperatura}°C")
            logger.info(f"Humedad: {lectura.humedad_aire}%")
            logger.info(f"pH: {lectura.ph if lectura.ph else 'N/A'}")
            logger.info(f"Timestamp: {lectura.timestamp}")
        else:
            logger.error("Error al sincronizar sensor")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
    finally:
        db.close()


def sync_all_example():
    db = SessionLocal()
    
    try:
        logger.info("Sincronizando todos los sensores activos...")
        
        # Inicializar servicio de Tuya
        tuya_service = TuyaIntegrationService()
        
        # Sincronizar todos
        stats = tuya_service.sync_all_sensors(db, only_active=True)
        
        logger.info("Sincronización completada!")
        logger.info(f"Total de sensores: {stats['total']}")
        logger.info(f"Exitosos: {stats['success']}")
        logger.info(f"Fallidos: {stats['failed']}")
        
        if stats['failed'] > 0:
            logger.warning(f"   Errores: {stats['errors']}")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
    finally:
        db.close()


def list_sensors():
    """
    Listar todos los sensores registrados
    """
    db = SessionLocal()
    
    try:
        sensores = db.query(Sensor).all()
        
        if not sensores:
            logger.info("No hay sensores registrados")
            return
        
        logger.info(f"\nSensores registrados ({len(sensores)}):")
        logger.info("=" * 80)
        
        for sensor in sensores:
            logger.info(f"ID: {sensor.id_sensor}")
            logger.info(f"Nombre: {sensor.nombre_sensor}")
            logger.info(f"Device ID: {sensor.device_id}")
            logger.info(f"Tipo: {sensor.tipo_sensor}")
            logger.info(f"Estado: {sensor.estado}")
            logger.info(f"Ubicación: {sensor.ubicacion_sensor or 'N/A'}")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
    finally:
        db.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Sincronizar sensores de Tuya Cloud')
    parser.add_argument(
        'action',
        choices=['sync', 'sync-all', 'list'],
        help='Acción a realizar'
    )
    parser.add_argument(
        '--sensor-id',
        type=int,
        help='ID del sensor a sincronizar (requerido para action=sync)'
    )
    
    args = parser.parse_args()
    
    if args.action == 'sync':
        if not args.sensor_id:
            logger.error("Se requiere --sensor-id para la acción 'sync'")
            sys.exit(1)
        sync_sensor_example(args.sensor_id)
        
    elif args.action == 'sync-all':
        sync_all_example()
        
    elif args.action == 'list':
        list_sensors()


if __name__ == "__main__":
    main()
