from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
from database.models.database import (
    Sensor, LecturaSensor, Alerta, ConfiguracionUmbral
)
import logging

logger = logging.getLogger(__name__)

def verify_and_generate_alerts(lectura: LecturaSensor, sensor: Sensor, db: Session):
    """Verificar lecturas contra umbrales y generar alertas automáticamente"""
    
    # Obtener configuración de umbrales para la empresa
    result = db.execute(select(ConfiguracionUmbral).where(
        ConfiguracionUmbral.id_empresa == sensor.id_empresa,
        ConfiguracionUmbral.activo == True
    ))
    config = result.scalars().first()
    
    if not config:
        # Crear configuración por defecto si no existe
        config = ConfiguracionUmbral(
            id_empresa=sensor.id_empresa,
            temp_min=15.0, temp_max=35.0,
            humedad_aire_min=40.0, humedad_aire_max=90.0,
            humedad_suelo_min=60.0, humedad_suelo_max=85.0,
            ph_min=6.0, ph_max=7.5,
            radiacion_min=0.0, radiacion_max=1000.0,
            activo=True
        )
        db.add(config)
        db.commit()
    
    alertas_generadas = []
    
    # Helper para verificar y crear alerta
    def check_metric(metric_value, min_val, max_val, metric_name, unit, msg_low, msg_high):
        if metric_value is None: return
        
        if metric_value < min_val:
            alerta = create_alert(
                sensor, metric_name, "high" if metric_name in ["temperatura", "ph"] else "medium",
                f"{msg_low}",
                f"La {metric_name} en {sensor.nombre_sensor} es de {metric_value}{unit}, por debajo del mínimo de {min_val}{unit}.",
                float(metric_value), float(min_val), db
            )
            if alerta: alertas_generadas.append(alerta)
            
        elif metric_value > max_val:
            alerta = create_alert(
                sensor, metric_name, "high" if metric_name in ["temperatura", "ph"] else "medium",
                f"{msg_high}",
                f"La {metric_name} en {sensor.nombre_sensor} es de {metric_value}{unit}, por encima del máximo de {max_val}{unit}.",
                float(metric_value), float(max_val), db
            )
            if alerta: alertas_generadas.append(alerta)

    check_metric(lectura.temperatura, config.temp_min, config.temp_max, "temperatura", "°C", "🌡️ Temperatura Muy Baja", "🌡️ Temperatura Muy Alta")
    check_metric(lectura.humedad_aire, config.humedad_aire_min, config.humedad_aire_max, "humedad_aire", "%", "💧 Humedad del Aire Baja", "💧 Humedad del Aire Alta")
    check_metric(lectura.humedad_suelo, config.humedad_suelo_min, config.humedad_suelo_max, "humedad_suelo", "%", "🌧️ Humedad del Suelo Baja", "🌧️ Humedad del Suelo Alta")
    check_metric(lectura.ph_suelo, config.ph_min, config.ph_max, "ph", "", "🧪 pH del Suelo Muy Ácido", "🧪 pH del Suelo Muy Alcalino")
    
    if lectura.radiacion_solar is not None and lectura.radiacion_solar > config.radiacion_max:
        alerta = create_alert(
            sensor, "radiacion", "medium",
            "☀️ Radiación Solar Excesiva",
            f"La radiación solar en {sensor.nombre_sensor} es de {lectura.radiacion_solar} W/m², por encima del máximo de {config.radiacion_max} W/m².",
            float(lectura.radiacion_solar), float(config.radiacion_max), db
        )
        if alerta: alertas_generadas.append(alerta)
    
    return alertas_generadas


def create_alert(sensor: Sensor, tipo: str, severidad: str, titulo: str, mensaje: str, valor_actual: float, valor_umbral: float, db: Session):
    """Crear una nueva alerta si no existe una similar reciente"""
    
    # Verificar si ya existe una alerta similar en las últimas 2 horas
    result = db.execute(select(Alerta).where(
        Alerta.id_sensor == sensor.id_sensor,
        Alerta.tipo_alerta == tipo,
        Alerta.estado == 'pendiente',
        Alerta.fecha_creacion >= datetime.now() - timedelta(hours=2)
    ))
    alerta_reciente = result.scalars().first()
    
    if alerta_reciente:
        return None  # No crear alerta duplicada
    
    # Crear nueva alerta
    nueva_alerta = Alerta(
        id_sensor=sensor.id_sensor,
        # id_empresa no existe en el modelo Alerta
        tipo_alerta=tipo,
        severidad=severidad,
        # titulo no existe en el modelo Alerta, lo agregamos al mensaje
        mensaje=f"{titulo}: {mensaje}",
        valor_actual=valor_actual,
        valor_umbral=valor_umbral,
        estado='pendiente',
        fecha_creacion=datetime.now()
    )
    db.add(nueva_alerta)
    db.commit()
    db.refresh(nueva_alerta)
    return nueva_alerta
