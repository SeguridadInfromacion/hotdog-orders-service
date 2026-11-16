"""Cliente HTTP del servicio de productos (comunicación entre servicios).

orders-service no tiene acceso a la base de productos: la única forma de conocer
un precio es preguntarle a products-service, que vuelve a verificar el token.
"""

import logging
import uuid
from functools import lru_cache
from typing import Protocol

import httpx
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.config import get_settings
from app.errors import NotAuthenticated, ServiceUnavailable

logger = logging.getLogger("products-client")

UNAVAILABLE = "El menú no está disponible en este momento. Intenta de nuevo en un minuto."


class ProductInfo(BaseModel):
    """Lo que este servicio necesita de un producto.

    Los límites se repiten aquí a propósito: tampoco se confía a ciegas en lo
    que responde otro servicio. Un precio negativo o absurdo no llega a una venta.
    """

    id: uuid.UUID
    name: str = Field(min_length=1, max_length=60)
    price: int = Field(ge=1, le=1_000_000, strict=True)
    is_available: bool


Menu = dict[uuid.UUID, ProductInfo]
_menu_response = TypeAdapter(list[ProductInfo])


class ProductsGateway(Protocol):
    def get_menu(self, token: str) -> Menu: ...


class HttpProductsGateway:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        # follow_redirects=False: el token nunca se reenvía a otra dirección.
        self._client = httpx.Client(
            base_url=base_url, timeout=timeout_seconds, follow_redirects=False
        )

    def get_menu(self, token: str) -> Menu:
        """Trae el menú completo en UNA sola llamada, identificándose con el
        token del mismo usuario que hace la venta."""
        try:
            response = self._client.get(
                "/api/products", headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.HTTPError as error:
            raise ServiceUnavailable(UNAVAILABLE) from error

        if response.status_code == httpx.codes.UNAUTHORIZED:
            # La sesión venció justo entre una verificación y la otra.
            raise NotAuthenticated("Tu sesión no es válida o ya venció.")
        if response.status_code != httpx.codes.OK:
            logger.error("products-service respondió %s", response.status_code)
            raise ServiceUnavailable(UNAVAILABLE)
        try:
            products = _menu_response.validate_json(response.content)
        except ValidationError as error:
            logger.error("products-service envió un menú inválido")
            raise ServiceUnavailable(UNAVAILABLE) from error
        return {product.id: product for product in products}


@lru_cache
def get_products_gateway() -> ProductsGateway:
    settings = get_settings()
    return HttpProductsGateway(settings.products_service_url, settings.products_timeout_seconds)
