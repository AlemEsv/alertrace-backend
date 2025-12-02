import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from api.main import app
from api.models import UserCreate
import uuid
from datetime import datetime, timezone

# Mock Supabase response objects
class MockUser:
    def __init__(self, id, email):
        self.id = id
        self.email = email

class MockAuthResponse:
    def __init__(self, user, session=None):
        self.user = user
        self.session = session

class MockSession:
    def __init__(self, access_token, user=None):
        self.access_token = access_token
        self.user = user

@pytest.fixture
def mock_supabase_and_jwt():
    with patch("api.routes.auth.get_admin_client") as mock_get_admin, \
         patch("api.routes.auth.supabase") as mock_client, \
         patch("api.auth.dependencies.jwt_service.verify_supabase_token") as mock_verify:
        
        # Setup Admin Client (Register)
        mock_admin_instance = MagicMock()
        mock_get_admin.return_value = mock_admin_instance
        
        test_user_id = str(uuid.uuid4())
        
        def create_user_side_effect(payload):
            return MockAuthResponse(user=MockUser(id=test_user_id, email=payload["email"]))
            
        mock_admin_instance.auth.admin.create_user.side_effect = create_user_side_effect
        
        # Setup Regular Client (Login)
        def sign_in_side_effect(payload):
            user = MockUser(id=test_user_id, email=payload["email"])
            return MockAuthResponse(
                user=user,
                session=MockSession(access_token="fake-jwt-token", user=user)
            )
            
        mock_client.auth.sign_in_with_password.side_effect = sign_in_side_effect
        
        # Setup JWT Verification
        mock_verify.return_value = {"sub": test_user_id, "role": "authenticated"}
        
        yield mock_get_admin, mock_client, mock_verify

def test_full_sensor_flow(client, mock_supabase_and_jwt):
    # 1. Register User & Company
    user_data = {
        "email": "farmer@example.com",
        "password": "SecurePassword123!",
        "nombre": "Juan",
        "apellido": "Perez",
        "dni": "12345678",
        "empresa": {
            "ruc": "20123456789",
            "razon_social": "Agro Tech S.A.",
            "email": "contact@agrotech.com"
        }
    }
    
    response = client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 201, f"Register failed: {response.text}"
    
    # 2. Login
    login_data = {
        "email": "farmer@example.com",
        "password": "SecurePassword123!"
    }
    response = client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200, f"Login failed: {response.text}"
    token_data = response.json()
    access_token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 3. Create Sensor
    sensor_data = {
        "device_id": "SENSOR-E2E-001",
        "nombre": "Sensor E2E",
        "tipo": "multisensor",
        "id_cultivo": 1,
        "coordenadas_lat": -12.0,
        "coordenadas_lng": -77.0,
        "ubicacion_sensor": "Campo 1"
    }
    
    response = client.post("/api/v1/sensores/", json=sensor_data, headers=headers)
    assert response.status_code == 201, f"Create sensor failed: {response.text}"
    created_sensor = response.json()["sensor"]
    assert created_sensor["device_id"] == sensor_data["device_id"]
    
    # 4. Send Data (Sync Endpoint)
    payload = {
        "device_id": "SENSOR-E2E-001",
        "temperatura": 25.5,
        "humedad_aire": 60.0,
        "humedad_suelo": 45.0,
        "ph_suelo": 7.0,
        "radiacion_solar": 500.0
    }
    
    response = client.post("/api/v1/sensores/data", json=payload)
    assert response.status_code == 201, f"Send data failed: {response.text}"
    
    # 5. Verify Data (List Sensors or Get Sensor Data)
    response = client.get("/api/v1/sensores/", headers=headers)
    assert response.status_code == 200
    sensors = response.json()
    found = False
    for s in sensors:
        if s["device_id"] == "SENSOR-E2E-001":
            found = True
            break
    assert found, "Sensor not found in list"
