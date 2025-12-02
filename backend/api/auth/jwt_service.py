from typing import Optional
import jwt
from api.config import settings


class JWTService:
    """Servicio para manejo de tokens JWT y autenticación"""

    @staticmethod
    def verify_supabase_token(token: str) -> Optional[dict]:
        """Verificar y decodificar token JWT"""
        try:
            # Verificar el token
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )

            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None


jwt_service = JWTService()
