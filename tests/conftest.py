"""Entorno de pruebas: llaves RSA temporales, SQLite en memoria y un menú falso.

El servicio de productos se reemplaza por un doble en memoria: así se prueba
orders-service aislado, sin red.
"""

import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_PEM = _key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
)
_public_path = Path(tempfile.mkdtemp(prefix="hotdog-keys-")) / "public.pem"
_public_path.write_bytes(
    _key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
)
os.environ.update(
    DATABASE_URL="sqlite+pysqlite:///:memory:",
    JWT_PUBLIC_KEY_FILE=str(_public_path),
    PRODUCTS_SERVICE_URL="http://products.invalid",
)

# Los imports de la app van después de preparar el entorno.
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, get_engine  # noqa: E402
from app.errors import ServiceUnavailable  # noqa: E402
from app.main import create_app  # noqa: E402
from app.products_client import ProductInfo, get_products_gateway  # noqa: E402

CSRF_HEADER = {"X-Requested-With": "XMLHttpRequest"}


class FakeMenu:
    """Doble de products-service."""

    def __init__(self) -> None:
        self.products: dict[uuid.UUID, ProductInfo] = {}
        self.is_down = False
        self.tokens_seen: list[str] = []

    def add(self, name: str, price: int, *, is_available: bool = True) -> str:
        product = ProductInfo(id=uuid.uuid4(), name=name, price=price, is_available=is_available)
        self.products[product.id] = product
        return str(product.id)

    def get_product(self, product_id: uuid.UUID, token: str) -> ProductInfo | None:
        self.tokens_seen.append(token)
        if self.is_down:
            raise ServiceUnavailable("El menú no está disponible.")
        return self.products.get(product_id)


def make_token(role: str, username: str, user_id: uuid.UUID | None = None) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id or uuid.uuid4()),
        "username": username,
        "role": role,
        "iss": "hotdog-auth",
        "aud": "hotdog-api",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(claims, PRIVATE_PEM, algorithm="RS256")


@pytest.fixture(autouse=True)
def _fresh_database():
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    yield


@pytest.fixture
def menu() -> FakeMenu:
    return FakeMenu()


@pytest.fixture
def make_client(menu):
    def _make(token: str | None) -> TestClient:
        app = create_app()
        app.dependency_overrides[get_products_gateway] = lambda: menu
        client = TestClient(app, base_url="https://testserver", headers=CSRF_HEADER)
        if token:
            client.cookies.set("access_token", token)
        return client

    return _make


@pytest.fixture
def anonymous_client(make_client):
    return make_client(None)


@pytest.fixture
def admin_client(make_client):
    return make_client(make_token("admin", "admin"))


@pytest.fixture
def cashier_client(make_client):
    return make_client(make_token("cashier", "cajero"))


@pytest.fixture
def other_cashier_client(make_client):
    return make_client(make_token("cashier", "lucia"))
