# tests/conftest.py
# Pytest configuration and shared test fixtures for store locator.
# Connects to: src/config.py, src/services/store_repository.py, src/api/app.py
# Created: 2026-09-06

import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
import pytest
import httpx
from src.api.app import create_app
from src.config import settings
from src.services.store_repository import StoreRepository


@pytest.fixture(scope="session")
def temp_db_path() -> Path:
    """Create a temporary SQLite database for test isolation."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_store_locator_")
    os.close(fd)
    yield Path(path)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def configure_test_settings(temp_db_path: Path):
    """Point application settings to the temporary database during tests."""
    original_db = settings.database_path
    settings.database_path = str(temp_db_path)
    yield
    settings.database_path = original_db


@pytest.fixture
def repo(temp_db_path: Path) -> StoreRepository:
    """Provide a StoreRepository backed by the isolated test database."""
    return StoreRepository(db_path=str(temp_db_path))


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an asynchronous HTTP client for API integration tests."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
