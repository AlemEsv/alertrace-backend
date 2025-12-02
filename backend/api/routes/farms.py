from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Annotated
from database.connection import get_db
from database.models.database import Farm, FarmCertification, Empresa
from api.models import (
    FarmCreate, FarmResponse, FarmUpdate,
    FarmCertificationCreate, FarmCertificationResponse
)
from api.auth.dependencies import get_current_empresa

router = APIRouter(tags=["Farms"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("/", response_model=FarmResponse, status_code=status.HTTP_201_CREATED)
async def create_farm(
    farm_data: FarmCreate,
    db: DbSession,
    empresa: Empresa = Depends(get_current_empresa)
):
    """Crear nueva finca para la empresa autenticada"""
    farm = Farm(
        id_empresa=empresa.id_empresa,
        **farm_data.model_dump()
    )
    db.add(farm)
    await db.commit()
    await db.refresh(farm)
    return farm


@router.get("/", response_model=List[FarmResponse])
async def list_farms(
    db: DbSession,
    empresa: Empresa = Depends(get_current_empresa),
    skip: int = 0,
    limit: int = 100
):
    """Listar fincas de la empresa autenticada"""
    query = select(Farm).where(Farm.id_empresa == empresa.id_empresa)
    
    result = await db.execute(query.offset(skip).limit(limit))
    farms = result.scalars().all()
    return farms


@router.get("/{farm_id}", response_model=FarmResponse)
async def get_farm(
    farm_id: int,
    db: DbSession,
    empresa: Empresa = Depends(get_current_empresa)
):
    """Obtener detalles de una finca específica"""
    result = await db.execute(select(Farm).where(
        Farm.id_farm == farm_id,
        Farm.id_empresa == empresa.id_empresa
    ))
    farm = result.scalars().first()
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finca no encontrada"
        )
    
    return farm


@router.put("/{farm_id}", response_model=FarmResponse)
async def update_farm(
    farm_id: int,
    farm_update: FarmUpdate,
    db: DbSession,
    empresa: Empresa = Depends(get_current_empresa)
):
    """Actualizar información de una finca"""
    result = await db.execute(select(Farm).where(
        Farm.id_farm == farm_id,
        Farm.id_empresa == empresa.id_empresa
    ))
    farm = result.scalars().first()
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finca no encontrada"
        )
    
    update_data = farm_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(farm, field, value)
    
    await db.commit()
    await db.refresh(farm)
    return farm


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_farm(
    farm_id: int,
    db: DbSession,
    empresa: Empresa = Depends(get_current_empresa)
):
    """Desactivar una finca"""
    result = await db.execute(select(Farm).where(
        Farm.id == farm_id,
        Farm.id_empresa == empresa.id_empresa
    ))
    farm = result.scalars().first()
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finca no encontrada"
        )
    
    farm.active = False
    await db.commit()
    return None


@router.post("/{farm_id}/certifications", response_model=FarmCertificationResponse, status_code=status.HTTP_201_CREATED)
async def create_certification(
    farm_id: int,
    cert_data: FarmCertificationCreate,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Agregar certificación a una finca"""
    result = await db.execute(select(Farm).where(
        Farm.id == farm_id,
        Farm.id_empresa == empresa.id_empresa
    ))
    farm = result.scalars().first()
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finca no encontrada"
        )
    
    if cert_data.id_farm != farm_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id_farm no coincide con el farm_id de la URL"
        )
    
    certification = FarmCertification(**cert_data.model_dump())
    db.add(certification)
    await db.commit()
    await db.refresh(certification)
    return certification


@router.get("/{farm_id}/certifications", response_model=List[FarmCertificationResponse])
async def list_certifications(
    farm_id: int,
    db: DbSession,
    active_only: bool = True,
    empresa: Empresa = Depends(get_current_empresa)
):
    """Listar certificaciones de una finca"""
    result_farm = await db.execute(select(Farm).where(
        Farm.id == farm_id,
        Farm.id_empresa == empresa.id_empresa
    ))
    farm = result_farm.scalars().first()
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finca no encontrada"
        )
    
    query = select(FarmCertification).where(FarmCertification.id_farm == farm_id)
    
    if active_only:
        query = query.where(FarmCertification.active == True)
    
    result = await db.execute(query)
    certifications = result.scalars().all()
    return certifications


@router.patch("/certifications/{cert_id}", response_model=FarmCertificationResponse)
async def update_certification(
    cert_id: int,
    cert_data: FarmCertificationCreate,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Actualizar una certificación"""
    result = await db.execute(select(FarmCertification).join(Farm).where(
        FarmCertification.id == cert_id,
        Farm.id_empresa == empresa.id_empresa
    ))
    certification = result.scalars().first()
    
    if not certification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificación no encontrada"
        )
    
    update_data = cert_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(certification, field, value)
    
    await db.commit()
    await db.refresh(certification)
    return certification


@router.delete("/certifications/{cert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certification(
    cert_id: int,
    db: DbSession,
    empresa = Depends(get_current_empresa)
):
    """Desactivar una certificación"""
    result = await db.execute(select(FarmCertification).join(Farm).where(
        FarmCertification.id == cert_id,
        Farm.id_empresa == empresa.id_empresa
    ))
    certification = result.scalars().first()
    
    if not certification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificación no encontrada"
        )
    
    certification.active = False
    await db.commit()
    return None
