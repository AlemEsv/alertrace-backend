import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any
import psutil
from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    """Health check response model"""

    status: str
    timestamp: str
    version: str
    environment: str
    uptime_seconds: float
    system_info: Dict[str, Any]
    database_status: str
    api_status: str


class MemoryInfo(BaseModel):
    """Memory information"""

    total_mb: float
    used_mb: float
    available_mb: float
    percent: float


class CPUInfo(BaseModel):
    """CPU information"""

    percent: float
    count: int


class SystemInfo(BaseModel):
    """System information"""

    memory: MemoryInfo
    cpu: CPUInfo
    disk_usage_percent: float
    python_version: str
    environment: str


class HealthMonitor:
    """Health monitoring class"""

    start_time: float = datetime.now(timezone.utc).timestamp()

    @staticmethod
    def get_uptime_seconds() -> float:
        """Get application uptime in seconds"""
        return datetime.now(timezone.utc).timestamp() - HealthMonitor.start_time

    @staticmethod
    def get_memory_info() -> MemoryInfo:
        """Get memory usage information"""
        memory = psutil.virtual_memory()
        return MemoryInfo(
            total_mb=memory.total / 1024 / 1024,
            used_mb=memory.used / 1024 / 1024,
            available_mb=memory.available / 1024 / 1024,
            percent=memory.percent,
        )

    @staticmethod
    def get_cpu_info() -> CPUInfo:
        """Get CPU information"""
        return CPUInfo(
            percent=psutil.cpu_percent(interval=0.1),
            count=psutil.cpu_count(logical=True),
        )

    @staticmethod
    def get_disk_usage() -> float:
        """Get disk usage percentage"""
        try:
            disk = psutil.disk_usage("/")
            return disk.percent
        except Exception:
            return 0.0

    @staticmethod
    def get_system_info() -> SystemInfo:
        """Get comprehensive system information"""
        return SystemInfo(
            memory=HealthMonitor.get_memory_info(),
            cpu=HealthMonitor.get_cpu_info(),
            disk_usage_percent=HealthMonitor.get_disk_usage(),
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            environment=os.getenv("ENVIRONMENT", "unknown"),
        )

    @staticmethod
    async def check_database(db_session=None) -> str:
        """Check database connectivity"""
        if db_session is None:
            return "unknown"

        try:
            # Try a simple query
            from sqlalchemy import text

            await db_session.execute(text("SELECT 1"))
            return "healthy"
        except Exception as e:
            return f"unhealthy: {str(e)[:50]}"

    @staticmethod
    async def get_health_check(
        version: str = "1.0.0", db_session=None
    ) -> HealthCheckResponse:
        """Get comprehensive health check"""
        db_status = await HealthMonitor.check_database(db_session)
        return HealthCheckResponse(
            status="healthy",
            timestamp=datetime.now(timezone.utc).isoformat(),
            version=version,
            environment=os.getenv("ENVIRONMENT", "development"),
            uptime_seconds=HealthMonitor.get_uptime_seconds(),
            system_info=HealthMonitor.get_system_info().model_dump(),
            database_status=db_status,
            api_status="operational",
        )
