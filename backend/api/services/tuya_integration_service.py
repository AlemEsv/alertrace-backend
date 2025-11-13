from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from tuya_connector import TuyaOpenAPI, TUYA_LOGGER
import os
import logging
from decimal import Decimal

from database.models.database import Sensor, LecturaSensor, Alerta
from api.models.schemas import LecturaSensorResponse

logger = logging.getLogger(__name__)
TUYA_LOGGER.setLevel(logging.WARNING)  # Reducir logs de Tuya


class TuyaIntegrationService:
    """
    Servicio para integrar sensores de Tuya Cloud con Supabase
    """
    
    def __init__(self):
        """Inicializar conexión con Tuya Cloud API"""
        self.api_endpoint = os.getenv("TUYA_API_ENDPOINT", "https://openapi.tuyaus.com")
        self.access_id = os.getenv("TUYA_ACCESS_ID")
        self.access_key = os.getenv("TUYA_ACCESS_KEY")
        
        if not self.access_id or not self.access_key:
            logger.error("Credenciales de Tuya no configuradas en variables de entorno")
            raise ValueError("TUYA_ACCESS_ID y TUYA_ACCESS_KEY son requeridos")
        
        self.openapi = TuyaOpenAPI(self.api_endpoint, self.access_id, self.access_key)
        self.openapi.connect()
        logger.info(f"Conectado a Tuya Cloud API: {self.api_endpoint}")
    
    def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtener el estado actual de un dispositivo desde Tuya Cloud
        
        Args:
            device_id: ID del dispositivo en Tuya
            
        Returns:
            Diccionario con el estado del dispositivo o None si hay error
        """
        try:
            response = self.openapi.get(f"/v1.0/devices/{device_id}/status")
            
            if response.get("success"):
                # Convertir lista de estados a diccionario
                status_data = {item["code"]: item["value"] for item in response.get("result", [])}
                logger.debug(f"Estado obtenido de dispositivo {device_id}: {status_data}")
                return status_data
            else:
                logger.error(f"Error al obtener estado del dispositivo {device_id}: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Excepción al consultar dispositivo {device_id}: {str(e)}")
            return None
    
    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtener información detallada de un dispositivo
        
        Args:
            device_id: ID del dispositivo en Tuya
            
        Returns:
            Diccionario con información del dispositivo
        """
        try:
            response = self.openapi.get(f"/v1.0/devices/{device_id}")
            
            if response.get("success"):
                return response.get("result", {})
            else:
                logger.error(f"Error al obtener info del dispositivo {device_id}: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Excepción al consultar info de dispositivo {device_id}: {str(e)}")
            return None
    
    def parse_sensor_data(self, status_data: Dict[str, Any], sensor_type: str) -> Dict[str, Decimal]:
        """
        Parsear datos del sensor según su tipo
        
        Args:
            status_data: Datos crudos del sensor
            sensor_type: Tipo de sensor
            
        Returns:
            Diccionario con valores parseados
        """
        parsed = {
            'temperatura': Decimal('0'),
            'humedad_aire': Decimal('0'),
            'humedad_suelo': Decimal('0'),
            'ph_suelo': Decimal('0'),
            'radiacion_solar': Decimal('0')
        }
        
        try:
            # Mapeo común de códigos Tuya a nuestros campos
            # Ajustar según los códigos específicos de tus sensores
            
            # Temperatura (generalmente en décimas de grado)
            if 'temp_current' in status_data:
                parsed['temperatura'] = Decimal(str(status_data['temp_current'] / 10))
            elif 'va_temperature' in status_data:
                parsed['temperatura'] = Decimal(str(status_data['va_temperature'] / 10))
            elif 'temperature' in status_data:
                parsed['temperatura'] = Decimal(str(status_data['temperature']))
            
            # Humedad del aire
            if 'humidity_value' in status_data:
                parsed['humedad_aire'] = Decimal(str(status_data['humidity_value']))
            elif 'va_humidity' in status_data:
                parsed['humedad_aire'] = Decimal(str(status_data['va_humidity']))
            elif 'humidity' in status_data:
                parsed['humedad_aire'] = Decimal(str(status_data['humidity']))
            
            # Humedad del suelo
            if 'soil_humidity' in status_data:
                parsed['humedad_suelo'] = Decimal(str(status_data['soil_humidity']))
            elif 'moisture' in status_data:
                parsed['humedad_suelo'] = Decimal(str(status_data['moisture']))
            
            # pH del suelo
            if 'ph_value' in status_data:
                parsed['ph_suelo'] = Decimal(str(status_data['ph_value']))
            
            # Radiación solar / luz
            if 'bright_value' in status_data:
                parsed['radiacion_solar'] = Decimal(str(status_data['bright_value']))
            elif 'light' in status_data:
                parsed['radiacion_solar'] = Decimal(str(status_data['light']))
            
            logger.debug(f"Datos parseados: {parsed}")
            
        except Exception as e:
            logger.error(f"Error al parsear datos del sensor: {str(e)}")
        
        return parsed
    
    def sync_sensor_data(
        self, 
        db: Session, 
        sensor: Sensor,
        create_alert: bool = True
    ) -> Optional[LecturaSensor]:
        """
        Sincronizar datos de un sensor desde Tuya Cloud a Supabase
        
        Args:
            db: Sesión de base de datos
            sensor: Objeto Sensor de la base de datos
            create_alert: Si se deben crear alertas automáticamente
            
        Returns:
            LecturaSensor creada o None si hay error
        """
        try:
            # Obtener estado del dispositivo desde Tuya
            status_data = self.get_device_status(sensor.device_id)
            
            if not status_data:
                logger.warning(f"No se pudieron obtener datos del sensor {sensor.device_id}")
                return None
            
            # Parsear datos según tipo de sensor
            parsed_data = self.parse_sensor_data(status_data, sensor.tipo_sensor)
            
            # Crear nueva lectura en Supabase
            # Nota: El modelo usa 'humedad_aire' que mapea a columna 'humedad'
            # y 'ph' en lugar de 'ph_suelo'
            lectura = LecturaSensor(
                id_sensor=sensor.id_sensor,
                temperatura=parsed_data['temperatura'],
                humedad_aire=parsed_data['humedad_aire'],  # Se mapea a columna 'humedad'
                ph=parsed_data['ph_suelo'],  # Columna 'ph' en la BD
                timestamp=datetime.utcnow()
            )
            
            db.add(lectura)
            
            # Actualizar última lectura del sensor
            sensor.ultima_lectura = lectura.timestamp
            
            # Commit a la base de datos (Supabase vía PostgreSQL)
            db.commit()
            db.refresh(lectura)
            
            logger.info(f"Lectura sincronizada exitosamente para sensor {sensor.nombre_sensor} (ID: {sensor.id_sensor})")
            
            # Verificar umbrales y crear alertas si es necesario
            if create_alert:
                self._check_thresholds_and_create_alerts(db, sensor, lectura)
            
            return lectura
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error al sincronizar sensor {sensor.device_id}: {str(e)}", exc_info=True)
            return None
    
    def sync_all_sensors(
        self, 
        db: Session,
        empresa_id: Optional[int] = None,
        only_active: bool = True
    ) -> Dict[str, Any]:
        """
        Sincronizar todos los sensores de una empresa o todos los sensores
        
        Args:
            db: Sesión de base de datos
            empresa_id: ID de empresa (None para todas)
            only_active: Solo sincronizar sensores activos
            
        Returns:
            Diccionario con estadísticas de sincronización
        """
        query = db.query(Sensor)
        
        if empresa_id:
            query = query.filter(Sensor.id_empresa == empresa_id)
        
        if only_active:
            query = query.filter(Sensor.estado == 'activo')
        
        sensores = query.all()
        
        stats = {
            'total': len(sensores),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for sensor in sensores:
            lectura = self.sync_sensor_data(db, sensor)
            
            if lectura:
                stats['success'] += 1
            else:
                stats['failed'] += 1
                stats['errors'].append({
                    'sensor_id': sensor.id_sensor,
                    'sensor_name': sensor.nombre_sensor,
                    'device_id': sensor.device_id
                })
        
        logger.info(f"Sincronización completada: {stats['success']}/{stats['total']} exitosos")
        
        return stats
    
    def _check_thresholds_and_create_alerts(
        self, 
        db: Session, 
        sensor: Sensor, 
        lectura: LecturaSensor
    ):
        """
        Verificar umbrales y crear alertas si es necesario
        
        Args:
            db: Sesión de base de datos
            sensor: Sensor
            lectura: Lectura del sensor
        """
        try:
            from database.models.database import ConfiguracionUmbral
            
            # Obtener configuración de umbrales para este sensor
            umbrales = db.query(ConfiguracionUmbral).filter(
                ConfiguracionUmbral.id_sensor == sensor.id_sensor
            ).first()
            
            if not umbrales:
                return
            
            alerts = []
            
            # Verificar temperatura
            if umbrales.temp_min is not None and lectura.temperatura < umbrales.temp_min:
                alerts.append(('temperatura_baja', f'Temperatura bajo el mínimo: {lectura.temperatura}°C'))
            elif umbrales.temp_max is not None and lectura.temperatura > umbrales.temp_max:
                alerts.append(('temperatura_alta', f'Temperatura sobre el máximo: {lectura.temperatura}°C'))
            
            # Verificar humedad
            if umbrales.humedad_min is not None and lectura.humedad_aire < umbrales.humedad_min:
                alerts.append(('humedad_baja', f'Humedad bajo el mínimo: {lectura.humedad_aire}%'))
            elif umbrales.humedad_max is not None and lectura.humedad_aire > umbrales.humedad_max:
                alerts.append(('humedad_alta', f'Humedad sobre el máximo: {lectura.humedad_aire}%'))
            
            # Crear alertas
            for tipo_alerta, mensaje in alerts:
                alerta = Alerta(
                    id_sensor=sensor.id_sensor,
                    tipo_alerta=tipo_alerta,
                    mensaje=mensaje,
                    severidad='media',
                    estado='pendiente',
                    valor_actual=lectura.temperatura if 'temperatura' in tipo_alerta else lectura.humedad_aire
                )
                db.add(alerta)
                logger.info(f"Alerta creada: {mensaje}")
            
            if alerts:
                db.commit()
                
        except Exception as e:
            logger.error(f"Error al verificar umbrales: {str(e)}")
    
    def get_historical_data(
        self,
        device_id: str,
        codes: List[str],
        start_time: int,
        end_time: int
    ) -> Optional[List[Dict]]:
        """
        Obtener datos históricos de un dispositivo (si está disponible en tu plan de Tuya)
        
        Args:
            device_id: ID del dispositivo
            codes: Lista de códigos de datos a obtener
            start_time: Timestamp de inicio (epoch en segundos)
            end_time: Timestamp de fin (epoch en segundos)
            
        Returns:
            Lista de datos históricos
        """
        try:
            response = self.openapi.get(
                f"/v1.0/devices/{device_id}/logs",
                {
                    "codes": ",".join(codes),
                    "start_time": start_time,
                    "end_time": end_time,
                    "type": "7"  # Tipo de log (ajustar según documentación de Tuya)
                }
            )
            
            if response.get("success"):
                return response.get("result", {}).get("logs", [])
            else:
                logger.error(f"Error al obtener histórico: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Excepción al obtener histórico: {str(e)}")
            return None
