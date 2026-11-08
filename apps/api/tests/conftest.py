import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app


@pytest.fixture
def settings() -> Settings:
    # Small chunks so short test documents still split into several pieces.
    # `_env_file=None` keeps a developer's local .env from changing test results.
    return Settings(chunk_size=300, chunk_overlap=50, _env_file=None)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))
