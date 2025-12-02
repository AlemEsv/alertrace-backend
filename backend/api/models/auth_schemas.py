from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
import uuid


class EmpresaCreate(BaseModel):
    ruc: str
    razon_social: str
    email: EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nombre: str
    apellido: str
    dni: str
    empresa: EmpresaCreate


class RegisterRequest(BaseModel):
    """Modelo para registro desde el frontend"""

    email: EmailStr
    password: str
    user_type: str

    # Campos para Industria
    nombre_empresa: Optional[str] = None
    ruc: Optional[str] = None

    # Campos para Agricultor
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    dni: Optional[str] = None

    telefono: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class UserProfile(BaseModel):
    id_trabajador: int
    user_id: uuid.UUID
    nombre: str
    apellido: str
    email: EmailStr
    rol: str
    id_empresa: Optional[int] = None  # Puede ser None si no tiene empresa asignada
    empresa_nombre: str
    user_type: str

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    """Modelo para solicitud de login"""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Modelo para respuesta de login exitoso"""

    access_token: str
    token_type: str
    user_id: str
    username: str


class UserInfo(BaseModel):
    """Modelo para información de usuario autenticado"""

    user_id: str
    username: str
    role: str
    nombre: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    user_type: str = "trabajador"  # "trabajador" o "empresa"

    # Campos específicos para trabajadores
    dni: Optional[str] = None

    # Campos específicos para empresas
    ruc: Optional[str] = None
    tipo_empresa: Optional[str] = None

    # Campos comunes
    fecha_registro: Optional[str] = None
