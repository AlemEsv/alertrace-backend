from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

class LotState(str, Enum):
    EN_FINCA = "EnFinca"
    EN_PROCESO = "EnProceso"
    DISTRIBUIDO = "Distribuido"

class BlockchainRole(str, Enum):
    """Roles en blockchain"""
    PRODUCTOR = "Productor"
    PROCESADOR = "Procesador"
    DISTRIBUIDOR = "Distribuidor"

class CertificationType(str, Enum):
    """Tipos de certificación"""
    ORGANIC = "Organic"
    FAIR_TRADE = "FairTrade"
    RAINFOREST_ALLIANCE = "RainforestAlliance"
    GLOBAL_GAP = "GlobalGAP"
    UTZ = "UTZ"

class FarmCreate(BaseModel):
    """Creación de finca"""
    name: str
    location: str
    geohash: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    area_hectares: Optional[Decimal] = None

class FarmUpdate(BaseModel):
    """Actualización de finca"""
    name: Optional[str] = None
    location: Optional[str] = None
    geohash: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    area_hectares: Optional[Decimal] = None

class FarmResponse(BaseModel):
    """Respuesta de finca"""
    model_config = ConfigDict(from_attributes=True)
    
    id_farm: int
    id_empresa: int
    name: str
    location: str
    geohash: Optional[str]
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]
    area_hectares: Optional[Decimal]
    created_at: datetime
    updated_at: datetime

class FarmCertificationCreate(BaseModel):
    """Creación de certificación"""
    id_farm: int
    certification_type: str
    certifier_name: str
    certification_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    document_url: Optional[str] = None
    document_hash: Optional[str] = None

class FarmCertificationResponse(BaseModel):
    """Respuesta de certificación"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    id_farm: int
    certification_type: str
    certifier_name: str
    certification_number: Optional[str]
    issue_date: Optional[date]
    expiry_date: Optional[date]
    document_url: Optional[str]
    document_hash: Optional[str]
    active: bool
    created_at: datetime
    updated_at: datetime

class LotCreate(BaseModel):
    """Creación de lote"""
    lot_id: int
    id_farm: Optional[int] = None
    product_name: str
    product_variety: Optional[str] = None
    quantity: Decimal
    unit: str
    harvest_date: Optional[date] = None
    current_owner: str

class LotResponse(BaseModel):
    """Respuesta de lote"""
    model_config = ConfigDict(from_attributes=True)
    
    lot_id: int
    id_empresa: int
    id_farm: Optional[int]
    product_name: str
    product_variety: Optional[str]
    quantity: Decimal
    unit: str
    harvest_date: Optional[date]
    current_state: str
    current_owner: str
    token_uri: Optional[str]
    metadata_hash: Optional[str]
    created_at: datetime
    updated_at: datetime

class HarvestEventCreate(BaseModel):
    """Creación de evento de cosecha"""
    lot_id: int
    actor_address: str
    actor_name: Optional[str] = None
    harvest_date: date
    location_geohash: Optional[str] = None
    location_name: Optional[str] = None
    quality_score: Optional[int] = None
    weather_conditions: Optional[str] = None
    notes: Optional[str] = None
    event_time: datetime

class HarvestEventResponse(BaseModel):
    """Respuesta de evento de cosecha"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    lot_id: int
    actor_address: str
    actor_name: Optional[str]
    harvest_date: date
    location_geohash: Optional[str]
    location_name: Optional[str]
    quality_score: Optional[int]
    weather_conditions: Optional[str]
    notes: Optional[str]
    tx_hash: Optional[str]
    block_number: Optional[int]
    event_time: datetime
    created_at: datetime

class ProcessingEventCreate(BaseModel):
    """Creación de evento de procesamiento"""
    lot_id: int
    actor_address: str
    actor_name: Optional[str] = None
    process_type: str
    process_date: date
    location_geohash: Optional[str] = None
    location_name: Optional[str] = None
    input_quantity: Optional[Decimal] = None
    output_quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    duration_hours: Optional[int] = None
    temperature: Optional[Decimal] = None
    humidity: Optional[Decimal] = None
    quality_result: Optional[int] = None
    notes: Optional[str] = None
    event_time: datetime

class ProcessingEventResponse(BaseModel):
    """Respuesta de evento de procesamiento"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    lot_id: int
    actor_address: str
    actor_name: Optional[str]
    process_type: str
    process_date: date
    location_geohash: Optional[str]
    location_name: Optional[str]
    input_quantity: Optional[Decimal]
    output_quantity: Optional[Decimal]
    unit: Optional[str]
    duration_hours: Optional[int]
    temperature: Optional[Decimal]
    humidity: Optional[Decimal]
    quality_result: Optional[int]
    notes: Optional[str]
    tx_hash: Optional[str]
    block_number: Optional[int]
    event_time: datetime
    created_at: datetime

class TransferEventCreate(BaseModel):
    """Creación de evento de transferencia"""
    lot_id: int
    from_address: str
    from_name: Optional[str] = None
    to_address: str
    to_name: Optional[str] = None
    transfer_date: date
    from_location_geohash: Optional[str] = None
    from_location_name: Optional[str] = None
    to_location_geohash: Optional[str] = None
    to_location_name: Optional[str] = None
    quantity_transferred: Optional[Decimal] = None
    unit: Optional[str] = None
    transport_method: Optional[str] = None
    estimated_delivery: Optional[date] = None
    notes: Optional[str] = None
    event_time: datetime

class TransferEventResponse(BaseModel):
    """Respuesta de evento de transferencia"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    lot_id: int
    from_address: str
    from_name: Optional[str]
    to_address: str
    to_name: Optional[str]
    transfer_date: date
    from_location_geohash: Optional[str]
    from_location_name: Optional[str]
    to_location_geohash: Optional[str]
    to_location_name: Optional[str]
    quantity_transferred: Optional[Decimal]
    unit: Optional[str]
    transport_method: Optional[str]
    estimated_delivery: Optional[date]
    notes: Optional[str]
    tx_hash: Optional[str]
    block_number: Optional[int]
    event_time: datetime
    created_at: datetime

class BlockchainSyncResponse(BaseModel):
    """Respuesta de sincronización blockchain"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    tx_hash: str
    block_number: int
    log_index: int
    event_name: str
    contract_address: str
    lot_id: Optional[int]
    event_table: Optional[str]
    event_id: Optional[int]
    processed: bool
    processed_at: Optional[datetime]
    error_message: Optional[str]
    block_timestamp: datetime
    created_at: datetime
