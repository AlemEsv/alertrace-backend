from fastapi_mqtt import FastMQTT, MQTTConfig
from api.config import settings
import json
import logging
from database.models.database import SessionLocal, Sensor, LecturaSensor
from sqlalchemy import select
from api.services.sensors.service import verify_and_generate_alerts
from datetime import datetime
from api.services.websocket.service import ws_manager

logger = logging.getLogger(__name__)

# Configuración del cliente MQTT
mqtt_config = MQTTConfig(
    host=settings.mqtt_broker,
    port=settings.mqtt_port,
    username=settings.mqtt_username,
    password=settings.mqtt_password,
    keepalive=60
)

mqtt = FastMQTT(config=mqtt_config)

@mqtt.on_connect()
def connect(client, flags, rc, properties):
    logger.info(f"Connected to MQTT Broker: {settings.mqtt_broker}:{settings.mqtt_port}")
    # Suscribirse a todos los tópicos de datos de sensores
    # Estructura del tópico: sensores/{device_id}/data
    mqtt.client.subscribe("sensores/+/data")

@mqtt.on_message()
async def message(client, topic, payload, qos, properties):
    try:
        payload_str = payload.decode()
        logger.info(f"Received message on {topic}: {payload_str}")
        data = json.loads(payload_str)
        
        # Extract device_id from topic or payload
        # Topic: sensores/{device_id}/data
        topic_parts = topic.split('/')
        if len(topic_parts) >= 3 and topic_parts[0] == 'sensores' and topic_parts[2] == 'data':
            device_id = topic_parts[1]
        else:
            # Fallback to payload if available
            device_id = data.get('device_id')
            
        if not device_id:
            logger.warning(f"Could not determine device_id from topic {topic} or payload")
            return

        with SessionLocal() as db:
            try:
                result = db.execute(select(Sensor).where(Sensor.device_id == device_id))
                sensor = result.scalars().first()
                if not sensor:
                    logger.warning(f"Sensor with device_id {device_id} not found")
                    return

                # Create reading
                # Assuming payload matches SensorData structure roughly
                # timestamp might need parsing
                ts_str = data.get('timestamp')
                if ts_str:
                    try:
                        timestamp = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    except ValueError:
                        timestamp = datetime.utcnow()
                else:
                    timestamp = datetime.utcnow()

                nueva_lectura = LecturaSensor(
                    id_sensor=sensor.id_sensor,
                    temperatura=data.get('temperatura'),
                    humedad_aire=data.get('humedad_aire'),
                    ph_suelo=data.get('ph_suelo'),
                    humedad_suelo=data.get('humedad_suelo'),
                    radiacion_solar=data.get('radiacion_solar'),
                    timestamp=timestamp
                )
                
                db.add(nueva_lectura)
                sensor.ultima_lectura = nueva_lectura.timestamp
                sensor.estado = 'activo'
                db.commit()
                db.refresh(nueva_lectura)
                
                # Alerts
                verify_and_generate_alerts(nueva_lectura, sensor, db)
                
                logger.info(f"Processed data for sensor {device_id}")

                # Broadcast to WebSockets
                await ws_manager.broadcast({
                    "type": "sensor_update",
                    "device_id": device_id,
                    "data": {
                        "temperatura": nueva_lectura.temperatura,
                        "humedad_aire": nueva_lectura.humedad_aire,
                        "ph_suelo": nueva_lectura.ph_suelo,
                        "humedad_suelo": nueva_lectura.humedad_suelo,
                        "radiacion_solar": nueva_lectura.radiacion_solar,
                        "timestamp": nueva_lectura.timestamp.isoformat()
                    }
                })
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error saving data for {device_id}: {str(e)}")
            
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from topic {topic}")
    except Exception as e:
        logger.error(f"Error processing MQTT message: {str(e)}")
