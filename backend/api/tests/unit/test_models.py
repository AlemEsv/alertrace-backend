from api.models import UserCreate, FarmCreate, SensorCreate, SensorData, EmpresaCreate


def test_empresa_create_schema():
    """Test EmpresaCreate schema validation."""
    empresa = EmpresaCreate(
        ruc="12345678", razon_social="Test Company", email="test@example.com"
    )
    assert empresa.ruc == "12345678"
    assert empresa.razon_social == "Test Company"
    assert empresa.email == "test@example.com"


def test_user_create_schema():
    user_data = {
        "email": "test@example.com",
        "password": "password123",
        "nombre": "Test",
        "apellido": "User",
        "dni": "12345678",
        "empresa": {
            "ruc": "20123456789",
            "razon_social": "Test Corp",
            "email": "corp@test.com",
        },
    }
    user = UserCreate(**user_data)
    assert user.email == "test@example.com"
    assert user.nombre == "Test"


def test_farm_create_schema():
    """Test FarmCreate schema validation."""
    farm = FarmCreate(name="Test Farm", location="Test Location", area_hectares=100.5)
    assert farm.name == "Test Farm"
    assert farm.location == "Test Location"
    assert farm.area_hectares == 100.5


def test_sensor_create_schema():
    """Test SensorCreate schema validation."""
    sensor = SensorCreate(
        device_id="SENSOR001",
        nombre="Temperature Sensor",
        tipo="temperature",
        id_cultivo=1,
        ubicacion_sensor="Field A",
    )
    assert sensor.device_id == "SENSOR001"
    assert sensor.nombre == "Temperature Sensor"
    assert sensor.tipo == "temperature"
    assert sensor.id_cultivo == 1


def test_sensor_data_schema():
    """Test SensorData schema validation."""
    data = SensorData(
        device_id="SENSOR001",
        temperatura=25.5,
        humedad_aire=65.0,
        humedad_suelo=45.0,
        ph_suelo=6.8,
    )
    assert data.device_id == "SENSOR001"
    assert data.temperatura == 25.5
    assert data.humedad_aire == 65.0
