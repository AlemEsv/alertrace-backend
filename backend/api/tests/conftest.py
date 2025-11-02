import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    return engine


@pytest.fixture
def client():
    from api.main import app
    from api.config import get_db
    from database.models import Base

    # Create tables
    Base.metadata.create_all(bind=test_db())

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db()
    )

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_db_session():
    from database.models import Base
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def auth_headers():
    return {
        "Authorization": "Bearer test_token_12345",
        "Content-Type": "application/json"
    }


@pytest.fixture
def mock_user_data():
    return {
        "email": "test@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User",
        "role": "farmer"
    }


@pytest.fixture
def mock_farm_data():
    return {
        "name": "Test Farm",
        "location": "Test Location",
        "hectares": 100.5,
        "description": "A test farm"
    }


@pytest.fixture
def mock_sensor_data():
    return {
        "name": "Temperature Sensor",
        "sensor_type": "temperature",
        "location": "Field A",
        "farm_id": 1,
        "status": "active"
    }
