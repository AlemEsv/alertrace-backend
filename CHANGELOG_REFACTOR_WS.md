# Resumen de Cambios y Guía de Implementación Frontend

Este documento resume las mejoras de estabilidad, refactorización y nuevas funcionalidades de tiempo real implementadas en el Backend, junto con una guía para su integración en el Frontend.

## 1. Cambios Realizados en el Backend

### 🛠️ Estabilidad de Base de Datos (Supabase)
Se solucionaron los errores de conexión (`DuplicatePreparedStatementError`, `ConnectionReset`) causados por el uso de **PgBouncer en modo Transaction Pooling** (puerto 6543 de Supabase).

*   **Configuración del Engine:** Se cambió a `NullPool` para evitar conflictos con el pooler de Supabase.
*   **Prepared Statements:** Se desactivó el caché de statements (`statement_cache_size=0`) y se forzaron nombres únicos mediante UUIDs para evitar colisiones en conexiones compartidas.
*   **Corrección de Esquema:** Se alinearon los modelos ORM (`Farm`, `FarmCertification`) para usar correctamente `id_farm` en lugar de `id`.

### 🏗️ Refactorización de Arquitectura
Se reorganizó la carpeta `backend/api/services` para mejorar la modularidad y mantenibilidad:

*   **Antes:** Archivos sueltos (`mqtt_service.py`, `sensor_service.py`).
*   **Ahora:** Subcarpetas organizadas:
    *   `api/services/mqtt/`
    *   `api/services/sensors/`
    *   `api/services/websocket/`

### 📡 WebSockets (Tiempo Real)
Se implementó un sistema de transmisión de datos en tiempo real para actualizar el dashboard sin recargar la página.

*   **Nuevo Servicio:** `WebSocketManager` en `api/services/websocket/service.py`.
*   **Nuevo Endpoint:** `/sensores/live` (definido en `api/routes/realtime.py`).
*   **Integración MQTT:** Cada vez que un sensor envía datos al broker MQTT, el backend los procesa, los guarda en la BD y **automáticamente los retransmite** a todos los clientes WebSocket conectados.

---

## 2. Guía de Implementación para el Frontend

Para consumir los datos en tiempo real, el Frontend debe conectarse al nuevo endpoint de WebSockets.

### 🔌 Conexión

*   **URL de Desarrollo:** `ws://localhost:8000/sensores/live`
*   **URL de Producción:** `wss://tu-api-dominio.com/sensores/live` (Nota: usar `wss://` para conexiones seguras).

### 📨 Formato de Datos

El servidor enviará mensajes JSON con la siguiente estructura cada vez que un sensor reporte nuevos datos:

```json
{
    "type": "sensor_update",
    "device_id": "dev_mq6",
    "data": {
        "temperatura": 25.5,
        "humedad_aire": 60.0,
        "ph_suelo": 7.0,
        "humedad_suelo": 40.0,
        "radiacion_solar": 500.0,
        "timestamp": "2025-12-01T23:45:00"
    }
}
```

### 💡 Recomendaciones para React/Vue/Angular

1.  **Gestión de Estado:**
    *   Al recibir un evento `sensor_update`, busca el sensor en tu estado local (por `device_id`) y actualiza sus valores.
    *   Esto hará que las gráficas y tarjetas se "muevan" solas.

2.  **Reconexión Automática:**
    *   Las conexiones WebSocket pueden caerse. Implementa una lógica simple que intente reconectar cada 5 segundos si la conexión se cierra (`onclose`).

3.  **Ejemplo de Código (Concepto):**

```javascript
let socket = new WebSocket("ws://localhost:8000/sensores/live");

socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    if (message.type === "sensor_update") {
        console.log("Nuevo dato recibido:", message.data);
        // Actualizar estado de la UI aquí
        updateSensorUI(message.device_id, message.data);
    }
};

socket.onclose = () => {
    console.log("Conexión perdida. Reconectando en 5s...");
    setTimeout(connectWebSocket, 5000);
};
```
