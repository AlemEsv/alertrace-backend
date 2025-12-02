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

async def test_auth():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # Generate random data
        random_suffix = generate_random_string(5)
        email = f"test_{random_suffix}@example.com"
        password = "TestPassword123!"
        ruc = "20" + generate_random_digits(9)
        dni = generate_random_digits(8)
        
        logger.info(f"--- Starting Auth Test for {email} ---")

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
        try:
            response = await client.post("/auth/register", json=register_payload)
            if response.status_code == 201:
                logger.info("✅ Registration Successful")
            else:
                logger.error(f"❌ Registration Failed: {response.status_code} - {response.text}")
                return
        except Exception as e:
            logger.error(f"❌ Registration Exception: {e}")
            return

        # 2. Login
        logger.info(f"2. Logging in...")
        login_payload = {
            "username": email,
            "password": password
        }
        try:
            response = await client.post("/auth/login", json=login_payload)
            if response.status_code == 200:
                logger.info("✅ Login Successful")
                token_data = response.json()
                access_token = token_data["access_token"]
                headers = {"Authorization": f"Bearer {access_token}"}
            else:
                logger.error(f"❌ Login Failed: {response.status_code} - {response.text}")
                return
        except Exception as e:
            logger.error(f"❌ Login Exception: {e}")
            return

        # 3. Get Me
        logger.info(f"3. Getting User Profile (/auth/me)...")
        try:
            response = await client.get("/auth/me", headers=headers)
            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"✅ Get Me Successful. User ID: {user_data.get('user_id')}")
            else:
                logger.error(f"❌ Get Me Failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"❌ Get Me Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_auth())
