from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from typing import List, Dict, Any, Annotated
from database.connection import get_db
from database.models.database import (
    Lot, Farm, HarvestEvent, ProcessingEvent, TransferEvent, Empresa
)
from api.models import (
    LotCreate, LotResponse,
    HarvestEventCreate, HarvestEventResponse,
    ProcessingEventCreate, ProcessingEventResponse,
    TransferEventCreate, TransferEventResponse
)
from api.auth.dependencies import get_current_empresa

router = APIRouter(tags=["Lots"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("/", response_model=LotResponse, status_code=status.HTTP_201_CREATED)
async def create_lot(
    lot_data: LotCreate,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Crear nuevo lote de productos"""
    if lot_data.id_farm:
        result_farm = await db.execute(select(Farm).where(
            Farm.id == lot_data.id_farm,
            Farm.id_empresa == empresa.id_empresa
        ))
        farm = result_farm.scalars().first()
        
        if not farm:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Finca no encontrada"
            )
    
    result_lot = await db.execute(select(Lot).where(Lot.lot_id == lot_data.lot_id))
    existing_lot = result_lot.scalars().first()
    if existing_lot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un lote con este ID"
        )
    
    lot = Lot(
        id_empresa=empresa.id_empresa,
        **lot_data.model_dump()
    )
    db.add(lot)
    await db.commit()
    await db.refresh(lot)
    return lot


@router.get("/", response_model=List[LotResponse])
async def list_lots(
    db: DbSession,
    empresa: Empresa = Depends(get_current_empresa),
    skip: int = 0,
    limit: int = 100,
    state: str = None,
    farm_id: int = None
):
    """Listar lotes de la empresa autenticada"""
    query = select(Lot).where(Lot.id_empresa == empresa.id_empresa)
    
    if state:
        query = query.where(Lot.current_state == state)
    
    if farm_id:
        query = query.where(Lot.id_farm == farm_id)
    
    result = await db.execute(query.order_by(desc(Lot.created_at)).offset(skip).limit(limit))
    lots = result.scalars().all()
    return lots


@router.get("/{lot_id}", response_model=LotResponse)
async def get_lot(
    lot_id: int,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Obtener detalles de un lote específico"""
    result = await db.execute(select(Lot).where(
        Lot.lot_id == lot_id,
        Lot.id_empresa == empresa.id_empresa
    ))
    lot = result.scalars().first()
    
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote no encontrado"
        )
    
    return lot


@router.patch("/{lot_id}", response_model=LotResponse)
async def update_lot(
    lot_id: int,
    lot_data: LotCreate,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Actualizar información de un lote"""
    result = await db.execute(select(Lot).where(
        Lot.lot_id == lot_id,
        Lot.id_empresa == empresa.id_empresa
    ))
    lot = result.scalars().first()
    
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote no encontrado"
        )
    
    update_data = lot_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lot, field, value)
    
    await db.commit()
    await db.refresh(lot)
    return lot


@router.get("/{lot_id}/traceability")
async def get_lot_traceability(
    lot_id: int,
    db: DbSession,
    empresa = Depends(get_current_empresa)
) -> Dict[str, Any]:
    """Obtener trazabilidad completa de un lote"""
    result_lot = await db.execute(select(Lot).where(
        Lot.lot_id == lot_id,
        Lot.id_empresa == empresa.id_empresa
    ))
    lot = result_lot.scalars().first()
    
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote no encontrado"
        )
    
    result_harvest = await db.execute(select(HarvestEvent).where(
        HarvestEvent.lot_id == lot_id
    ).order_by(HarvestEvent.event_time))
    harvest_events = result_harvest.scalars().all()
    
    result_processing = await db.execute(select(ProcessingEvent).where(
        ProcessingEvent.lot_id == lot_id
    ).order_by(ProcessingEvent.event_time))
    processing_events = result_processing.scalars().all()
    
    result_transfer = await db.execute(select(TransferEvent).where(
        TransferEvent.lot_id == lot_id
    ).order_by(TransferEvent.event_time))
    transfer_events = result_transfer.scalars().all()
    
    return {
        "lot": LotResponse.model_validate(lot),
        "harvest_events": [HarvestEventResponse.model_validate(e) for e in harvest_events],
        "processing_events": [ProcessingEventResponse.model_validate(e) for e in processing_events],
        "transfer_events": [TransferEventResponse.model_validate(e) for e in transfer_events],
        "total_events": len(harvest_events) + len(processing_events) + len(transfer_events)
    }


@router.post("/{lot_id}/harvest", response_model=HarvestEventResponse, status_code=status.HTTP_201_CREATED)
async def register_harvest_event(
    lot_id: int,
    event_data: HarvestEventCreate,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Registrar evento de cosecha para un lote"""
    result_lot = await db.execute(select(Lot).where(
        Lot.lot_id == lot_id,
        Lot.id_empresa == empresa.id_empresa
    ))
    lot = result_lot.scalars().first()
    
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote no encontrado"
        )
    
    if event_data.lot_id != lot_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El lot_id del evento no coincide con el lot_id de la URL"
        )
    
    harvest_event = HarvestEvent(**event_data.model_dump())
    db.add(harvest_event)
    await db.commit()
    await db.refresh(harvest_event)
    return harvest_event


@router.get("/{lot_id}/harvest", response_model=List[HarvestEventResponse])
async def list_harvest_events(
    lot_id: int,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Listar eventos de cosecha de un lote"""
    result_lot = await db.execute(select(Lot).where(
        Lot.lot_id == lot_id,
        Lot.id_empresa == empresa.id_empresa
    ))
    lot = result_lot.scalars().first()
    
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote no encontrado"
        )
    
    result_events = await db.execute(select(HarvestEvent).where(
        HarvestEvent.lot_id == lot_id
    ).order_by(HarvestEvent.event_time))
    events = result_events.scalars().all()
    
    return events


@router.post("/{lot_id}/processing", response_model=ProcessingEventResponse, status_code=status.HTTP_201_CREATED)
async def register_processing_event(
    lot_id: int,
    event_data: ProcessingEventCreate,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Registrar evento de procesamiento para un lote"""
    result_lot = await db.execute(select(Lot).where(
        Lot.lot_id == lot_id,
        Lot.id_empresa == empresa.id_empresa
    ))
    lot = result_lot.scalars().first()
    
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote no encontrado"
        )
    
    if event_data.lot_id != lot_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El lot_id del evento no coincide con el lot_id de la URL"
        )
    
    processing_event = ProcessingEvent(**event_data.model_dump())
    db.add(processing_event)
    await db.commit()
    await db.refresh(processing_event)
    return processing_event


