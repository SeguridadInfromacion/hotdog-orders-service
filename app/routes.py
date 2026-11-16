"""Rutas HTTP de ventas."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import AdminUser, ClientIp, CurrentUser, SessionDep
from app.products_client import ProductsGateway, get_products_gateway
from app.repositories import AuditRepository
from app.schemas import AuditOut, OrderIn, OrderOut, SummaryOut
from app.services import SalesHistory, SalesRegister

router = APIRouter(prefix="/api/orders", tags=["orders"])

ProductsDep = Annotated[ProductsGateway, Depends(get_products_gateway)]


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderIn, user: CurrentUser, session: SessionDep, products: ProductsDep, ip: ClientIp
) -> OrderOut:
    order = SalesRegister(session, products).create_order(data, user=user, ip=ip)
    return OrderOut.model_validate(order)


@router.get("", response_model=list[OrderOut])
def list_orders(user: CurrentUser, session: SessionDep) -> list[OrderOut]:
    return [OrderOut.model_validate(order) for order in SalesHistory(session).list_orders(user)]


@router.get("/summary", response_model=SummaryOut)
def summary(user: CurrentUser, session: SessionDep) -> SummaryOut:
    return SalesHistory(session).summary(user)


@router.get("/audit", response_model=list[AuditOut])
def audit_trail(_: AdminUser, session: SessionDep) -> list[AuditOut]:
    return [AuditOut.model_validate(entry) for entry in AuditRepository(session).recent()]
