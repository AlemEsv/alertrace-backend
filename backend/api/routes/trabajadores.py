from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

from database.connection import get_db
from database.models.database import Trabajador, AsignacionSensor
from api.auth.dependencies import get_current_user
from supabase import create_client, Client
from api.config import settings

router = APIRouter(
    tags=["Trabajadores"]
)

# Cliente Supabase
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)


# Schemas
class TrabajadorCreate(BaseModel):
    nombre: str
    apellido: str
    dni: str
    email: EmailStr
    password: str
    telefono: Optional[str] = None
    rol: str = "worker"  # Por defecto es trabajador


class TrabajadorUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    dni: Optional[str] = None
    telefono: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None


@router.post("/", status_code=status.HTTP_201_CREATED)
async def crear_trabajador(
    trabajador_data: TrabajadorCreate,
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crear un nuevo trabajador en la empresa.
    Solo accesible para admin_empresa.
    """
    # Verificar que el usuario actual es admin de empresa
    if current_user.rol != "admin_empresa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores de empresa pueden crear trabajadores"
        )
    
    # Verificar que el email no esté en uso
    trabajador_existente = db.query(Trabajador).filter(
        Trabajador.email == trabajador_data.email
    ).first()
    
    if trabajador_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un trabajador con este email"
        )
    
    try:
        # Crear usuario en Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": trabajador_data.email,
            "password": trabajador_data.password,
        })
        
        supabase_user = auth_response.user
        if not supabase_user or not supabase_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear el usuario en el servicio de autenticación"
            )
        
        user_id = supabase_user.id
        
        # Crear el trabajador en la base de datos
        nuevo_trabajador = Trabajador(
            id_empresa=current_user.id_empresa,
            nombre=trabajador_data.nombre,
            apellido=trabajador_data.apellido,
            dni=trabajador_data.dni,
            email=trabajador_data.email,
            telefono=trabajador_data.telefono,
            rol=trabajador_data.rol,
            user_id=user_id,
            activo=True
        )
        
        db.add(nuevo_trabajador)
        db.commit()
        db.refresh(nuevo_trabajador)
        
        return {
            "message": "Trabajador creado exitosamente",
            "trabajador": {
                "id_trabajador": nuevo_trabajador.id_trabajador,
                "nombre": nuevo_trabajador.nombre,
                "apellido": nuevo_trabajador.apellido,
                "email": nuevo_trabajador.email,
                "rol": nuevo_trabajador.rol
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear trabajador: {str(e)}"
        )


@router.get("/{trabajador_id}")
async def obtener_trabajador(
    trabajador_id: int,
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener información de un trabajador específico"""
    trabajador = db.query(Trabajador).filter(
        Trabajador.id_trabajador == trabajador_id,
        Trabajador.id_empresa == current_user.id_empresa
    ).first()
    
    if not trabajador:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Obtener sensores asignados
    asignaciones = db.query(AsignacionSensor).filter(
        AsignacionSensor.id_trabajador == trabajador_id,
        AsignacionSensor.fecha_desasignacion.is_(None)
    ).all()
    
    sensores_asignados = [asig.id_sensor for asig in asignaciones]
    
    return {
        "id_trabajador": trabajador.id_trabajador,
        "nombre": trabajador.nombre,
        "apellido": trabajador.apellido,
        "dni": trabajador.dni,
        "email": trabajador.email,
        "telefono": trabajador.telefono,
        "rol": trabajador.rol,
        "activo": trabajador.activo,
        "fecha_contratacion": trabajador.fecha_contratacion,
        "sensores_asignados": sensores_asignados
    }


@router.put("/{trabajador_id}")
async def actualizar_trabajador(
    trabajador_id: int,
    trabajador_data: TrabajadorUpdate,
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Actualizar información de un trabajador.
    Solo accesible para admin_empresa.
    """
    if current_user.rol != "admin_empresa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores de empresa pueden editar trabajadores"
        )
    
    trabajador = db.query(Trabajador).filter(
        Trabajador.id_trabajador == trabajador_id,
        Trabajador.id_empresa == current_user.id_empresa
    ).first()
    
    if not trabajador:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Actualizar campos
    if trabajador_data.nombre is not None:
        trabajador.nombre = trabajador_data.nombre
    if trabajador_data.apellido is not None:
        trabajador.apellido = trabajador_data.apellido
    if trabajador_data.dni is not None:
        trabajador.dni = trabajador_data.dni
    if trabajador_data.telefono is not None:
        trabajador.telefono = trabajador_data.telefono
    if trabajador_data.rol is not None:
        trabajador.rol = trabajador_data.rol
    if trabajador_data.activo is not None:
        trabajador.activo = trabajador_data.activo
    
    try:
        db.commit()
        db.refresh(trabajador)
        
        return {
            "message": "Trabajador actualizado exitosamente",
            "trabajador": {
                "id_trabajador": trabajador.id_trabajador,
                "nombre": trabajador.nombre,
                "apellido": trabajador.apellido,
                "email": trabajador.email,
                "rol": trabajador.rol,
                "activo": trabajador.activo
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar trabajador: {str(e)}"
        )


@router.delete("/{trabajador_id}")
async def desactivar_trabajador(
    trabajador_id: int,
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Desactivar un trabajador (soft delete).
    Solo accesible para admin_empresa.
    """
    if current_user.rol != "admin_empresa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores de empresa pueden desactivar trabajadores"
        )
    
    trabajador = db.query(Trabajador).filter(
        Trabajador.id_trabajador == trabajador_id,
        Trabajador.id_empresa == current_user.id_empresa
    ).first()
    
    if not trabajador:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # No permitir desactivar al mismo admin que hace la petición
    if trabajador.id_trabajador == current_user.id_trabajador:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivarte a ti mismo"
        )
    
    try:
        trabajador.activo = False
        db.commit()
        
        return {
            "message": "Trabajador desactivado exitosamente",
            "trabajador_id": trabajador_id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al desactivar trabajador: {str(e)}"
        )


@router.get("/")
async def listar_trabajadores(
    current_user: Trabajador = Depends(get_current_user),
    db: Session = Depends(get_db),
    activos_solo: bool = True
):
    """Listar todos los trabajadores de la empresa"""
    query = db.query(Trabajador).filter(
        Trabajador.id_empresa == current_user.id_empresa
    )
    
    if activos_solo:
        query = query.filter(Trabajador.activo == True)
    
    trabajadores = query.all()
    
    resultado = []
    for trabajador in trabajadores:
        # Contar sensores asignados
        sensores_asignados = db.query(AsignacionSensor).filter(
            AsignacionSensor.id_trabajador == trabajador.id_trabajador,
            AsignacionSensor.fecha_desasignacion.is_(None)
        ).count()
        
        resultado.append({
            "id_trabajador": trabajador.id_trabajador,
            "nombre": f"{trabajador.nombre} {trabajador.apellido}",
            "dni": trabajador.dni,
            "email": trabajador.email,
            "telefono": trabajador.telefono or "N/A",
            "rol": trabajador.rol,
            "activo": trabajador.activo,
            "sensores_asignados": sensores_asignados,
            "fecha_contratacion": trabajador.fecha_contratacion.strftime("%Y-%m-%d") if trabajador.fecha_contratacion else None
        })
    
    return resultado
