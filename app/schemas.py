"""Contratos de entrada y salida de la API. Toda entrada se valida aquí."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_QUANTITY_PER_ITEM = 20
MAX_ITEMS_PER_ORDER = 20

# Sin caracteres de control (saltos de línea, NUL...): no sirven en un nombre y
# permitirían falsificar líneas del log o provocar errores en la base.
PRINTABLE = r"^[^\x00-\x1f\x7f]*$"

CustomerName = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=60, pattern=PRINTABLE)
]


class StrictModel(BaseModel):
    """Rechaza campos desconocidos: el cliente no puede colar precios ni totales."""

    model_config = ConfigDict(extra="forbid")


class OrderItemIn(StrictModel):
    product_id: uuid.UUID
    quantity: int = Field(ge=1, le=MAX_QUANTITY_PER_ITEM, strict=True)


class OrderIn(StrictModel):
    """Una venta nueva. El cliente solo dice QUÉ y CUÁNTO: los precios
    y el total los calcula el servidor consultando el menú."""

    customer_name: CustomerName = ""
    items: list[OrderItemIn] = Field(min_length=1, max_length=MAX_ITEMS_PER_ORDER)

    @field_validator("items")
    @classmethod
    def _no_repeated_products(cls, items: list[OrderItemIn]) -> list[OrderItemIn]:
        product_ids = [item.product_id for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Cada producto debe aparecer una sola vez en la venta.")
        return items


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_name: str
    unit_price: int
    quantity: int
    line_total: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cashier_username: str
    customer_name: str
    total: int
    created_at: datetime
    items: list[OrderItemOut]


class SummaryOut(BaseModel):
    """Resumen de las últimas 24 horas."""

    orders_count: int
    revenue: int


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    occurred_at: datetime
    actor: str
    action: str
    target: str
    ip: str
