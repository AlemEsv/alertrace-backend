from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class AlertaResponse(BaseModel):
    """Modelo para respuesta de alerta"""
    model_config = ConfigDict(from_attributes=True)
    
    id_alerta: int
    id_sensor: int
    tipo_alerta: str
    severidad: str
    titulo: str
    mensaje: str
    valor_actual: Optional[float] = None
    valor_umbral: Optional[float] = None
    resuelta: bool
    fecha_creacion: datetime

class AlertaCreate(BaseModel):
    """Modelo para crear una nueva alerta"""
    id_sensor: int
    tipo: str  # temperatura, humedad, ph, etc.
    mensaje: str
    severidad: str  # baja, media, alta, critica
    valor_medido: Optional[float] = None
    umbral_configurado: Optional[float] = None

class ConfiguracionUmbralCreate(BaseModel):
    """Modelo para crear configuración de umbrales"""
    id_cultivo: int
    temp_min: Optional[float] = 10.0  # °C
    temp_max: Optional[float] = 35.0  # °C
    humedad_aire_min: Optional[float] = 40.0  # %
    humedad_aire_max: Optional[float] = 90.0  # %
    humedad_suelo_min: Optional[float] = 30.0  # %
    humedad_suelo_max: Optional[float] = 80.0  # %
    ph_min: Optional[float] = 6.0
    ph_max: Optional[float] = 7.5
    radiacion_min: Optional[float] = 200.0  # W/m²
    radiacion_max: Optional[float] = 1000.0  # W/m²

class ConfiguracionUmbralResponse(BaseModel):
    """Modelo para respuesta de configuración de umbrales"""
    model_config = ConfigDict(from_attributes=True)
    
    id_configuracion: int
    id_cultivo: int
    temp_min: float  # °C
    temp_max: float  # °C
    humedad_aire_min: float  # %
    humedad_aire_max: float  # %
    humedad_suelo_min: float  # %
    humedad_suelo_max: float  # %
    ph_min: float
    ph_max: float
    radiacion_min: float  # W/m²
    radiacion_max: float  # W/m²
    activo: bool
    fecha_creacion: datetime
