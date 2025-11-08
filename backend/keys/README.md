# Claves RSA para Alchemy Account Kit

## Archivos en este directorio

### `alchemy_private_key.pem` 🔐
**Clave privada RSA de 2048 bits**

- **Uso:** Firmar JWTs para autenticación con Alchemy Account Kit
- **Algoritmo:** RS256 (RSA Signature with SHA-256)
- **CRÍTICO:** Nunca commitear este archivo a Git
- **CRÍTICO:** Nunca compartir con nadie
- **CRÍTICO:** En producción, usar secretos de Azure/AWS/GCP

### `alchemy_public_key.pem` 🔓
**Clave pública RSA**

- **Uso:** Alchemy usa esta clave para verificar la firma de los JWTs
- **Expuesto en:** Endpoint `/jwks` del backend
- **Seguro:** Este archivo sí puede ser público

## Key ID (KID)

**KID generado:** `21047662e12769c6693d1d3b5b53b6bc`

Este identificador único se incluye en el header de los JWTs y permite a Alchemy identificar qué clave pública usar para verificar la firma.

## Generación de Claves

Las claves fueron generadas usando OpenSSL:

```bash
# Generar clave privada
openssl genrsa -out alchemy_private_key.pem 2048

# Extraer clave pública
openssl rsa -in alchemy_private_key.pem -pubout -out alchemy_public_key.pem

# Generar KID
openssl rand -hex 16
```

## Variables de Entorno Necesarias

Agregar al archivo `.env`:

```bash
# Alchemy JWT Configuration
ALCHEMY_JWT_KID=21047662e12769c6693d1d3b5b53b6bc
ALCHEMY_AUDIENCE_ID=alchemy-temp-audience-id
API_DOMAIN=http://localhost:8000  # Cambiar a https://api.alertrace.com en producción
```

## Seguridad en Producción

⚠️ **NO usar archivos .pem en producción**

En producción, almacenar las claves privadas en:
- **AWS:** AWS Secrets Manager o AWS KMS
- **Azure:** Azure Key Vault
- **GCP:** Google Cloud Secret Manager
- **Alternativa:** HashiCorp Vault

Ejemplo con AWS Secrets Manager:

```python
import boto3

def get_private_key():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='alchemy-private-key')
    return response['SecretString']
```

## Verificación

Para verificar que las claves son válidas:

```bash
# Verificar formato de clave privada
openssl rsa -in alchemy_private_key.pem -check

# Verificar que la pública coincide con la privada
openssl rsa -in alchemy_private_key.pem -pubout | diff - alchemy_public_key.pem
```

## Renovación de Claves

Si necesitas regenerar las claves:

1. Generar nuevo par de claves
2. Generar nuevo KID
3. Actualizar endpoint `/jwks` con nueva clave pública
4. Actualizar variable `ALCHEMY_JWT_KID` en `.env`
5. Reiniciar backend
6. **Importante:** Mantener claves antiguas activas por 24h para tokens en tránsito
