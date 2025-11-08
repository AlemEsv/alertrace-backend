"""
OpenID Connect Discovery Endpoints para Alchemy Account Kit

Estos endpoints son requeridos por Alchemy para verificar JWTs usando
el método "Bring Your Own Auth" (BYOA).

Flujo:
1. Frontend solicita JWT al backend con nonce
2. Backend genera JWT firmado con RSA (RS256)
3. Frontend pasa JWT a Alchemy
4. Alchemy consulta /.well-known/openid-configuration
5. Alchemy obtiene jwks_uri
6. Alchemy consulta /jwks para obtener claves públicas
7. Alchemy verifica firma del JWT
8. Alchemy crea/recupera Smart Account del usuario
"""

from fastapi import APIRouter, HTTPException
from api.config import settings
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["OpenID Connect"])


@router.get("/.well-known/openid-configuration")
async def openid_configuration():
    """
    OpenID Connect Discovery endpoint

    Este endpoint es consultado por Alchemy para descubrir la configuración
    de OpenID Connect de nuestro servidor de autenticación.

    Especificación: https://openid.net/specs/openid-connect-discovery-1_0.html

    Returns:
        dict: Metadata del servidor OpenID Connect
    """
    try:
        config = {
            "issuer": settings.api_domain,
            "jwks_uri": f"{settings.api_domain}/jwks",
            "id_token_signing_alg_values_supported": ["RS256"],
            "authorization_endpoint": f"{settings.api_domain}/api/v1/auth/authorize",
            "token_endpoint": f"{settings.api_domain}/api/v1/auth/token",
            "response_types_supported": ["code", "token", "id_token"],
            "subject_types_supported": ["public"],
            "grant_types_supported": ["authorization_code", "implicit"],
        }

        logger.info("OpenID configuration requested")
        return config

    except Exception as e:
        logger.error(f"Error generating OpenID config: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error generating OpenID configuration"
        )


@router.get("/jwks")
async def jwks():
    """
    JSON Web Key Set (JWKS) endpoint

    Expone las claves públicas RSA que Alchemy usa para verificar
    la firma de los JWTs generados por nuestro backend.

    El campo 'kid' (Key ID) debe coincidir con el header del JWT.

    Especificación: https://datatracker.ietf.org/doc/html/rfc7517

    Returns:
        dict: Conjunto de claves públicas en formato JWK
    """
    try:
        # Leer clave pública RSA
        public_key_pem = settings.get_alchemy_public_key()

        # Cargar clave pública
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(),
            backend=default_backend()
        )

        # Extraer números públicos RSA (n y e)
        public_numbers = public_key.public_numbers()

        # Convertir a base64url (formato JWK)
        def int_to_base64url(num: int) -> str:
            """Convierte un entero a base64url encoding (RFC 7515)"""
            # Convertir número a bytes (big-endian)
            num_bytes = num.to_bytes(
                (num.bit_length() + 7) // 8,
                byteorder='big'
            )
            # Codificar en base64url (sin padding '=')
            return base64.urlsafe_b64encode(num_bytes).rstrip(b'=').decode('utf-8')

        # Generar JWK (JSON Web Key)
        jwk = {
            "kty": "RSA",                          # Key Type
            "use": "sig",                          # Public Key Use (signature)
            "kid": settings.alchemy_jwt_kid,       # Key ID (debe coincidir con JWT header)
            "alg": "RS256",                        # Algorithm
            "n": int_to_base64url(public_numbers.n),  # RSA modulus
            "e": int_to_base64url(public_numbers.e),  # RSA exponent
        }

        logger.info(f"JWKS requested, returning key with kid={settings.alchemy_jwt_kid}")

        return {
            "keys": [jwk]
        }

    except FileNotFoundError:
        logger.error("Public key file not found")
        raise HTTPException(
            status_code=500,
            detail="Public key not configured"
        )
    except Exception as e:
        logger.error(f"Error generating JWKS: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating JWKS: {str(e)}"
        )


@router.get("/jwks/debug")
async def jwks_debug():
    """
    Endpoint de debug para verificar la configuración de JWKS

    ⚠️ Solo para desarrollo. Remover en producción.

    Returns:
        dict: Información de debug sobre la configuración
    """
    try:
        public_key_pem = settings.get_alchemy_public_key()

        return {
            "status": "ok",
            "kid": settings.alchemy_jwt_kid,
            "issuer": settings.api_domain,
            "audience": settings.alchemy_audience_id,
            "public_key_loaded": bool(public_key_pem),
            "public_key_length": len(public_key_pem),
            "public_key_preview": public_key_pem[:100] + "...",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
