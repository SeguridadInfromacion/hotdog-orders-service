"""Acceso a datos. Todas las consultas usan el ORM, que envía los valores
como parámetros: no hay SQL armado con texto del usuario (sin inyección SQL)."""

import logging
import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import AuditLog, Order

audit_logger = logging.getLogger("audit")


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, order: Order) -> Order:
        self._session.add(order)
        self._session.flush()
        return order

    def list_recent(self, *, cashier_id: uuid.UUID | None, limit: int = 100) -> Sequence[Order]:
        """Ventas más recientes. Con cashier_id, solo las de ese cajero."""
        query = (
            select(Order)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        if cashier_id is not None:
            query = query.where(Order.cashier_id == cashier_id)
        return self._session.scalars(query).all()

    def totals_since(self, since: datetime, *, cashier_id: uuid.UUID | None) -> tuple[int, int]:
        """(cantidad de ventas, dinero vendido) desde una fecha."""
        query = select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0)).where(
            Order.created_at >= since
        )
        if cashier_id is not None:
            query = query.where(Order.cashier_id == cashier_id)
        count, revenue = self._session.execute(query).one()
        return int(count), int(revenue)


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, *, actor: str, action: str, target: str = "", ip: str = "") -> None:
        self._session.add(AuditLog(actor=actor, action=action, target=target[:120], ip=ip[:45]))
        # %r: un salto de línea en un dato no puede falsificar otra línea del log.
        audit_logger.info("actor=%r action=%r target=%r ip=%r", actor, action, target, ip)

    def recent(self, limit: int = 100) -> Sequence[AuditLog]:
        query = select(AuditLog).order_by(AuditLog.occurred_at.desc()).limit(limit)
        return self._session.scalars(query).all()
