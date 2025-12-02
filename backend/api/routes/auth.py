from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from supabase import create_client, Client
from pydantic import BaseModel, EmailStr, field_validator, ValidationError, model_validator
from typing import Optional, Annotated

from database.connection import get_db
from database.models.database import Trabajador, Empresa
from api.models import UserCreate, Token, UserProfile, EmpresaCreate, RegisterRequest
from api.auth.dependencies import get_current_user
from ..config import settings
import logging
import uuid
import json

# Type aliases
DbSession = Annotated[AsyncSession, Depends(get_db)]
AuthCreds = Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())]

# Modelo para login con JSON
class LoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[EmailStr] = None  # Alias para compatibilidad con el frontend
    password: str
    
    @model_validator(mode='after')
    def check_email_or_username(self):
        """Valida que al menos uno de email o username esté presente"""
        if not self.email and not self.username:
            raise ValueError('Debe proporcionar email o username')
        # Si viene username pero no email, copiar username a email
        if self.username and not self.email:
            self.email = self.username
        return self
    
    @field_validator('email', 'username')
    @classmethod
    def email_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        """Valida que el email tenga un formato correcto"""
        if v is None:
            return v
        if not v or '@' not in v:
            raise ValueError('Email inválido')
        return v.lower().strip()
    
    @field_validator('password')
    @classmethod
    def password_must_not_be_empty(cls, v: str) -> str:
        """Valida que la contraseña no esté vacía"""
        if not v or len(v) < 1:
            raise ValueError('La contraseña no puede estar vacía')
        return v

# Configuración del router y clientes de Supabase
router = APIRouter()

def get_admin_client() -> Client:
    """Obtiene el cliente admin de Supabase con service_role_key"""
    admin_key = settings.supabase_service_role_key if settings.supabase_service_role_key else settings.supabase_key
    return create_client(settings.supabase_url, admin_key)

