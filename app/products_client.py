"""Cliente HTTP del servicio de productos (comunicación entre servicios).

orders-service no tiene acceso a la base de productos: la única forma de conocer
un precio es preguntarle a products-service, que vuelve a verificar el token.
"""

import uuid
from functools import lru_cache
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.errors import ServiceUnavailable

UNAVAILABLE = "El menú no está disponible en este momento. Intenta de nuevo en un minuto."


class ProductInfo(BaseModel):
    """Lo que este servicio necesita de un producto. También valida la respuesta ajena."""

    id: uuid.UUID
    name: str
    price: int
    is_available: bool


class ProductsGateway(Protocol):
    def get_product(self, product_id: uuid.UUID, token: str) -> ProductInfo | None: ...


class HttpProductsGateway:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        # follow_redirects=False: el token nunca se reenvía a otra dirección.
        self._client = httpx.Client(
            base_url=base_url, timeout=timeout_seconds, follow_redirects=False
        )

    def get_product(self, product_id: uuid.UUID, token: str) -> ProductInfo | None:
        """Devuelve el producto, o None si no existe. Se identifica con el token
        del mismo usuario que hace la venta."""
        try:
            response = self._client.get(
                f"/api/products/{product_id}", headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.HTTPError as error:
            raise ServiceUnavailable(UNAVAILABLE) from error

        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        if response.status_code != httpx.codes.OK:
            raise ServiceUnavailable(UNAVAILABLE)
        try:
            return ProductInfo.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise ServiceUnavailable(UNAVAILABLE) from error


@lru_cache
def get_products_gateway() -> ProductsGateway:
    settings = get_settings()
    return HttpProductsGateway(settings.products_service_url, settings.products_timeout_seconds)
