"""Modelos de la base de datos (el esquema real vive en el repo hotdog-database)."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UtcDateTime, utcnow


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cashier_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    cashier_username: Mapped[str] = mapped_column(String(32))
    customer_name: Mapped[str] = mapped_column(String(60), default="")
    total: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, index=True)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.product_name"
    )


class OrderItem(Base):
    """Renglón de una venta. Guarda nombre y precio tal como eran al vender:
    si después cambia el menú, la venta histórica no se altera."""

    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    product_name: Mapped[str] = mapped_column(String(60))
    unit_price: Mapped[int]
    quantity: Mapped[int]
    line_total: Mapped[int]

    order: Mapped[Order] = relationship(back_populates="items")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    actor: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(48))
    target: Mapped[str] = mapped_column(String(120), default="")
    ip: Mapped[str] = mapped_column(String(45), default="")
