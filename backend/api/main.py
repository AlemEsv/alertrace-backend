from fastapi import FastAPI, Response, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import time
import os
from contextlib import asynccontextmanager
from api.monitoring import setup_logging, PrometheusMiddleware, setup_sentry
from prometheus_client import generate_latest

# Importar los routers modulares
from api.routes import auth, health
from api.routes.sensores import router as sensores_router
from api.routes.dashboard import router as dashboard_router
from api.routes.alertas import router as alertas_router
from api.routes.farms import router as farms_router
from api.routes.lots import router as lots_router
from api.routes.blockchain import router as blockchain_router
from api.routes.trabajadores import router as trabajadores_router
from api.routes.asignaciones import router as asignaciones_router
from api.routes.realtime import router as realtime_router
from api.services.mqtt.service import mqtt

# Configurar monitoreo
logger = setup_logging()
setup_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events"""
    logger.info("Alertrace API v1.1.0 started successfully")
    yield


app = FastAPI(
    title="Alertrace API",
    description="Sistema de monitoreo IoT agrícola",
    version="1.1.0",
    redirect_slashes=False,
    lifespan=lifespan,
)

# Inicializar MQTT
mqtt.init_app(app)

app.add_middleware(PrometheusMiddleware)

# Configuración CORS
origins = [
    "http://localhost:3000",  # Desarrollo local
    "http://localhost:5173",  # Desarrollo Vite
    "https://alertrace.vercel.app",  # Producción Vercel
]
if origins_env := os.getenv("ALLOWED_ORIGINS"):
    origins.extend(origins_env.split(","))


# Función para validar orígenes de Vercel
def allow_vercel_origins(origin: str) -> bool:
    """Permite todos los dominios de Vercel (preview y producción)"""
    allowed_patterns = [
        "https://alertrace.vercel.app",
        "https://alertrace-",  # Todos los preview deployments
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    return any(origin.startswith(pattern) for pattern in allowed_patterns)


# Agregar middleware CORS con soporte para Vercel y desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Crear router
api_v1_router = APIRouter(prefix="/api/v1")

# Incluir routers con sus prefijos correspondientes
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_v1_router.include_router(
    trabajadores_router, prefix="/trabajadores", tags=["Trabajadores"]
)
api_v1_router.include_router(
    asignaciones_router, prefix="/asignaciones", tags=["Asignaciones"]
)
api_v1_router.include_router(sensores_router, prefix="/sensores", tags=["Sensores"])
api_v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_v1_router.include_router(alertas_router, prefix="/alertas", tags=["Alertas"])
api_v1_router.include_router(farms_router, prefix="/farms", tags=["Farms"])
api_v1_router.include_router(lots_router, prefix="/lots", tags=["Lots"])
api_v1_router.include_router(
    blockchain_router, prefix="/blockchain", tags=["Blockchain"]
)

app.include_router(api_v1_router)
app.include_router(realtime_router, tags=["Realtime"])

# Health y métricas
app.include_router(health.router, tags=["Health"])


@app.get("/", tags=["Sistema"])
def root():
    """Endpoint raíz con información básica del API"""
    return {
        "message": "Alertrace API - Sistema de Trazabilidad Agrícola",
        "version": "1.1.0",
        "status": "running",
        "documentation": "/docs",
        "api_v1": "/api/v1",
        "health": "/health",
        "metrics": "/metrics",
        "timestamp": int(time.time()),
    }


@app.get("/metrics", tags=["Monitoreo"])
async def metrics():
    """Endpoint de Prometheus metrics para monitoreo"""
    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
