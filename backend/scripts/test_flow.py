import asyncio
import httpx
import logging
import random
import string
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api/v1"

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

def generate_random_digits(length=8):
    return ''.join(random.choices(string.digits, k=length))

async def test_full_flow():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # Generate random data
        random_suffix = generate_random_string(5)
        email = f"test_{random_suffix}@example.com"
        password = "TestPassword123!"
        ruc = "20" + generate_random_digits(9)
        dni = generate_random_digits(8)
        
        logger.info(f"--- Starting Full Flow Test for {email} ---")

        # 1. Register
        register_payload = {
            "email": email,
            "password": password,
            "nombre": "Test",
            "apellido": "User",
            "dni": dni,
            "empresa": {
                "ruc": ruc,
                "razon_social": f"Test Company {random_suffix}",
                "email": f"company_{random_suffix}@example.com"
            }
        }
        
        logger.info(f"1. Registering user...")
        response = await client.post("/auth/register", json=register_payload)
        if response.status_code != 201:
            logger.error(f"❌ Registration Failed: {response.status_code} - {response.text}")
            return
        logger.info("✅ Registration Successful")

        # 2. Login
        logger.info(f"2. Logging in...")
        login_payload = {
            "username": email,
            "password": password
        }
        response = await client.post("/auth/login", json=login_payload)
        if response.status_code != 200:
            logger.error(f"❌ Login Failed: {response.status_code} - {response.text}")
            return
        
        token_data = response.json()
        access_token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        logger.info("✅ Login Successful")

        # 3. Create Farm
        logger.info(f"3. Creating Farm...")
        farm_payload = {
            "name": f"Farm {random_suffix}",
            "location": "Test Address 123",
            "area_hectares": 50.5
        }
        response = await client.post("/farms/", json=farm_payload, headers=headers)
        if response.status_code == 201:
            farm_data = response.json()
            farm_id = farm_data.get("id_farm")
            logger.info(f"Farm Created. ID: {farm_id}")
        else:
            logger.error(f"Create Farm Failed: {response.status_code} - {response.text}")
            # Continue anyway to test sensors independently if possible, though they might need farm context?
            # Based on schemas, sensors don't seem to require farm_id in creation payload directly, 
            # but they are linked to company via user.
            
        # 4. Create Sensor
        # Note: SensorCreate schema requires id_cultivo. We might need to create a crop (cultivo) first?
        # Let's check if we can create a sensor with dummy id_cultivo or if we need to create one.
        # Looking at routes/sensores.py, it doesn't seem to validate id_cultivo existence explicitly in the snippet I read,
        # but DB constraints might enforce it.
        # Let's try to create a sensor. If it fails due to FK, we know we need a crop.
        
        logger.info(f"4. Creating Sensor...")
        sensor_payload = {
            "device_id": f"dev_{random_suffix}",
            "nombre": f"Sensor {random_suffix}",
            "tipo": "temperature",
            "id_cultivo": 1, # Assuming 1 exists or is not checked strictly yet? Or maybe we need to create it.
            "ubicacion_sensor": "Field A",
            "coordenadas_lat": -12.0,
            "coordenadas_lng": -77.0
        }
        
        response = await client.post("/sensores/", json=sensor_payload, headers=headers)
        if response.status_code == 201:
            logger.info("✅ Sensor Created")
        else:
            logger.error(f"❌ Create Sensor Failed: {response.status_code} - {response.text}")
            if "foreign key constraint" in response.text.lower() and "cultivo" in response.text.lower():
                 logger.warning("⚠️ Failed due to missing Cultivo. Skipping sensor creation for now.")

        # 5. List Farms
        logger.info(f"5. Listing Farms...")
        response = await client.get("/farms/", headers=headers)
        if response.status_code == 200:
            farms = response.json()
            logger.info(f"✅ Listed {len(farms)} farms")
        else:
            logger.error(f"❌ List Farms Failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    asyncio.run(test_full_flow())
