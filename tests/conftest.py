import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/wallet-test.db",
        jwt_secret="test-secret-change-me",
        enable_external_rates=False,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def signup(client: TestClient, email: str, password: str = "Password123!", default_currency: str = "USD") -> str:
    response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": password,
            "display_name": email.split("@")[0],
            "default_currency": default_currency,
            "photo_url": "https://example.com/photo.png",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