@router.get("/{lot_id}/processing", response_model=List[ProcessingEventResponse])
async def list_processing_events(
    lot_id: int,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Listar eventos de procesamiento de un lote"""
    result_lot = await db.execute(select(Lot).where(
        Lot.lot_id == lot_id,
        Lot.id_empresa == empresa.id_empresa
    ))
    lot = result_lot.scalars().first()
    
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote no encontrado"
        )
    
    result_events = await db.execute(select(ProcessingEvent).where(
        ProcessingEvent.lot_id == lot_id
    ).order_by(ProcessingEvent.event_time))
    events = result_events.scalars().all()
    
    return events


@router.post("/{lot_id}/transfer", response_model=TransferEventResponse, status_code=status.HTTP_201_CREATED)
async def register_transfer_event(
    lot_id: int,
    event_data: TransferEventCreate,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Registrar evento de transferencia para un lote"""
    result_lot = await db.execute(select(Lot).where(
        Lot.lot_id == lot_id,
        Lot.id_empresa == empresa.id_empresa
    ))
    lot = result_lot.scalars().first()
    
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote no encontrado"
        )
    
    if event_data.lot_id != lot_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El lot_id del evento no coincide con el lot_id de la URL"
        )
    
    transfer_event = TransferEvent(**event_data.model_dump())
    db.add(transfer_event)
    
    lot.current_owner = event_data.to_address
    lot.current_state = "Distribuido"
    
    await db.commit()
    await db.refresh(transfer_event)
    return transfer_event


@router.get("/{lot_id}/transfer", response_model=List[TransferEventResponse])
async def list_transfer_events(
    lot_id: int,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Listar eventos de transferencia de un lote"""
    result_lot = await db.execute(select(Lot).where(
        Lot.lot_id == lot_id,
        Lot.id_empresa == empresa.id_empresa
    ))
    lot = result_lot.scalars().first()
    
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote no encontrado"
        )
    
    result_events = await db.execute(select(TransferEvent).where(
        TransferEvent.lot_id == lot_id
    ).order_by(TransferEvent.event_time))
    events = result_events.scalars().all()
    
    return events
