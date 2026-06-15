from decimal import Decimal

from tests.conftest import auth_header, signup


def balance_for(wallets, currency):
    for wallet in wallets:
        if wallet["currency"] == currency:
            return Decimal(wallet["balance"])
    return Decimal("0.00")


def test_credit_debit_conversion_and_history(client):
    token = signup(client, "credit@example.com", default_currency="EUR")
    headers = auth_header(token)

    credit_response = client.post(
        "/wallets/credit",
        headers=headers,
        json={"amount": "100.00", "currency": "USD", "wallet_currency": "EUR", "description": "Initial funding"},
    )
    assert credit_response.status_code == 200, credit_response.text
    credit_body = credit_response.json()
    assert credit_body["kind"] == "credit"
    assert credit_body["wallet_currency"] == "EUR"
    assert Decimal(credit_body["wallet_amount"]) == Decimal("92.00")

    debit_response = client.post(
        "/wallets/debit",
        headers=headers,
        json={"amount": "10.00", "currency": "EUR", "wallet_currency": "EUR", "description": "Cash out"},
    )
    assert debit_response.status_code == 200
    assert Decimal(debit_response.json()["wallet_amount"]) == Decimal("-10.00")

    wallets_response = client.get("/wallets", headers=headers)
    assert wallets_response.status_code == 200
    assert balance_for(wallets_response.json(), "EUR") == Decimal("82.00")

    history_response = client.get("/transactions?kind=credit&page=1&page_size=5", headers=headers)
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["total"] == 1
    assert history["items"][0]["description"] == "Initial funding"


def test_insufficient_balance_returns_conflict(client):
    token = signup(client, "debit@example.com")
    response = client.post(
        "/wallets/debit",
        headers=auth_header(token),
        json={"amount": "5.00", "currency": "USD"},
    )
    assert response.status_code == 409


def test_tiny_debit_that_rounds_to_zero_is_rejected(client):
    token = signup(client, "tiny-debit@example.com", default_currency="USD")
    response = client.post(
        "/wallets/debit",
        headers=auth_header(token),
        json={"amount": "0.01", "currency": "INR", "wallet_currency": "USD"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Converted wallet amount is too small"


def test_cross_currency_transfer_is_atomic_and_traceable(client):
    alice_token = signup(client, "sender@example.com", default_currency="USD")
    bob_token = signup(client, "recipient@example.com", default_currency="INR")

    credit_response = client.post(
        "/wallets/credit",
        headers=auth_header(alice_token),
        json={"amount": "200.00", "currency": "USD", "wallet_currency": "USD"},
    )
    assert credit_response.status_code == 200

    transfer_response = client.post(
        "/transfers",
        headers=auth_header(alice_token),
        json={
            "recipient_email": "recipient@example.com",
            "amount": "50.00",
            "currency": "USD",
            "source_wallet_currency": "USD",
            "target_wallet_currency": "INR",
            "description": "Dinner split",
            "idempotency_key": "transfer-0001",
        },
    )
    assert transfer_response.status_code == 200, transfer_response.text
    transfer = transfer_response.json()
    assert transfer["kind"] == "transfer_out"
    assert transfer["exchange_provider"] == "seed"
    assert transfer["related_transaction_id"] is not None

    repeat_response = client.post(
        "/transfers",
        headers=auth_header(alice_token),
        json={
            "recipient_email": "recipient@example.com",
            "amount": "50.00",
            "currency": "USD",
            "source_wallet_currency": "USD",
            "target_wallet_currency": "INR",
            "description": "Dinner split",
            "idempotency_key": "transfer-0001",
        },
    )
    assert repeat_response.status_code == 200
    assert repeat_response.json()["id"] == transfer["id"]

    alice_wallets = client.get("/wallets", headers=auth_header(alice_token)).json()
    bob_wallets = client.get("/wallets", headers=auth_header(bob_token)).json()
    assert balance_for(alice_wallets, "USD") == Decimal("150.00")
    assert balance_for(bob_wallets, "INR") == Decimal("4150.00")

    bob_history = client.get("/transactions?currency=USD", headers=auth_header(bob_token)).json()
    assert bob_history["total"] == 1
    assert bob_history["items"][0]["kind"] == "transfer_in"


def test_tiny_transfer_that_rounds_sender_debit_to_zero_is_rejected(client):
    sender_token = signup(client, "tiny-sender@example.com", default_currency="USD")
    recipient_token = signup(client, "tiny-recipient@example.com", default_currency="JPY")

    transfer_response = client.post(
        "/transfers",
        headers=auth_header(sender_token),
        json={
            "recipient_email": "tiny-recipient@example.com",
            "amount": "0.01",
            "currency": "INR",
            "source_wallet_currency": "USD",
            "target_wallet_currency": "JPY",
            "description": "Rounding exploit attempt",
        },
    )
    assert transfer_response.status_code == 400
    assert transfer_response.json()["detail"] == "Converted wallet amount is too small"

    recipient_wallets = client.get("/wallets", headers=auth_header(recipient_token)).json()
    assert balance_for(recipient_wallets, "JPY") == Decimal("0.00")
