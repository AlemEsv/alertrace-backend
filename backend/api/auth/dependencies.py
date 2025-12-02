from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Union
from api.auth.jwt_service import jwt_service
from database.connection import get_db
from database.models.database import Trabajador, Empresa
from uuid import UUID

# Esquema de seguridad para tokens (Bearer)
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Union[Trabajador, Empresa]:
    """Extraer y validar usuario actual desde token JWT"""
    token = credentials.credentials

    # Verificar el token
    payload = jwt_service.verify_supabase_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supabase_user_id = payload.get("sub")

    if not supabase_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Buscar el trabajador

    try:
        user_uuid = UUID(supabase_user_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de UUID inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(Trabajador).where(Trabajador.user_id == user_uuid))
    trabajador = result.scalars().first()

    if not trabajador:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado en el sistema",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not trabajador.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario desactivado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return trabajador


async def get_current_trabajador(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Trabajador:
    """Dependency que solo acepta trabajadores"""
    user = await get_current_user(credentials, db)

    if not isinstance(user, Trabajador):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso solo para trabajadores",
        )

    return user


async def get_current_empresa(
    current_user: Trabajador = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Empresa:
    """Dependency que obtiene la empresa del usuario actual"""

    # Verificar que el usuario tiene una empresa asignada
    if not current_user.id_empresa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario no asociado a ninguna empresa",
        )

    # Obtener la empresa
    result = await db.execute(
        select(Empresa).where(Empresa.id_empresa == current_user.id_empresa)
    )
    empresa = result.scalars().first()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada"
        )

    return empresa


def require_admin(current_user: Trabajador = Depends(get_current_user)) -> Trabajador:
    """Validar que el usuario actual tiene rol de administrador"""
    if current_user.dni != "12345678":  # Verificación temporal de admin por DNI
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )

    return current_user


def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[dict]:
    """Autenticación opcional que no genera error si no hay token presente"""
    if credentials is None:
        return None

    token = credentials.credentials
    payload = jwt_service.verify_token(token)

    return payload
