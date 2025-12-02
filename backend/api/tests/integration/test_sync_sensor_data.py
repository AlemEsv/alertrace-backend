import pytest
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
from database.models.database import Sensor, Empresa, LecturaSensor

def test_receive_sensor_data_sync(client, test_db_engine):
    # Create a session using the engine from conftest
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    db = TestingSessionLocal()
    
    try:
        # 1. Setup: Create a company and a sensor
        # Check if company exists first (cleanup might not have run if previous test crashed)
        empresa = db.query(Empresa).filter(Empresa.ruc == "12345678901").first()
        if not empresa:
            empresa = Empresa(
                ruc="12345678901",
                razon_social="Test Company",
                direccion="123 Test St",
                telefono="555-0123",
                email="test@company.com",
                estado="activo"
            )
            db.add(empresa)
            db.commit()
            db.refresh(empresa)
        
        # Create Sensor
        device_id = "TEST-DEVICE-001"
        sensor = db.query(Sensor).filter(Sensor.device_id == device_id).first()
        if not sensor:
            sensor = Sensor(
                id_empresa=empresa.id_empresa,
                nombre_sensor="Test Sensor",
                tipo_sensor="multisensor",
                device_id=device_id,
                estado="activo",
                fecha_instalacion=datetime.now(timezone.utc)
            )
            db.add(sensor)
            db.commit()
            db.refresh(sensor)
        
        sensor_id = sensor.id_sensor
        
        # 2. Action: Send data to the endpoint
        payload = {
            "device_id": device_id,
            "temperatura": 25.5,
            "humedad_aire": 60.0,
            "humedad_suelo": 45.0,
            "ph_suelo": 7.0,
            "radiacion_solar": 500.0
        }
        
        response = client.post("/api/v1/sensores/data", json=payload)
        
        # 3. Assertion: Check response
        assert response.status_code == 201
        assert response.json() == {"message": "Datos recibidos correctamente"}
        
        # 4. Verification: Check if data was saved
        # Use a new session to ensure we read from DB
        db.expire_all()
        lectura = db.query(LecturaSensor).filter(LecturaSensor.id_sensor == sensor_id).order_by(LecturaSensor.timestamp.desc()).first()
        
        assert lectura is not None
        assert lectura.temperatura == 25.5
        assert lectura.humedad_aire == 60.0
        
    finally:
        db.close()
