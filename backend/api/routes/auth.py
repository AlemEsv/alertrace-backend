from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from supabase import create_client, Client
from pydantic import BaseModel, EmailStr, field_validator, ValidationError, model_validator
from typing import Optional

from database.connection import get_db
from database.models.database import Trabajador, Empresa
from api.models.schemas import UserCreate, Token, UserProfile, EmpresaCreate
from api.auth.dependencies import get_current_user
from ..config import settings
import logging
import uuid
import json

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

# Configuración del router y cliente de Supabase
router = APIRouter()
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)
logging.basicConfig(level=logging.INFO)
# Updated: 2025-10-29 - Fixed user registration with empresa field

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Registra un nuevo usuario y su empresa asociada.
    Este endpoint realiza una transacción para asegurar la consistencia de los datos.
    """
    try:
        # Iniciar transacción
        with db.begin_nested():
            # 1. Crear usuario en Supabase Auth
            auth_response = supabase.auth.sign_up({
                "email": user_data.email,
                "password": user_data.password,
            })
            
            supabase_user = auth_response.user
            if not supabase_user or not supabase_user.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo crear el usuario en el servicio de autenticación.")
            
            user_id = supabase_user.id

            # 2. Crear la empresa en la base de datos
            nueva_empresa = Empresa(
                ruc=user_data.empresa.ruc,
                razon_social=user_data.empresa.razon_social,
                email=user_data.empresa.email
            )
            db.add(nueva_empresa)
            db.flush() # Para obtener el id_empresa generado

            # 3. Crear el perfil del trabajador (administrador de la empresa)
            nuevo_trabajador = Trabajador(
                id_empresa=nueva_empresa.id_empresa,
                nombre=user_data.nombre,
                apellido=user_data.apellido,
                dni=user_data.dni,
                email=user_data.email,
                rol='admin_empresa',  # Rol por defecto para el primer usuario de una empresa
                user_id=user_id  # Vinculación con Supabase Auth
            )
            db.add(nuevo_trabajador)
        
        db.commit()
        return {"message": "Usuario y empresa registrados exitosamente.", "user_id": user_id, "email": user_data.email}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        error_message = str(e)
        logging.error(f"Error en el registro: {e}", exc_info=True)
        
        # Mensajes de error más específicos
        if "already exists" in error_message.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este email ya esta registrado")
        elif "foreign key" in error_message.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error de clave foranea en la base de datos: {error_message}")
        elif "not null" in error_message.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Campo requerido faltante: {error_message}")
        elif "unique constraint" in error_message.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Valor duplicado: {error_message}")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en el registro: {error_message}")


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
async def login(request: Request, db: Session = Depends(get_db)):

    try:
        # Leer el cuerpo de la solicitud para debugging
        body = await request.body()
        logging.info(f"📨 Login request body: {body.decode('utf-8')}")
        
        # Parsear y validar los datos
        try:
            body_json = await request.json()
            logging.info(f"Parsed JSON: {body_json}")
            credentials = LoginRequest(**body_json)
        except ValidationError as ve:
            logging.error(f"Validation error: {ve.errors()}")
            error_details = []
            for error in ve.errors():
                field = error.get('loc', ['unknown'])[0]
                msg = error.get('msg', 'Invalid value')
                error_details.append(f"{field}: {msg}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Datos de login inválidos",
                    "errors": error_details,
                    "hint": "Asegúrate de enviar 'email' (formato válido) y 'password'"
                }
            )
        except json.JSONDecodeError:
            logging.error("JSON decode error")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El cuerpo de la solicitud debe ser JSON válido"
            )
        
        logging.info(f"Attempting login for: {credentials.email}")
        
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
        user_id = supabase_user.id if supabase_user else None
        
        # Verificar que el trabajador exista en la base de datos
        trabajador_existente = db.query(Trabajador).filter(Trabajador.user_id == user_id).first()
        
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
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
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
        perfil_trabajador = db.query(Trabajador).filter(Trabajador.user_id == user_id_uuid).first()
        logging.info(f"Trabajador found: {perfil_trabajador is not None}")

        if not perfil_trabajador:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Perfil de trabajador no encontrado para este usuario."
            )

        # Busca la empresa asociada para obtener su nombre
        empresa_asociada = db.query(Empresa).filter(Empresa.id_empresa == perfil_trabajador.id_empresa).first()

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