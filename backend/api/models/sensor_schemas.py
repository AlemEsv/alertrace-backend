from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class SensorData(BaseModel):
    """Datos de sensores IoT"""

    device_id: str  # Identificador físico del dispositivo
    temperatura: Optional[float] = None  # Temperatura del aire (°C)
    humedad_aire: Optional[float] = None  # Humedad del aire (%)
    humedad_suelo: Optional[float] = None  # Humedad del suelo (%)
    ph_suelo: Optional[float] = None  # Nivel de pH del suelo
    radiacion_solar: Optional[float] = None  # Radiación solar (W/m²)
    timestamp: Optional[str] = None


class SensorCreate(BaseModel):
    device_id: str  # Identificador físico del dispositivo IoT
    nombre: str
    tipo: str
    id_cultivo: int
    ubicacion_sensor: Optional[str] = None
    coordenadas_lat: Optional[float] = None
    coordenadas_lng: Optional[float] = None
    intervalo_lectura: Optional[int] = 300


class SensorResponse(BaseModel):
    """Modelo para respuesta de sensor"""

    model_config = ConfigDict(from_attributes=True)

    id_sensor: int
    device_id: str
    nombre_sensor: str
    tipo_sensor: str
    id_empresa: int
    estado: str
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    ubicacion_sensor: Optional[str] = None
    fecha_instalacion: datetime


class LecturaSensorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_lectura: int
    id_sensor: int
    timestamp: datetime
    temperatura: Optional[float] = None  # Temperatura del ambiente (°C)
    humedad_aire: Optional[float] = None  # Humedad del ambiente (%)
    humedad_suelo: Optional[float] = None  # Humedad del suelo (%)
    ph_suelo: Optional[float] = None  # pH del suelo
    radiacion_solar: Optional[float] = None  # Radiación solar (W/m²)


class SensorUpdate(BaseModel):
    """Schema para actualizar sensor"""

    ubicacion_sensor: Optional[str] = None
    coordenadas_lat: Optional[float] = None
    coordenadas_lng: Optional[float] = None
    nombre_sensor: Optional[str] = None
    descripcion: Optional[str] = None
    estado: Optional[str] = None

    @field_validator("ubicacion_sensor")
    @classmethod
    def validate_ubicacion(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            # Sanitizar espacios extras y limitar longitud
            v = v.strip()
            if len(v) > 128:
                raise ValueError("ubicacion_sensor no puede exceder 128 caracteres")
            if len(v) == 0:
                return None
        return v

    @field_validator("coordenadas_lat")
    @classmethod
    def validate_lat(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -90 or v > 90):
            raise ValueError("latitud debe estar entre -90 y 90")
        return v

    @field_validator("coordenadas_lng")
    @classmethod
    def validate_lng(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -180 or v > 180):
            raise ValueError("longitud debe estar entre -180 y 180")
        return v


class SensorMoveRequest(BaseModel):
    """Schema para mover sensores entre áreas"""

    from_ubicacion: str
    to_ubicacion: str
    sensor_ids: Optional[List[int]] = None

    @field_validator("from_ubicacion", "to_ubicacion")
    @classmethod
    def validate_ubicacion(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 128:
            raise ValueError("ubicacion no puede exceder 128 caracteres")
        if len(v) == 0:
            raise ValueError("ubicacion no puede estar vacía")
        return v


class SensorMoveResponse(BaseModel):
    """Respuesta de movimiento de sensores"""

    updated: int
    errors: List[Dict[str, Any]] = []
    sensors: List[SensorResponse] = []


class DeleteAreaResponse(BaseModel):
    """Respuesta de eliminación de área"""

    deleted_ubicacion: str
    sensors_moved: int
    new_ubicacion: Optional[str] = None
