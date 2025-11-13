import schedule
import time
import logging
from datetime import datetime
from typing import Optional
import os
import sys

# Agregar el directorio padre al path para poder importar los módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models.database import SessionLocal
from api.services.tuya_integration_service import TuyaIntegrationService

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class TuyaSyncScheduler:
    """
    Programador de tareas para sincronización automática desde Tuya Cloud
    """
    
    def __init__(self, sync_interval_minutes: int = 15):
        """
        Inicializar el programador
        
        Args:
            sync_interval_minutes: Intervalo de sincronización en minutos (default: 15)
        """
        self.sync_interval = sync_interval_minutes
        self.tuya_service = None
        self.is_running = False
        
    def initialize_tuya_service(self):
        """Inicializar el servicio de Tuya"""
        try:
            self.tuya_service = TuyaIntegrationService()
            logger.info("Servicio de Tuya inicializado correctamente")
            return True
        except Exception as e:
            logger.error(f"Error al inicializar servicio de Tuya: {str(e)}")
            return False
    
    def sync_all_sensors_job(self):
        """
        Job que sincroniza todos los sensores activos
        """
        logger.info(f"Iniciando sincronización automática - {datetime.now().isoformat()}")
        
        db = SessionLocal()
        try:
            if not self.tuya_service:
                if not self.initialize_tuya_service():
                    logger.error("No se pudo inicializar el servicio de Tuya. Saltando sincronización.")
                    return
            
            # Sincronizar todos los sensores activos
            stats = self.tuya_service.sync_all_sensors(
                db=db,
                empresa_id=None,  # Todas las empresas
                only_active=True
            )
            
            logger.info(
                f"Sincronización completada - "
                f"Total: {stats['total']}, "
                f"Exitosos: {stats['success']}, "
                f"Fallidos: {stats['failed']}"
            )
            
            if stats['failed'] > 0:
                logger.warning(f"Errores en sincronización: {stats['errors']}")
            
        except Exception as e:
            logger.error(f"Error durante sincronización automática: {str(e)}", exc_info=True)
        finally:
            db.close()
    
    def start(self):
        """
        Iniciar el programador de tareas
        """
        logger.info(f"Iniciando programador de sincronización cada {self.sync_interval} minutos")
        
        # Inicializar servicio de Tuya
        if not self.initialize_tuya_service():
            logger.error("No se pudo inicializar. Deteniendo programador.")
            return
        
        # Programar la tarea
        schedule.every(self.sync_interval).minutes.do(self.sync_all_sensors_job)
        
        # Ejecutar una sincronización inicial
        logger.info("Ejecutando sincronización inicial...")
        self.sync_all_sensors_job()
        
        # Loop principal
        self.is_running = True
        logger.info("Programador iniciado. Presione Ctrl+C para detener.")
        
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Deteniendo programador...")
            self.is_running = False
    
    def stop(self):
        """Detener el programador"""
        self.is_running = False
        logger.info("Programador detenido")


def main():
    """
    Función principal para ejecutar el worker
    """
    # Leer intervalo desde variable de entorno o usar default
    sync_interval = int(os.getenv("TUYA_SYNC_INTERVAL_MINUTES", "15"))
    
    logger.info(f"=== Tuya Cloud Sync Worker ===")
    logger.info(f"Intervalo de sincronización: {sync_interval} minutos")
    
    # Crear y ejecutar el programador
    scheduler = TuyaSyncScheduler(sync_interval_minutes=sync_interval)
    scheduler.start()


if __name__ == "__main__":
    main()
