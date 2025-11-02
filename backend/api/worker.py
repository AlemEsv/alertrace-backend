import asyncio
import threading
import logging
from api.services.sensor_service import SensorService
from database.connection import SessionLocal

logger = logging.getLogger(__name__)

async def polling_worker():
    sensor_service = SensorService()
    logger.info("Sensor polling worker started")
    
    while True:
        try:
            db = SessionLocal()
            await sensor_service.poll_all_sensors(db)
            db.close()
        except Exception as e:
            logger.error(f"Error in polling cycle: {str(e)}")
        
        await asyncio.sleep(10)  # Consulta cada 10 segundos

def start_polling_worker():
    asyncio.run(polling_worker())

def init_worker():
    worker_thread = threading.Thread(target=start_polling_worker, daemon=True)
    worker_thread.start()
    return worker_thread

if __name__ == "__main__":
    logger.info("Starting sensor polling worker manually")
    start_polling_worker()