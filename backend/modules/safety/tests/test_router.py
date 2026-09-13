from fastapi.testclient import TestClient

from backend.main import app


def test_safety_router_included_in_app():
    client = TestClient(app)
    response = client.get("/api/safety/status")

    assert response.status_code == 200
    assert "status" in response.json()
