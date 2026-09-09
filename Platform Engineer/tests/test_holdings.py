# ABOUTME: Behavioural tests for the holdings and valuation endpoints.
# ABOUTME: Runs against the seeded household with no provider sync in progress.
from decimal import Decimal


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_holding_returns_created_holding(client, db, seeded_household_id):
    response = client.post(
        "/api/v1/holdings",
        json={"household_id": seeded_household_id, "symbol": "vti", "quantity": "3", "cost_basis": "600"},
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["symbol"] == "VTI"
    assert Decimal(body["quantity"]) == Decimal("3")
    assert body["source"] == "manual"
    assert response.headers["X-Correlation-ID"]
    stored = db.execute("SELECT quantity FROM holdings WHERE id = %s", (body["id"],)).fetchone()
    assert stored["quantity"] == Decimal("3")


def test_create_holding_for_unknown_symbol_returns_404(client, seeded_household_id):
    response = client.post(
        "/api/v1/holdings",
        json={"household_id": seeded_household_id, "symbol": "NOPE", "quantity": "1"},
    )
    assert response.status_code == 404


def test_create_holding_for_unknown_household_returns_404(client):
    response = client.post(
        "/api/v1/holdings", json={"household_id": 999999, "symbol": "VTI", "quantity": "1"}
    )
    assert response.status_code == 404


def test_create_holding_echoes_correlation_id(client, seeded_household_id):
    response = client.post(
        "/api/v1/holdings",
        json={"household_id": seeded_household_id, "symbol": "BND", "quantity": "1"},
        headers={"X-Correlation-ID": "req-123"},
    )
    assert response.status_code == 201, response.json()
    assert response.headers["X-Correlation-ID"] == "req-123"
