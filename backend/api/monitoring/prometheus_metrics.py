from prometheus_client import Counter, Histogram, Gauge
import time
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


# Request metrics
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0)
)

# Database metrics
db_query_count = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation', 'table']
)

db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation', 'table'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0)
)

# Application metrics
active_connections = Gauge(
    'active_connections',
    'Number of active connections'
)

# Error metrics
error_count = Counter(
    'errors_total',
    'Total errors',
    ['error_type', 'endpoint']
)

# Cache metrics
cache_hits = Counter(
    'cache_hits_total',
    'Total cache hits'
)

cache_misses = Counter(
    'cache_misses_total',
    'Total cache misses'
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics"""

    async def dispatch(self, request: Request, call_next: Callable) -> any:
        start_time = time.time()
        
        # Record request start
        active_connections.inc()
        response = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            error_count.labels(
                error_type=type(exc).__name__,
                endpoint=request.url.path
            ).inc()
            raise
        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Usa 500 si response es None (hubo excepción antes de asignarlo)
            status_code = response.status_code if response else 500

            request_count.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=status_code
            ).inc()
            
            request_duration.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
            
            # Record response end
            active_connections.dec()
        
        return response