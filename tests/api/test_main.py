from fastapi.testclient import TestClient
from studio.api.main import create_app


def test_create_app_returns_fastapi():
    app = create_app()
    assert app is not None
    assert app.title == "Game Studio API"


def test_cors_enabled_for_dev():
    app = create_app()
    client = TestClient(app)
    # Make an actual GET request with Origin header to trigger CORS
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" in response.headers
