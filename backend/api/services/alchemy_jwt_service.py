"""
Servicio para generar JWTs compatibles con Alchemy Account Kit

Este servicio genera JWTs firmados con RS256 que Alchemy usa para
autenticar usuarios mediante el método "Bring Your Own Auth".

Diferencias con jwt_service.py:
- jwt_service.py: Usa HS256 para autenticación con Supabase
- alchemy_jwt_service.py: Usa RS256 para autenticación con Alchemy

Los JWTs de Alchemy NO se usan para autenticar con nuestro backend,
solo se pasan a Alchemy SDK en el frontend.
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from api.config import settings
import logging

logger = logging.getLogger(__name__)


class AlchemyJWTService:
    """
    Servicio separado para generar JWTs solo para Alchemy Account Kit

    Este servicio NO interfiere con el jwt_service.py existente (Supabase).
    """

    def __init__(self):
        self.private_key = settings.get_alchemy_private_key()
        self.kid = settings.alchemy_jwt_kid
        self.issuer = settings.api_domain
        self.audience = settings.alchemy_audience_id

    def generate_jwt_for_alchemy(
        self,
        user_id: str,
        email: Optional[str] = None,
        nonce: Optional[str] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Genera JWT firmado con RS256 para autenticación con Alchemy

        Este JWT cumple con los requisitos de Alchemy Account Kit:
        - Algoritmo: RS256 (asimétrico con RSA)
        - Claims requeridos: iss, sub, aud, nonce
        - Header: alg, typ, kid

        Args:
            user_id: UUID del usuario en nuestro sistema (sub claim)
            email: Email del usuario (metadata opcional)
            nonce: sha256(targetPublicKey) sin 0x prefix (requerido por Alchemy)
            expires_delta: Duración del token (default: 30 días)

        Returns:
            str: JWT firmado listo para enviar a Alchemy

        Raises:
            Exception: Si hay error generando el token

        Example:
            >>> jwt = alchemy_jwt_service.generate_jwt_for_alchemy(
            ...     user_id="550e8400-e29b-41d4-a716-446655440000",
            ...     nonce="abc123def456...",
            ...     email="user@example.com"
            ... )
        """
        try:
            # Duración del token (30 días por defecto)
            if expires_delta is None:
                expires_delta = timedelta(days=30)

            now = datetime.utcnow()
            exp = now + expires_delta

            # Claims requeridos por Alchemy
            payload = {
                "iss": self.issuer,      # Issuer - debe coincidir con OpenID config
                "sub": user_id,          # Subject - ID único del usuario
                "aud": self.audience,    # Audience - ID de Alchemy Dashboard
                "iat": int(now.timestamp()),   # Issued at
                "exp": int(exp.timestamp()),   # Expiration
            }

            # Agregar nonce si está presente (requerido para crear wallet)
            if nonce:
                payload["nonce"] = nonce

            # Metadata adicional (opcional)
            if email:
                payload["email"] = email

            # Header con Key ID
            headers = {
                "alg": "RS256",
                "typ": "JWT",
                "kid": self.kid  # Debe coincidir con el kid en /jwks
            }

            # Firmar con clave privada RSA
            token = jwt.encode(
                payload,
                self.private_key,
                algorithm="RS256",
                headers=headers
            )

            logger.info(f"Generated Alchemy JWT for user {user_id} (nonce: {bool(nonce)})")

            return token

        except Exception as e:
            logger.error(f"Error generating Alchemy JWT: {str(e)}")
            raise Exception(f"Failed to generate JWT for Alchemy: {str(e)}")

    def validate_nonce(self, nonce: str) -> bool:
        """
        Valida formato del nonce

        El nonce debe ser sha256(targetPublicKey) en hexadecimal sin 0x prefix
        Longitud esperada: 64 caracteres hexadecimales

        Args:
            nonce: Nonce a validar

        Returns:
            bool: True si el nonce es válido
        """
        if not nonce:
            return False

        # Debe ser hexadecimal sin 0x
        if nonce.startswith("0x"):
            return False

        # Debe tener 64 caracteres (256 bits en hex)
        if len(nonce) != 64:
            return False

        # Debe ser hexadecimal válido
        try:
            int(nonce, 16)
            return True
        except ValueError:
            return False


# Singleton instance
alchemy_jwt_service = AlchemyJWTService()