# Cliente normal para operaciones regulares (login, etc)
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(request: RegisterRequest, db: DbSession):
    """
    Registra un nuevo usuario y su empresa asociada.
    Este endpoint realiza una transacción para asegurar la consistencia de los datos.
    """
    logger.info(f"Register request received for: {request.email}")
    
    # Mapear RegisterRequest a los datos necesarios
    if request.user_type == 'empresa':
        if not request.nombre_empresa or not request.ruc:
            raise HTTPException(status_code=400, detail="Nombre de empresa y RUC son requeridos para cuentas de empresa")
        
        # Para empresa, usamos datos genéricos o derivados para el administrador
        nombre = "Admin"
        apellido = request.nombre_empresa
        # Generar un DNI temporal o usar parte del RUC si es posible, o un valor aleatorio seguro
        # Aquí usaremos los últimos 8 dígitos del RUC si es posible, o un valor dummy
        dni = request.ruc[-8:] if request.ruc and len(request.ruc) >= 8 else "00000000"
        
        empresa_data = {
            "ruc": request.ruc,
            "razon_social": request.nombre_empresa,
            "email": request.email # El email de la empresa es el del usuario admin inicial
        }
    else:
        # Lógica para agricultor (si se implementa registro directo de agricultor con empresa nueva?)
        if not request.nombres or not request.apellidos or not request.dni:
             raise HTTPException(status_code=400, detail="Nombres, apellidos y DNI son requeridos")
        
        nombre = request.nombres
        apellido = request.apellidos
        dni = request.dni
        
        # Si es agricultor independiente.
        # Usaremos su nombre como razón social y DNI como RUC
        empresa_data = {
            "ruc": request.dni, # Fallback
            "razon_social": f"{request.nombres} {request.apellidos}",
            "email": request.email
        }

    try:
        # Iniciar transacción
        logger.info("Starting DB transaction...")
        async with db.begin():
            logger.info("DB transaction started.")
            # Crear usuario en Supabase Auth usando Admin API
            supabase_admin = get_admin_client()
            logger.info("Calling Supabase create_user...")
            
            # Verificar si el usuario ya existe en Supabase para evitar error 500
            # (Opcional, pero create_user lanzará error si existe)
            
            auth_response = supabase_admin.auth.admin.create_user({
                "email": request.email,
                "password": request.password,
                "email_confirm": True,  # Auto-confirmar email
                "user_metadata": {
                    "nombre": nombre,
                    "apellido": apellido,
                    "rol": "admin_empresa",
                    "ruc_empresa": empresa_data["ruc"]
                }
            })
            logger.info("Supabase create_user finished.")
            
            supabase_user = auth_response.user
            if not supabase_user or not supabase_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se pudo crear el usuario en el servicio de autenticación."
                )
            
            user_id = supabase_user.id
            logger.info(f"Usuario creado en Supabase Auth: {user_id}")

            # 2. Crear la empresa en la base de datos
            # Verificar si la empresa ya existe por RUC
            result = await db.execute(select(Empresa).where(Empresa.ruc == empresa_data["ruc"]))
            existing_empresa = result.scalars().first()
            
            if existing_empresa:
                # Si la empresa existe, ¿asociamos el usuario a ella?
                # Por ahora, asumimos que el registro crea una NUEVA empresa.
                # Si ya existe, podría ser un error o unirse a ella.
                # Lanzamos error para evitar duplicados o inconsistencias por ahora.
                raise HTTPException(status_code=400, detail="Una empresa con este RUC ya está registrada.")

            nueva_empresa = Empresa(
                ruc=empresa_data["ruc"],
                razon_social=empresa_data["razon_social"],
                email=empresa_data["email"]
            )
            db.add(nueva_empresa)
            await db.flush() # Para obtener el id_empresa generado

            # 3. Crear el perfil del trabajador (administrador de la empresa)
            nuevo_trabajador = Trabajador(
                id_empresa=nueva_empresa.id_empresa,
                nombre=nombre,
                apellido=apellido,
                dni=dni,
                email=request.email,
                rol='admin_empresa',  # Rol por defecto para el primer usuario de una empresa
                user_id=uuid.UUID(str(user_id)),  # Vinculación con Supabase Auth
                telefono=request.telefono
            )
            db.add(nuevo_trabajador)
            logger.info(f"Trabajador admin creado: {request.email}, empresa: {nueva_empresa.id_empresa}")
        
        await db.commit()
        return {
            "message": "Usuario y empresa registrados exitosamente.",
            "user_id": str(user_id),
            "email": request.email,
            "empresa_id": nueva_empresa.id_empresa
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        error_message = str(e)
        logger.error(f"Error en el registro: {e}", exc_info=True)
        
        # Mensajes de error más específicos
        if "already exists" in error_message.lower() or "duplicate" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este email ya esta registrado"
            )
        elif "foreign key" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error de clave foranea en la base de datos: {error_message}"
            )
        elif "not null" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Campo requerido faltante: {error_message}"
            )
        elif "unique constraint" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Valor duplicado: {error_message}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error en el registro: {error_message}"
            )


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):

    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": form_data.username,
            "password": form_data.password
        })
        
        session = auth_response.session
        if not session or not session.access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {"access_token": session.access_token, "token_type": "bearer"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/login", response_model=Token)
async def login(credentials: LoginRequest, db: DbSession):
    logging.info(f"Attempting login for: {credentials.email}")
    
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        session = auth_response.session
        if not session or not session.access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        supabase_user = session.user
        user_id = uuid.UUID(str(supabase_user.id)) if supabase_user and supabase_user.id else None
        
        # Verificar que el trabajador exista en la base de datos
        result = await db.execute(select(Trabajador).where(Trabajador.user_id == user_id))
        trabajador_existente = result.scalars().first()
        
        if not trabajador_existente:
            # Si el usuario se autenticó en Supabase pero no tiene perfil de trabajador
            # esto significa que el registro no se completó correctamente
            logging.warning(f"Usuario autenticado pero sin perfil de trabajador: {credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario no autorizado. Complete el proceso de registro o contacte al administrador.",
            )
        
        logging.info(f"Login successful for: {credentials.email}")
        return {"access_token": session.access_token, "token_type": "bearer"}

    except HTTPException:
        # Re-lanzar excepciones HTTP tal cual
        raise
    except Exception as e:
        error_message = str(e)
        logging.error(f"Login error: {error_message}", exc_info=True)
        
        # Mensajes de error más específicos
        if "Invalid login credentials" in error_message:
            detail = "Credenciales incorrectas. Verifica tu email y contraseña o regístrate si no tienes cuenta."
        elif "Email not confirmed" in error_message:
            detail = "Por favor confirma tu email antes de iniciar sesión."
        else:
            detail = "Error al iniciar sesión. Por favor intenta nuevamente."
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/debug-login")
async def debug_login(request: Request):
    """
    Endpoint de debug para ver exactamente qué datos está enviando el frontend.
    REMOVER EN PRODUCCIÓN.
    """
    body = await request.body()
    try:
        body_json = await request.json()
        return {
            "raw_body": body.decode('utf-8'),
            "parsed_json": body_json,
            "headers": dict(request.headers),
            "content_type": request.headers.get('content-type')
        }
    except Exception as e:
        return {
            "raw_body": body.decode('utf-8'),
            "error": str(e),
            "headers": dict(request.headers)
        }


@router.get("/me", response_model=UserProfile)
async def read_users_me(
    credentials: AuthCreds,
    db: DbSession
):
    """
    Obtiene el perfil completo del usuario actualmente autenticado, incluyendo
    su rol y la empresa a la que pertenece.
    Valida el token de Supabase y busca el perfil asociado.
    """
    try:
        # Verificar el token con Supabase
        logging.info("Starting /me endpoint - verifying token")
        auth_response = supabase.auth.get_user(credentials.credentials)
        supabase_user = auth_response.user
        
        if not supabase_user or not supabase_user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado",
            )
        
        user_id = supabase_user.id
        logging.info(f"Token verified for user_id: {user_id}")
    except Exception as e:
        logging.error(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )

    try:
        # Busca el perfil del trabajador usando el user_id de Supabase Auth
        # Convertir user_id a UUID si es necesario
        try:
            user_id_uuid = uuid.UUID(str(user_id))
        except (ValueError, AttributeError):
            user_id_uuid = user_id
        
        logging.info(f"Querying trabajador with user_id: {user_id_uuid}")
        result = await db.execute(select(Trabajador).where(Trabajador.user_id == user_id_uuid))
        perfil_trabajador = result.scalars().first()
        logging.info(f"Trabajador found: {perfil_trabajador is not None}")

        if not perfil_trabajador:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Perfil de trabajador no encontrado para este usuario."
            )

        # Busca la empresa asociada para obtener su nombre
        result_empresa = await db.execute(select(Empresa).where(Empresa.id_empresa == perfil_trabajador.id_empresa))
        empresa_asociada = result_empresa.scalars().first()

        user_type = "empresa" if perfil_trabajador.rol == "admin_empresa" else "trabajador"
        
        # Construye la respuesta final con el modelo Pydantic UserProfile
        user_profile_data = {
            "id_trabajador": perfil_trabajador.id_trabajador,
            "user_id": perfil_trabajador.user_id,
            "nombre": perfil_trabajador.nombre,
            "apellido": perfil_trabajador.apellido,
            "email": perfil_trabajador.email,
            "rol": perfil_trabajador.rol,
            "id_empresa": perfil_trabajador.id_empresa,
            "empresa_nombre": empresa_asociada.razon_social if empresa_asociada else "Sin empresa asignada",
            "user_type": user_type
        }
        logging.info(f"User profile data: {user_profile_data}")
        return user_profile_data

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = f"Error al obtener perfil de usuario para user_id {user_id}: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error en el servidor al obtener el perfil del usuario."
        )