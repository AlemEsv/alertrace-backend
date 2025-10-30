# syntax=docker/dockerfile:1
FROM python:3.11-slim as builder

WORKDIR /build

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements desde backend/
COPY backend/requirements.txt ./

# Crear entorno virtual e instalar dependencias
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Etapa final
FROM python:3.11-slim

WORKDIR /app

# Instalar solo cliente PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN useradd -m -u 1000 appuser

# Copiar entorno virtual desde builder
COPY --from=builder /opt/venv /opt/venv

# Copiar código de la aplicación desde backend/
COPY --chown=appuser:appuser backend/api/ ./api/
COPY --chown=appuser:appuser backend/database/ ./database/

# Copiar script de inicio
COPY --chown=appuser:appuser start.sh ./
RUN chmod +x start.sh

# Cambiar a usuario no-root
USER appuser

# Activar entorno virtual
ENV PATH="/opt/venv/bin:$PATH"

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Comando por defecto
CMD ["sh", "start.sh"]