from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from database.connection import get_db
from database.models.database import BlockchainSync, Lot
from api.models import BlockchainSyncResponse

router = APIRouter(tags=["Blockchain"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/sync/status")
async def get_sync_status(db: DbSession) -> Dict[str, Any]:
    """Obtener estado de sincronización blockchain"""
    result_total = await db.execute(select(func.count(BlockchainSync.id)))
    total_events = result_total.scalar()

    result_processed = await db.execute(
        select(func.count(BlockchainSync.id)).where(
            BlockchainSync.processed == True  # noqa: E712
        )
    )
    processed_events = result_processed.scalar()

    result_pending = await db.execute(
        select(func.count(BlockchainSync.id)).where(
            BlockchainSync.processed == False  # noqa: E712
        )
    )
    pending_events = result_pending.scalar()

    result_failed = await db.execute(
        select(func.count(BlockchainSync.id)).where(
            BlockchainSync.processed == False,  # noqa: E712
            BlockchainSync.error_message.isnot(None),
        )
    )
    failed_events = result_failed.scalar()

    result_last_sync = await db.execute(
        select(BlockchainSync).order_by(desc(BlockchainSync.block_timestamp)).limit(1)
    )
    last_sync = result_last_sync.scalars().first()

    result_last_block = await db.execute(select(func.max(BlockchainSync.block_number)))
    last_block = result_last_block.scalar()

    return {
        "total_events": total_events or 0,
        "processed_events": processed_events or 0,
        "pending_events": pending_events or 0,
        "failed_events": failed_events or 0,
        "last_sync_time": last_sync.created_at if last_sync else None,
        "last_block_number": last_block or 0,
        "sync_health": "healthy" if failed_events == 0 else "degraded",
    }


@router.get("/sync/events", response_model=List[BlockchainSyncResponse])
async def list_sync_events(
    db: DbSession,
    skip: int = 0,
    limit: int = 100,
    processed: bool = None,
    event_name: str = None,
):
    """Listar eventos de sincronización blockchain"""
    query = select(BlockchainSync)

    if processed is not None:
        query = query.where(BlockchainSync.processed == processed)

    if event_name:
        query = query.where(BlockchainSync.event_name == event_name)

    query = (
        query.order_by(desc(BlockchainSync.block_timestamp)).offset(skip).limit(limit)
    )

    result = await db.execute(query)
    events = result.scalars().all()
    return events


@router.get("/sync/events/{tx_hash}", response_model=BlockchainSyncResponse)
async def get_sync_event(tx_hash: str, db: DbSession):
    """Obtener detalles de un evento específico por transaction hash"""
    result = await db.execute(
        select(BlockchainSync).where(BlockchainSync.tx_hash == tx_hash)
    )
    event = result.scalars().first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evento no encontrado"
        )

    return event


@router.post("/sync/retry/{sync_id}")
async def retry_failed_sync(sync_id: int, db: DbSession) -> Dict[str, Any]:
    """Reintentar procesamiento de evento fallido"""
    result = await db.execute(
        select(BlockchainSync).where(BlockchainSync.id == sync_id)
    )
    sync_event = result.scalars().first()

    if not sync_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento de sincronización no encontrado",
        )

    if sync_event.processed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este evento ya fue procesado exitosamente",
        )

    sync_event.error_message = None
    sync_event.processed = False

    await db.commit()

    return {
        "message": "Evento marcado para reintento",
        "sync_id": sync_id,
        "tx_hash": sync_event.tx_hash,
    }


@router.get("/lots/{lot_id}/blockchain-history")
async def get_lot_blockchain_history(lot_id: int, db: DbSession) -> Dict[str, Any]:
    """Obtener historial blockchain de un lote específico"""
    result_lot = await db.execute(select(Lot).where(Lot.lot_id == lot_id))
    lot = result_lot.scalars().first()

    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado"
        )

    result_events = await db.execute(
        select(BlockchainSync)
        .where(BlockchainSync.lot_id == lot_id)
        .order_by(BlockchainSync.block_timestamp)
    )
    blockchain_events = result_events.scalars().all()

    events_by_type = {}
    for event in blockchain_events:
        event_type = event.event_name
        if event_type not in events_by_type:
            events_by_type[event_type] = []
        events_by_type[event_type].append(
            {
                "tx_hash": event.tx_hash,
                "block_number": event.block_number,
                "timestamp": event.block_timestamp,
                "processed": event.processed,
            }
        )

    return {
        "lot_id": lot_id,
        "product_name": lot.product_name,
        "current_state": lot.current_state,
        "total_blockchain_events": len(blockchain_events),
        "events_by_type": events_by_type,
        "blockchain_events": [
            BlockchainSyncResponse.model_validate(e) for e in blockchain_events
        ],
    }


@router.get("/stats/daily")
async def get_daily_stats(db: DbSession, days: int = 7) -> Dict[str, Any]:
    """Obtener estadísticas diarias de eventos blockchain"""
    since_date = datetime.utcnow() - timedelta(days=days)

    # Note: func.date might be specific to the database dialect.
    # For PostgreSQL, it works. For SQLite, it might need adjustment if used.
    # Assuming PostgreSQL as per asyncpg usage.
    query = (
        select(
            func.date(BlockchainSync.block_timestamp).label("date"),
            func.count(BlockchainSync.id).label("count"),
            func.count(func.nullif(BlockchainSync.processed, False)).label(
                "processed_count"
            ),
        )
        .where(BlockchainSync.block_timestamp >= since_date)
        .group_by(func.date(BlockchainSync.block_timestamp))
        .order_by(func.date(BlockchainSync.block_timestamp))
    )

    result = await db.execute(query)
    events = result.all()

    daily_stats = []
    for event in events:
        daily_stats.append(
            {
                "date": event.date.isoformat()
                if hasattr(event.date, "isoformat")
                else str(event.date),
                "total_events": event.count,
                "processed_events": event.processed_count or 0,
                "pending_events": event.count - (event.processed_count or 0),
            }
        )

    return {"period_days": days, "daily_stats": daily_stats}


@router.get("/contracts/activity")
async def get_contract_activity(db: DbSession) -> Dict[str, Any]:
    """Obtener actividad por contrato inteligente"""
    query = (
        select(
            BlockchainSync.contract_address,
            func.count(BlockchainSync.id).label("event_count"),
            func.max(BlockchainSync.block_timestamp).label("last_activity"),
        )
        .group_by(BlockchainSync.contract_address)
        .order_by(desc("event_count"))
    )

    result = await db.execute(query)
    contracts = result.all()

    contract_stats = []
    for contract in contracts:
        contract_stats.append(
            {
                "contract_address": contract.contract_address,
                "total_events": contract.event_count,
                "last_activity": contract.last_activity,
            }
        )

    return {"total_contracts": len(contract_stats), "contracts": contract_stats}
