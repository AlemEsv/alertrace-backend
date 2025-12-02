import os
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Use a file-based DB for testing to allow sharing between sync and async engines
TEST_DB_FILE = "test.db"
if os.path.exists(TEST_DB_FILE):
    os.remove(TEST_DB_FILE)

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
os.environ["ASYNC_DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_FILE}"


@pytest.fixture(scope="session")
def test_db_engine():
    # Sync engine
    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    from database.models.database import Base
    Base.metadata.create_all(bind=engine)
    yield engine
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)

@pytest.fixture(scope="session")
def async_test_db_engine():
    # Async engine
    engine = create_async_engine(
        os.environ["ASYNC_DATABASE_URL"],
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    return engine

@pytest.fixture
def client(test_db_engine, async_test_db_engine):
    from api.main import app
    from database.connection import get_db, get_sync_db

    # Sync session maker
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine
    )

    # Async session maker
    AsyncTestingSessionLocal = sessionmaker(
        async_test_db_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )

    # Override async get_db
    async def override_get_db():
        async with AsyncTestingSessionLocal() as session:
            yield session

    # Override sync get_sync_db
    def override_get_sync_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_sync_db] = override_get_sync_db
    
    # Mock MQTT to avoid connection attempts and event loop issues
    from unittest.mock import MagicMock, AsyncMock
    from api.services.mqtt.service import mqtt
    mqtt.client = MagicMock()
    mqtt.mqtt_startup = AsyncMock()
    mqtt.mqtt_shutdown = AsyncMock()
    
    with TestClient(app) as c:
        yield c
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_db_session(test_db_engine):
    from sqlalchemy.orm import Session
    session = Session(bind=test_db_engine)
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
