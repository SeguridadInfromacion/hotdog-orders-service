"""Entradas hostiles y fugas de información en orders-service."""

import pytest


def _sell(client, items, **extra):
    return client.post("/api/orders", json={"items": items, **extra})


@pytest.mark.parametrize("name", ["Ana\x00", "Ana\nINFO audit actor='otro'", "Ana\x7f"])
def test_control_characters_in_the_customer_name_are_rejected(cashier_client, menu, name):
    product = menu.add("Perro Especial", 12000)
    response = _sell(cashier_client, [{"product_id": product, "quantity": 1}], customer_name=name)
    assert response.status_code == 422


def test_validation_errors_do_not_echo_the_request(cashier_client):
    response = _sell(cashier_client, [], customer_name="dato-privado-del-cliente")
    assert response.status_code == 422
    assert "dato-privado-del-cliente" not in response.text


def test_absurd_numbers_get_a_clean_validation_error(cashier_client, menu):
    product = menu.add("Perro Especial", 12000)
    response = cashier_client.post(
        "/api/orders",
        content=f'{{"items":[{{"product_id":"{product}","quantity":1e400}}]}}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_the_menu_is_fetched_once_per_sale_however_many_lines(cashier_client, menu):
    lines = [{"product_id": menu.add(f"Perro {n}", 5000), "quantity": 1} for n in range(8)]

    assert _sell(cashier_client, lines).status_code == 201
    assert len(menu.tokens_seen) == 1


def test_trailing_slash_does_not_redirect(cashier_client):
    response = cashier_client.get("/api/orders/", follow_redirects=False)
    assert response.status_code == 404
