# Implementación - Integración Tuya Cloud ⇄ Supabase

---

## Componentes Implementados

### 1. **Servicio de Integración (TuyaIntegrationService)**
**Archivo:** `backend/api/services/tuya_integration_service.py`  

**Funcionalidades:**
- Conexión con Tuya Cloud API usando credenciales OAuth2
- Obtención de estado de dispositivos en tiempo real
- Parseo de datos de sensores (temperatura, humedad, pH, etc.)
- Sincronización de lecturas a base de datos Supabase
- Verificación automática de umbrales y creación de alertas
- Sincronización masiva de múltiples sensores
- Manejo robusto de errores y logging

**Adaptaciones realizadas:**
- Mapeo correcto de campos de BD (humedad_aire → humedad, ph_suelo → ph)
- Modelo de alertas actualizado (mensaje, severidad, estado)
- Manejo de sensores offline/online

---

### 2. **Endpoints REST API**
**Archivo:** `backend/api/routes/tuya_sync.py`  

**Endpoints implementados:**

#### `POST /api/v1/tuya/sync/sensor/{sensor_id}`
- Sincroniza un sensor específico manualmente
- Parámetros: `create_alerts` (bool, opcional)
- Requiere autenticación JWT
- Verifica permisos por empresa

#### `POST /api/v1/tuya/sync/empresa/{empresa_id}`
- Sincroniza todos los sensores de una empresa
- Parámetros: `only_active` (bool, default: true)
- Solo admin o usuarios de la misma empresa

#### `POST /api/v1/tuya/sync/all`
- Sincroniza TODOS los sensores del sistema
- Solo para administradores
- Útil para sincronización global

#### `GET /api/v1/tuya/device/{device_id}/status`
- Obtiene estado en tiempo real SIN guardar en BD
- Útil para consultas rápidas
- Retorna datos parseados y crudos

#### `GET /api/v1/tuya/device/{device_id}/info`
- Información completa del dispositivo desde Tuya
- Metadatos, estado, categoría, etc.

**Características:**
- Autenticación y autorización completas
- Validación de permisos por empresa
- Respuestas estructuradas con estadísticas
- Manejo de errores HTTP apropiados
- Logging detallado

---

### 3. **Integración en API Principal**
**Archivo:** `backend/api/main.py` 

**Rutas finales:**
- `POST /api/v1/tuya/sync/sensor/{sensor_id}`
- `POST /api/v1/tuya/sync/empresa/{empresa_id}`
- `POST /api/v1/tuya/sync/all`
- `GET /api/v1/tuya/device/{device_id}/info`
- `GET /api/v1/tuya/device/{device_id}/status`

**Documentación automática:** Disponible en `/docs` (Swagger UI)

---

### 4. **Worker de Sincronización Automática**
**Archivo:** `backend/api/tuya_sync_worker.py`  

**Funcionalidades:**
- Sincronización programada cada X minutos (configurable)
- Ejecución en background como proceso independiente
- Logging detallado de cada sincronización
- Estadísticas de éxito/fallos
- Manejo de interrupciones (Ctrl+C)

**Uso:**
```bash
# Docker
docker-compose exec api python -m api.tuya_sync_worker

# Local
python -m api.tuya_sync_worker
```

**Características:**
- Usa librería `schedule` para programación
- Loop infinito con sleep de 1 segundo
- Sincronización inicial al arrancar
- Logs con timestamp y estadísticas

---

### 5. **Scripts de Utilidad**
**Directorio:** `backend/scripts/`

#### `test_tuya_connection.py`
Script de diagnóstico para verificar conexión con Tuya Cloud.

**Funcionalidades:**
- Verifica credenciales (ACCESS_ID, ACCESS_KEY)
- Prueba conexión con API
- Obtiene token de autenticación
- Opcional: Prueba con device_id específico
- Muestra códigos de datos del sensor

**Uso:**
```bash
docker-compose exec api python scripts/test_tuya_connection.py
```

#### `sync_example.py`
Script CLI para sincronización manual de sensores.

**Comandos:**
```bash
# Listar sensores
docker-compose exec api python scripts/sync_example.py list

# Sincronizar sensor específico
docker-compose exec api python scripts/sync_example.py sync --sensor-id 4

# Sincronizar todos
docker-compose exec api python scripts/sync_example.py sync-all
```

**Características:**
- Interface de línea de comandos clara
- Mensajes informativos con emojis
- Manejo de errores robusto
- Estadísticas de sincronización

## Próximos Pasos Sugeridos

1. **Configurar umbrales de alertas** para los sensores activos
2. **Iniciar worker automático** en producción (systemd/Docker)
3. **Monitorear lecturas** durante 24h para validar estabilidad
4. **Configurar notificaciones** por email/SMS cuando haya alertas
5. **Dashboard frontend** para visualizar datos en tiempo real

---
