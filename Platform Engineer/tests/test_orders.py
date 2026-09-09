# ABOUTME: Behavioural tests for the product listing and order endpoints.
# ABOUTME: Runs against the seeded shop with no stock update in progress.


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_serves_the_storefront(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Larkspur Roasters" in response.text


def test_list_products_returns_featured_products_with_stock(client, shop_id):
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) == 8
    assert products[0]["name"] == "Hollow Creek"
    assert products[0]["on_hand"] >= 0


def test_place_order_decrements_stock(client, db, featured_product_id):
    before = db.execute("SELECT on_hand FROM stock_levels WHERE product_id = %s", (featured_product_id,)).fetchone()["on_hand"]
    response = client.post("/api/v1/orders", json={"product_id": featured_product_id, "quantity": 1})
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["product_id"] == featured_product_id
    assert body["quantity"] == 1
    assert body["on_hand"] == before - 1
    assert response.headers["X-Correlation-ID"]
    after = db.execute("SELECT on_hand FROM stock_levels WHERE product_id = %s", (featured_product_id,)).fetchone()["on_hand"]
    assert after == before - 1


def test_place_order_for_unknown_product_returns_404(client):
    response = client.post("/api/v1/orders", json={"product_id": 999999, "quantity": 1})
    assert response.status_code == 404


def test_place_order_beyond_stock_returns_409(client, db, shop_id):
    unstocked = db.execute(
        """
        SELECT p.id FROM products p
        LEFT JOIN stock_levels l ON l.product_id = p.id
        WHERE p.shop_id = %s AND COALESCE(l.on_hand, 0) = 0
        ORDER BY p.id LIMIT 1
        """,
        (shop_id,),
    ).fetchone()
    response = client.post("/api/v1/orders", json={"product_id": unstocked["id"], "quantity": 1})
    assert response.status_code == 409


def test_place_order_echoes_correlation_id(client, featured_product_id):
    response = client.post(
        "/api/v1/orders",
        json={"product_id": featured_product_id, "quantity": 1},
        headers={"X-Correlation-ID": "req-123"},
    )
    assert response.status_code == 201, response.json()
    assert response.headers["X-Correlation-ID"] == "req-123"
