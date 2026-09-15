"""Unit tests for FastAPI health check route."""

from fastapi.testclient import TestClient
from src.backend.main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Test GET /health returns 200 OK and connected database status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_root_endpoint():
    """Test GET / returns welcome message."""
    response = client.get("/")
    assert response.status_code == 200
    assert "health_check" in response.json()
