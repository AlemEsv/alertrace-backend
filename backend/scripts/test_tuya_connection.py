#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from tuya_connector import TuyaOpenAPI, TUYA_LOGGER
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
TUYA_LOGGER.setLevel(logging.DEBUG)

# Cargar variables de entorno
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)


def test_tuya_connection():
    """Probar conexión con Tuya Cloud API"""
    # Obtener credenciales
    api_endpoint = os.getenv("TUYA_API_ENDPOINT", "https://openapi.tuyaus.com")
    access_id = os.getenv("TUYA_ACCESS_ID")
    access_key = os.getenv("TUYA_ACCESS_KEY")
    
    # Verificar credenciales
    print("Verificando credenciales...")
    if not access_id:
        print("ERROR: TUYA_ACCESS_ID no está configurado")
        return False
    if not access_key:
        print("ERROR: TUYA_ACCESS_KEY no está configurado")
        return False
    
    # Conectar con Tuya
    try:
        openapi = TuyaOpenAPI(api_endpoint, access_id, access_key)
        openapi.connect()
        print("Conexión exitosa!")
        print()
    except Exception as e:
        print(f"ERROR al conectar: {str(e)}")
        return False
    
    # Listar dispositivos (si hay usuario ID configurado)
    try:
        # Test con un device_id si está disponible
        test_device_id = os.getenv("TEST_DEVICE_ID")
        if test_device_id:
            print(f"Probando con device_id: {test_device_id}")
            response = openapi.get(f"/v1.0/devices/{test_device_id}")
            
            if response.get("success"):
                print("Dispositivo encontrado:")
                print(f"Nombre: {response['result'].get('name', 'N/A')}")
                print(f"ID: {response['result'].get('id', 'N/A')}")
                print(f"Categoría: {response['result'].get('category', 'N/A')}")
                print(f"Online: {response['result'].get('online', False)}")
                
                # Obtener estado del dispositivo
                status_response = openapi.get(f"/v1.0/devices/{test_device_id}/status")
                
                if status_response.get("success"):
                    print("Estado obtenido:")
                    for item in status_response['result']:
                        print(f"   {item['code']}: {item['value']}")
                else:
                    print(f"Error al obtener estado: {status_response}")
            else:
                print(f"Error: {response}")
        return True
        
    except Exception as e:
        print(f"No se pudieron listar dispositivos: {str(e)}")
        return True  # La conexión funciona, solo no podemos listar
    

def main():
    try:
        success = test_tuya_connection()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"Error durante la prueba: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
