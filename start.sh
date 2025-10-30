#!/bin/bash

# puerto de Railway o 8000 por defecto
PORT=${PORT:-8000}

# Iniciar uvicorn
exec uvicorn api.main:app --host 0.0.0.0 --port $PORT