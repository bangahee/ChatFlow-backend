from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings(tmp_path) -> Settings:
    database_path = tmp_path / "test.db"
    return Settings(
        _env_file=None,
        app_env="test",
        secret_key=("test-secret-key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
        database_url=f"sqlite:///{database_path}",
        cors_origins="http://localhost:5173",
    )


@pytest.fixture
def test_app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(test_app) as test_client:
        yield test_client


@pytest.fixture
def db_session(test_app: FastAPI) -> Generator[Session, None, None]:
    with TestClient(test_app):
        session_factory = test_app.state.session_factory
        with session_factory() as session:
            yield session
