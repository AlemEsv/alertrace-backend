from fastapi import WebSocket
from typing import List
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Gestor de conexiones WebSocket.
    Mantiene el registro de clientes conectados y permite enviar mensajes en tiempo real.
    """
    def __init__(self):
        # Lista de conexiones activas
        # Nota: En el futuro, esto podría ser un diccionario {device_id: [WebSocket]} 
        # para enviar mensajes solo a usuarios interesados en dispositivos específicos.
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Acepta una nueva conexión WebSocket y la registra."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Cliente WebSocket conectado. Total conexiones: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Elimina una conexión WebSocket de la lista."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Cliente WebSocket desconectado. Total conexiones: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """
        Envía un mensaje JSON a todos los clientes conectados.
        Si falla el envío a un cliente, se asume desconectado y se elimina.
        """
        # Iteramos sobre una copia de la lista para evitar errores si se modifica durante el bucle
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error enviando mensaje a websocket: {e}")
                self.disconnect(connection)

# Instancia global del gestor para ser importada en otros módulos
ws_manager = WebSocketManager()
