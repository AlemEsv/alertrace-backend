import asyncio
import websockets
import json
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WS_URL = "ws://localhost:8000/sensores/live"

async def test_websocket():
    logger.info(f"Connecting to WebSocket at {WS_URL}...")
    try:
        async with websockets.connect(WS_URL) as websocket:
            logger.info("✅ Connected to WebSocket successfully!")
            
            # Wait for a message (timeout after 5 seconds if no message received)
            # Note: In a real test, we would trigger an MQTT message here to verify reception.
            # For now, we just verify the connection is established and stays open.
            try:
                logger.info("Waiting for messages (Ctrl+C to exit)...")
                # Just wait for a bit to prove connection stability
                await asyncio.sleep(2)
                logger.info("✅ Connection maintained for 2 seconds.")
                
                # If we wanted to test receiving:
                # msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                # logger.info(f"Received: {msg}")
                
            except asyncio.TimeoutError:
                logger.info("No message received (expected, as we didn't trigger MQTT).")
                
    except Exception as e:
        logger.error(f"❌ WebSocket connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_websocket())
