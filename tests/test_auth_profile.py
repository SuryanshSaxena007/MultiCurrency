from tests.conftest import auth_header, signup


def test_signup_login_and_profile_update(client):
    token = signup(client, "alice@example.com", default_currency="EUR")
    profile_response = client.get("/profile", headers=auth_header(token))
    assert profile_response.status_code == 200
    assert profile_response.json()["default_currency"] == "EUR"

    login_response = client.post("/auth/login", json={"email": "alice@example.com", "password": "Password123!"})
    assert login_response.status_code == 200
    assert login_response.json()["token_type"] == "bearer"

    update_response = client.patch(
        "/profile",
        headers=auth_header(token),
        json={"display_name": "Alice Wallet", "default_currency": "GBP", "photo_url": "https://cdn.example.com/a.png"},
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["display_name"] == "Alice Wallet"
    assert body["default_currency"] == "GBP"

    wallets_response = client.get("/wallets", headers=auth_header(token))
    assert wallets_response.status_code == 200
    currencies = {wallet["currency"] for wallet in wallets_response.json()}
    assert {"EUR", "GBP"}.issubset(currencies)


def test_duplicate_email_is_rejected(client):
    signup(client, "duplicate@example.com")
    response = client.post(
        "/auth/signup",
        json={"email": "duplicate@example.com", "password": "Password123!", "display_name": "Duplicate"},
    )
    assert response.status_code == 409
