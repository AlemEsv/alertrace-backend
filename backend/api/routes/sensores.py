from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from database.connection import get_db
from database.models.database import (
    Sensor, LecturaSensor, Alerta, ConfiguracionUmbral, 
    Empresa, Trabajador, AsignacionSensor
)
from api.models.schemas import SensorData, SensorResponse, LecturaSensorResponse
from api.auth.dependencies import get_current_user

router = APIRouter(tags=["sensores"])

@router.post("/data", status_code=status.HTTP_201_CREATED)
async def receive_sensor_data(
    sensor_data: SensorData,
    db: Session = Depends(get_db)
):
    """Recibir datos de sensores públicos para dispositivos"""
    sensor = db.query(Sensor).filter(
        Sensor.device_id == sensor_data.device_id
    ).first()
    
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor with device_id {sensor_data.device_id} not found"
        )
    
    nueva_lectura = LecturaSensor(
        id_sensor=sensor.id_sensor,
        temperatura=sensor_data.temperatura,
        humedad_aire=sensor_data.humedad_aire,
        ph_suelo=sensor_data.ph_suelo,
        humedad_suelo=sensor_data.humedad_suelo,
        radiacion_solar=sensor_data.radiacion_solar,
        timestamp=datetime.fromisoformat(sensor_data.timestamp.replace('Z', '+00:00')) if sensor_data.timestamp else datetime.utcnow()
    )
    
    db.add(nueva_lectura)
    sensor.ultima_lectura = nueva_lectura.timestamp
    sensor.estado = 'activo'
    db.commit()
    db.refresh(nueva_lectura)
    
        # Verificar valores y generar alertas automáticamente
    alertas_generadas = verificar_y_generar_alertas(nueva_lectura, sensor, db)
    
    return {
        "message": "Sensor data received successfully",
        "lectura_id": nueva_lectura.id_lectura,
        "alertas_generadas": len(alertas_generadas) if alertas_generadas else 0
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def crear_sensor(
    nombre_sensor: str,
    tipo_sensor: str,
    device_id: str,
    latitud: Optional[float] = None,
    longitud: Optional[float] = None,
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crear un nuevo sensor en la empresa.
    Solo accesible para admin_empresa.
    """
    # Verificar que el usuario actual es admin de empresa
    if current_user.rol != "admin_empresa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores de empresa pueden crear sensores"
        )
    
    # Verificar que el device_id no esté en uso
    sensor_existente = db.query(Sensor).filter(
        Sensor.device_id == device_id
    ).first()
    
    if sensor_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un sensor con device_id {device_id}"
        )
    
    try:
        # Crear el sensor
        nuevo_sensor = Sensor(
            id_empresa=current_user.id_empresa,
            nombre_sensor=nombre_sensor,
            tipo_sensor=tipo_sensor,
            device_id=device_id,
            estado='activo',
            latitud=latitud,
            longitud=longitud,
            fecha_instalacion=datetime.utcnow()
        )
        
        db.add(nuevo_sensor)
        db.commit()
        db.refresh(nuevo_sensor)
        
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
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear sensor: {str(e)}"
        )

@router.get("/", response_model=List[SensorResponse])
async def obtener_sensores(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    activo: Optional[bool] = None
):
    """Obtener lista de sensores según el tipo de usuario"""
    if isinstance(current_user, Trabajador):
        # Para trabajadores: solo sensores asignados
        query = db.query(Sensor).join(AsignacionSensor).filter(
            AsignacionSensor.id_trabajador == current_user.id_trabajador,
            AsignacionSensor.fecha_desasignacion.is_(None)
        )
    elif isinstance(current_user, Empresa):
        # Para empresas: todos los sensores de sus trabajadores
        query = db.query(Sensor).join(AsignacionSensor).join(Trabajador).filter(
            Trabajador.id_empresa == current_user.id_empresa
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tipo de usuario no válido"
        )
    
    if activo is not None:
        query = query.filter(Sensor.estado == activo)
    
    sensores = query.all()
    return sensores


@router.get("/with-readings")
async def get_sensores_with_readings(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    activo: Optional[bool] = None
):
    """Obtener lista de sensores con sus lecturas más recientes"""
    # Obtener sensores según tipo de usuario
    if isinstance(current_user, Trabajador):
        query = db.query(Sensor).join(AsignacionSensor).filter(
            AsignacionSensor.id_trabajador == current_user.id_trabajador,
            AsignacionSensor.fecha_desasignacion.is_(None)
        )
    elif isinstance(current_user, Empresa):
        query = db.query(Sensor).join(AsignacionSensor).join(Trabajador).filter(
            Trabajador.id_empresa == current_user.id_empresa
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tipo de usuario no válido"
        )
    
    if activo is not None:
        query = query.filter(Sensor.estado == activo)
    
    sensores = query.all()
    
    # Para cada sensor, obtener la lectura más reciente
    result = []
    for sensor in sensores:
        lectura_reciente = db.query(LecturaSensor).filter(
            LecturaSensor.id_sensor == sensor.id_sensor
        ).order_by(LecturaSensor.timestamp.desc()).first()
        
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


def verificar_y_generar_alertas(lectura: LecturaSensor, sensor: Sensor, db: Session):
    """Verificar lecturas contra umbrales y generar alertas automáticamente"""
    from database.models.database import ConfiguracionUmbral, Alerta
    from datetime import datetime, timedelta
    
    # Obtener configuración de umbrales para la empresa
    config = db.query(ConfiguracionUmbral).filter(
        ConfiguracionUmbral.id_empresa == sensor.id_empresa,
        ConfiguracionUmbral.activo == True
    ).first()
    
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
    
    # Verificar temperatura
    if lectura.temperatura is not None:
        if lectura.temperatura < config.temp_min:
            alerta = crear_alerta(
                sensor, "temperatura", "high",
                "🌡️ Temperatura Muy Baja",
                f"La temperatura en {sensor.nombre_sensor} es de {lectura.temperatura}°C, por debajo del mínimo recomendado de {config.temp_min}°C para Sacha Inchi.",
                float(lectura.temperatura), float(config.temp_min), db
            )
            if alerta:
                alertas_generadas.append(alerta)
                
        elif lectura.temperatura > config.temp_max:
            alerta = crear_alerta(
                sensor, "temperatura", "high",
                "🌡️ Temperatura Muy Alta", 
                f"La temperatura en {sensor.nombre_sensor} es de {lectura.temperatura}°C, por encima del máximo recomendado de {config.temp_max}°C para Sacha Inchi.",
                float(lectura.temperatura), float(config.temp_max), db
            )
            if alerta:
                alertas_generadas.append(alerta)
    
    # Verificar humedad del aire
    if lectura.humedad_aire is not None:
        if lectura.humedad_aire < config.humedad_aire_min:
            alerta = crear_alerta(
                sensor, "humedad_aire", "medium",
                "💧 Humedad del Aire Baja",
                f"La humedad del aire en {sensor.nombre_sensor} es de {lectura.humedad_aire}%, por debajo del mínimo de {config.humedad_aire_min}%.",
                float(lectura.humedad_aire), float(config.humedad_aire_min), db
            )
            if alerta:
                alertas_generadas.append(alerta)
                
        elif lectura.humedad_aire > config.humedad_aire_max:
            alerta = crear_alerta(
                sensor, "humedad_aire", "medium",
                "💧 Humedad del Aire Alta",
                f"La humedad del aire en {sensor.nombre_sensor} es de {lectura.humedad_aire}%, por encima del máximo de {config.humedad_aire_max}%.",
                float(lectura.humedad_aire), float(config.humedad_aire_max), db
            )
            if alerta:
                alertas_generadas.append(alerta)
    
    # Verificar humedad del suelo
    if lectura.humedad_suelo is not None:
        if lectura.humedad_suelo < config.humedad_suelo_min:
            alerta = crear_alerta(
                sensor, "humedad_suelo", "high",
                "🌧️ Humedad del Suelo Baja - Riego Necesario",
                f"La humedad del suelo en {sensor.nombre_sensor} es de {lectura.humedad_suelo}%, por debajo del mínimo de {config.humedad_suelo_min}%. Se requiere riego.",
                float(lectura.humedad_suelo), float(config.humedad_suelo_min), db
            )
            if alerta:
                alertas_generadas.append(alerta)
                
        elif lectura.humedad_suelo > config.humedad_suelo_max:
            alerta = crear_alerta(
                sensor, "humedad_suelo", "medium",
                "🌧️ Humedad del Suelo Alta - Posible Encharcamiento",
                f"La humedad del suelo en {sensor.nombre_sensor} es de {lectura.humedad_suelo}%, por encima del máximo de {config.humedad_suelo_max}%. Revisar drenaje.",
                float(lectura.humedad_suelo), float(config.humedad_suelo_max), db
            )
            if alerta:
                alertas_generadas.append(alerta)
    
    # Verificar pH del suelo
    if lectura.ph_suelo is not None:
        if lectura.ph_suelo < config.ph_min:
            alerta = crear_alerta(
                sensor, "ph", "high",
                "🧪 pH del Suelo Muy Ácido",
                f"El pH del suelo en {sensor.nombre_sensor} es de {lectura.ph_suelo}, por debajo del mínimo de {config.ph_min}. El suelo está muy ácido para Sacha Inchi.",
                float(lectura.ph_suelo), float(config.ph_min), db
            )
            if alerta:
                alertas_generadas.append(alerta)
                
        elif lectura.ph_suelo > config.ph_max:
            alerta = crear_alerta(
                sensor, "ph", "high",
                "🧪 pH del Suelo Muy Alcalino",
                f"El pH del suelo en {sensor.nombre_sensor} es de {lectura.ph_suelo}, por encima del máximo de {config.ph_max}. El suelo está muy alcalino para Sacha Inchi.",
                float(lectura.ph_suelo), float(config.ph_max), db
            )
            if alerta:
                alertas_generadas.append(alerta)
    
    # Verificar radiación solar (solo durante el día)
    if lectura.radiacion_solar is not None and lectura.radiacion_solar > 0:
        if lectura.radiacion_solar > config.radiacion_max:
            alerta = crear_alerta(
                sensor, "radiacion", "medium",
                "☀️ Radiación Solar Excesiva",
                f"La radiación solar en {sensor.nombre_sensor} es de {lectura.radiacion_solar} W/m², por encima del máximo de {config.radiacion_max} W/m². Considerar protección.",
                float(lectura.radiacion_solar), float(config.radiacion_max), db
            )
            if alerta:
                alertas_generadas.append(alerta)
    
    return alertas_generadas


def crear_alerta(sensor: Sensor, tipo: str, severidad: str, titulo: str, mensaje: str, valor_actual: float, valor_umbral: float, db: Session):
    """Crear una nueva alerta si no existe una similar reciente"""
    from database.models.database import Alerta
    from datetime import datetime, timedelta
    
    # Verificar si ya existe una alerta similar en las últimas 2 horas
    alerta_reciente = db.query(Alerta).filter(
        Alerta.id_sensor == sensor.id_sensor,
        Alerta.tipo_alerta == tipo,
        Alerta.resuelta == False,
        Alerta.fecha_creacion >= datetime.now() - timedelta(hours=2)
    ).first()
    
    if alerta_reciente:
        return None  # No crear alerta duplicada
    
    # Crear nueva alerta
    nueva_alerta = Alerta(
        id_sensor=sensor.id_sensor,
        id_empresa=sensor.id_empresa,
        tipo_alerta=tipo,
        severidad=severidad,
        titulo=titulo,
        mensaje=mensaje,
        valor_actual=valor_actual,
        valor_umbral=valor_umbral,
        resuelta=False,
        fecha_creacion=datetime.now()
    )
    
    db.add(nueva_alerta)
    db.commit()
    db.refresh(nueva_alerta)
    
    return nueva_alerta


@router.post("/generar-alertas-test")
async def generar_alertas_de_prueba(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generar alertas de prueba basadas en las lecturas existentes"""
    # Obtener sensores de la empresa/trabajador
    if hasattr(current_user, 'id_trabajador'):
        query = db.query(Sensor).join(AsignacionSensor).filter(
            AsignacionSensor.id_trabajador == current_user.id_trabajador,
            AsignacionSensor.fecha_desasignacion.is_(None)
        )
    else:
        query = db.query(Sensor).filter(Sensor.id_empresa == current_user.id_empresa)
    
    sensores = query.all()
    total_alertas = 0
    
    for sensor in sensores:
        # Obtener las últimas lecturas
        lecturas = db.query(LecturaSensor).filter(
            LecturaSensor.id_sensor == sensor.id_sensor
        ).order_by(LecturaSensor.timestamp.desc()).limit(5).all()
        
        for lectura in lecturas:
            alertas = verificar_y_generar_alertas(lectura, sensor, db)
            total_alertas += len(alertas)
    
    return {
        "message": f"Análisis completado. Se generaron {total_alertas} alertas basadas en las lecturas existentes.",
        "sensores_analizados": len(sensores),
        "alertas_generadas": total_alertas
    }
