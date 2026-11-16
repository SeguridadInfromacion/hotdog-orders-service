"""Registro de ventas: precios calculados en el servidor y aislamiento entre cajeros."""

import uuid

import pytest


def _sell(client, items, **extra):
    return client.post("/api/orders", json={"items": items, **extra})


# --- Registrar una venta -----------------------------------------------------


def test_total_is_computed_by_the_server_from_the_menu(cashier_client, menu):
    special = menu.add("Perro Especial", 12000)
    simple = menu.add("Perro Sencillo", 8000)

    response = _sell(
        cashier_client,
        [{"product_id": special, "quantity": 2}, {"product_id": simple, "quantity": 1}],
        customer_name="  Doña Marta ",
    )

    assert response.status_code == 201
    order = response.json()
    assert order["total"] == 32000
    assert order["customer_name"] == "Doña Marta"
    assert order["cashier_username"] == "cajero"
    assert [item["line_total"] for item in order["items"]] == [24000, 8000]


def test_client_cannot_send_its_own_price_or_total(cashier_client, menu):
    product = menu.add("Perro Especial", 12000)

    cheap_item = _sell(cashier_client, [{"product_id": product, "quantity": 1, "unit_price": 1}])
    cheap_order = _sell(cashier_client, [{"product_id": product, "quantity": 1}], total=1)

    assert cheap_item.status_code == 422
    assert cheap_order.status_code == 422


def test_sale_keeps_the_price_it_was_sold_at(cashier_client, menu):
    product = menu.add("Perro Especial", 12000)
    _sell(cashier_client, [{"product_id": product, "quantity": 1}])

    menu.products[uuid.UUID(product)] = menu.products[uuid.UUID(product)].model_copy(
        update={"price": 99000}
    )

    assert cashier_client.get("/api/orders").json()[0]["total"] == 12000


def test_the_user_token_is_forwarded_to_the_products_service(cashier_client, menu):
    product = menu.add("Perro Especial", 12000)

    _sell(cashier_client, [{"product_id": product, "quantity": 1}])

    assert menu.tokens_seen == [cashier_client.cookies["access_token"]]


def test_unknown_product_is_rejected(cashier_client):
    response = _sell(cashier_client, [{"product_id": str(uuid.uuid4()), "quantity": 1}])
    assert response.status_code == 422


def test_sold_out_product_is_rejected(cashier_client, menu):
    product = menu.add("Perro Agotado", 9000, is_available=False)

    response = _sell(cashier_client, [{"product_id": product, "quantity": 1}])

    assert response.status_code == 422
    assert "agotado" in response.json()["detail"]


def test_failed_sale_saves_nothing(cashier_client, menu):
    good = menu.add("Perro Especial", 12000)
    missing = str(uuid.uuid4())

    _sell(
        cashier_client,
        [{"product_id": good, "quantity": 1}, {"product_id": missing, "quantity": 1}],
    )

    assert cashier_client.get("/api/orders").json() == []


def test_products_service_down_gives_a_clean_503(cashier_client, menu):
    product = menu.add("Perro Especial", 12000)
    menu.is_down = True

    response = _sell(cashier_client, [{"product_id": product, "quantity": 1}])

    assert response.status_code == 503
    assert "Traceback" not in response.text


@pytest.mark.parametrize(
    "items",
    [
        [],
        [{"product_id": "no-es-un-uuid", "quantity": 1}],
        [{"product_id": str(uuid.uuid4()), "quantity": 0}],
        [{"product_id": str(uuid.uuid4()), "quantity": -3}],
        [{"product_id": str(uuid.uuid4()), "quantity": 21}],
        [{"product_id": str(uuid.uuid4()), "quantity": "2"}],
        [{"product_id": str(uuid.uuid4()), "quantity": 1}] * 21,
    ],
)
def test_invalid_orders_are_rejected(cashier_client, items):
    assert _sell(cashier_client, items).status_code == 422


def test_repeated_product_is_rejected(cashier_client, menu):
    product = menu.add("Perro Especial", 12000)
    line = {"product_id": product, "quantity": 1}
    assert _sell(cashier_client, [line, line]).status_code == 422


# --- Control de acceso -------------------------------------------------------


def test_anonymous_cannot_sell_or_read(anonymous_client):
    assert anonymous_client.get("/api/orders").status_code == 401
    assert _sell(anonymous_client, []).status_code == 401


def test_writes_need_the_csrf_header(cashier_client, menu):
    product = menu.add("Perro Especial", 12000)
    response = cashier_client.post(
        "/api/orders",
        json={"items": [{"product_id": product, "quantity": 1}]},
        headers={"X-Requested-With": ""},
    )
    assert response.status_code == 403


def test_cashier_only_sees_their_own_sales(cashier_client, other_cashier_client, menu):
    product = menu.add("Perro Especial", 12000)
    _sell(cashier_client, [{"product_id": product, "quantity": 1}])
    _sell(other_cashier_client, [{"product_id": product, "quantity": 3}])

    mine = cashier_client.get("/api/orders").json()

    assert [order["cashier_username"] for order in mine] == ["cajero"]
    assert cashier_client.get("/api/orders/summary").json() == {
        "orders_count": 1,
        "revenue": 12000,
    }


def test_admin_sees_every_sale(admin_client, cashier_client, other_cashier_client, menu):
    product = menu.add("Perro Especial", 12000)
    _sell(cashier_client, [{"product_id": product, "quantity": 1}])
    _sell(other_cashier_client, [{"product_id": product, "quantity": 3}])

    assert len(admin_client.get("/api/orders").json()) == 2
    assert admin_client.get("/api/orders/summary").json() == {
        "orders_count": 2,
        "revenue": 48000,
    }


def test_audit_trail_is_admin_only_and_records_sales(admin_client, cashier_client, menu):
    product = menu.add("Perro Especial", 12000)
    _sell(cashier_client, [{"product_id": product, "quantity": 1}])

    assert cashier_client.get("/api/orders/audit").status_code == 403
    trail = admin_client.get("/api/orders/audit").json()
    assert [(entry["actor"], entry["action"]) for entry in trail] == [("cajero", "venta.registrar")]
