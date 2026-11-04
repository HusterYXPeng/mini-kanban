import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "kanban.db"


@pytest.fixture
def app(db_path):
    return create_app(f"sqlite:///{db_path}")


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
