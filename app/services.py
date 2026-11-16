"""Casos de uso de ventas: registrar una venta y consultar el historial."""

import uuid
from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy.orm import Session

from app.database import utcnow
from app.errors import Unprocessable
from app.models import Order, OrderItem
from app.products_client import Menu, ProductsGateway
from app.repositories import AuditRepository, OrderRepository
from app.schemas import OrderIn, OrderItemIn, SummaryOut
from app.security import AuthenticatedUser

SUMMARY_WINDOW = timedelta(hours=24)


class SalesRegister:
    """Registra ventas. Los precios salen del menú oficial, nunca del cliente."""

    def __init__(self, session: Session, products: ProductsGateway) -> None:
        self._session = session
        self._products = products
        self._orders = OrderRepository(session)
        self._audit = AuditRepository(session)

    def create_order(self, data: OrderIn, *, user: AuthenticatedUser, ip: str) -> Order:
        menu = self._products.get_menu(user.token)
        items = [self._price_item(item, menu) for item in data.items]
        order = Order(
            cashier_id=user.id,
            cashier_username=user.username,
            customer_name=data.customer_name,
            total=sum(item.line_total for item in items),
            items=items,
        )
        self._orders.add(order)
        self._audit.record(
            actor=user.username,
            action="venta.registrar",
            target=f"{order.id} total={order.total}",
            ip=ip,
        )
        self._session.commit()
        return order

    @staticmethod
    def _price_item(item: OrderItemIn, menu: Menu) -> OrderItem:
        """Arma un renglón con el nombre y el precio OFICIALES del menú."""
        product = menu.get(item.product_id)
        if product is None:
            raise Unprocessable("Uno de los productos ya no existe en el menú.")
        if not product.is_available:
            raise Unprocessable(f"«{product.name}» está agotado.")
        return OrderItem(
            product_id=product.id,
            product_name=product.name,
            unit_price=product.price,
            quantity=item.quantity,
            line_total=product.price * item.quantity,
        )


class SalesHistory:
    """Consulta de ventas. El administrador ve todas; un cajero, solo las suyas."""

    def __init__(self, session: Session) -> None:
        self._orders = OrderRepository(session)

    def list_orders(self, user: AuthenticatedUser) -> Sequence[Order]:
        return self._orders.list_recent(cashier_id=self._scope(user))

    def summary(self, user: AuthenticatedUser) -> SummaryOut:
        count, revenue = self._orders.totals_since(
            utcnow() - SUMMARY_WINDOW, cashier_id=self._scope(user)
        )
        return SummaryOut(orders_count=count, revenue=revenue)

    @staticmethod
    def _scope(user: AuthenticatedUser) -> uuid.UUID | None:
        return None if user.is_admin else user.id
