from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.services.websocket.service import ws_manager
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/sensores/live")
async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket para clientes en tiempo real.
    Mantiene la conexión abierta para recibir actualizaciones de sensores.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Mantiene la conexión viva esperando mensajes.
            # El protocolo WebSocket maneja ping/pong automáticamente.
            # Aquí podríamos procesar mensajes del cliente (ej. suscripciones a tópicos específicos)
            _ = await websocket.receive_text()

            # Por ahora, solo logueamos si el cliente envía algo, pero no es necesario para el flujo actual
            # logger.debug(f"Mensaje recibido del cliente: {data}")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
        ws_manager.disconnect(websocket)
