from fastapi.testclient import TestClient

from app.api.app import create_app


def test_health():
    client = TestClient(create_app())
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "FrameGenius"
    assert body["status"] == "ok"
    assert "ffmpeg" in body
    assert "author" not in body


def test_config_options():
    client = TestClient(create_app())
    response = client.get("/api/v1/config/options")
    assert response.status_code == 200
    assert "demo" in response.json()["llm_providers"]


def test_dashboard_served():
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert b"FrameGenius" in response.content
