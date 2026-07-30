import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    app = create_app("sqlite://", seed=True)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def employee_headers():
    return {"X-Actor-ID": "3"}


@pytest.fixture
def manager_headers():
    return {"X-Actor-ID": "2"}


@pytest.fixture
def admin_headers():
    return {"X-Actor-ID": "1"}
