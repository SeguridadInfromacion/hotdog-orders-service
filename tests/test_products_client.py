"""El cliente HTTP hacia products-service: qué pasa cuando el otro servicio falla o miente."""

import uuid

import httpx
import pytest

from app.errors import NotAuthenticated, ServiceUnavailable
from app.products_client import HttpProductsGateway

PRODUCT_ID = uuid.uuid4()
PRODUCT = {"id": str(PRODUCT_ID), "name": "Perro Especial", "price": 12000, "is_available": True}


def _gateway(handler) -> HttpProductsGateway:
    gateway = HttpProductsGateway("http://products.invalid", timeout_seconds=1)
    gateway._client = httpx.Client(
        base_url="http://products.invalid", transport=httpx.MockTransport(handler)
    )
    return gateway


def _answering(response: httpx.Response) -> HttpProductsGateway:
    return _gateway(lambda request: response)


def test_returns_the_menu_in_one_call_and_sends_the_bearer_token():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path, request.headers["authorization"]))
        return httpx.Response(200, json=[PRODUCT])

    menu = _gateway(handler).get_menu("token-del-usuario")

    assert menu[PRODUCT_ID].price == 12000
    assert requests == [("/api/products", "Bearer token-del-usuario")]


def test_expired_session_upstream_is_reported_as_such_not_as_an_outage():
    with pytest.raises(NotAuthenticated):
        _answering(httpx.Response(401, json={"detail": "no"})).get_menu("t")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="boom"),
        httpx.Response(403, json={"detail": "no"}),
        httpx.Response(302, headers={"location": "http://otro.sitio/"}),
        httpx.Response(200, text="esto no es json"),
        httpx.Response(200, json={"no": "es una lista"}),
        httpx.Response(200, json=[{"id": str(PRODUCT_ID), "name": "Sin precio"}]),
    ],
)
def test_bad_upstream_answers_become_service_unavailable(response):
    with pytest.raises(ServiceUnavailable):
        _answering(response).get_menu("t")


@pytest.mark.parametrize(
    "hostile_fields",
    [
        {"price": -5000},
        {"price": 0},
        {"price": 2_000_000_000},
        {"price": "12000"},
        {"name": "x" * 300},
        {"name": ""},
    ],
)
def test_out_of_range_upstream_data_is_not_trusted(hostile_fields):
    """Aunque venga de un servicio "amigo", un precio negativo no llega a una venta."""
    response = httpx.Response(200, json=[{**PRODUCT, **hostile_fields}])
    with pytest.raises(ServiceUnavailable):
        _answering(response).get_menu("t")


def test_network_failure_becomes_service_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin conexión")

    with pytest.raises(ServiceUnavailable):
        _gateway(handler).get_menu("t")
