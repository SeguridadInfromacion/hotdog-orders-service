"""El cliente HTTP hacia products-service: qué pasa cuando el otro servicio falla."""

import uuid

import httpx
import pytest

from app.errors import ServiceUnavailable
from app.products_client import HttpProductsGateway

PRODUCT_ID = uuid.uuid4()
PRODUCT_JSON = {
    "id": str(PRODUCT_ID),
    "name": "Perro Especial",
    "price": 12000,
    "is_available": True,
}


def _gateway(handler) -> HttpProductsGateway:
    gateway = HttpProductsGateway("http://products.invalid", timeout_seconds=1)
    gateway._client = httpx.Client(
        base_url="http://products.invalid", transport=httpx.MockTransport(handler)
    )
    return gateway


def test_returns_the_product_and_sends_the_bearer_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        seen["path"] = request.url.path
        return httpx.Response(200, json=PRODUCT_JSON)

    product = _gateway(handler).get_product(PRODUCT_ID, "token-del-usuario")

    assert product.price == 12000
    assert seen == {
        "authorization": "Bearer token-del-usuario",
        "path": f"/api/products/{PRODUCT_ID}",
    }


def test_missing_product_is_none():
    gateway = _gateway(lambda request: httpx.Response(404, json={"detail": "No"}))
    assert gateway.get_product(PRODUCT_ID, "t") is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="boom"),
        httpx.Response(401, json={"detail": "no"}),
        httpx.Response(200, text="esto no es json"),
        httpx.Response(200, json={"id": str(PRODUCT_ID), "name": "Sin precio"}),
    ],
)
def test_bad_upstream_answers_become_service_unavailable(response):
    with pytest.raises(ServiceUnavailable):
        _gateway(lambda request: response).get_product(PRODUCT_ID, "t")


def test_network_failure_becomes_service_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin conexión")

    with pytest.raises(ServiceUnavailable):
        _gateway(handler).get_product(PRODUCT_ID, "t")
