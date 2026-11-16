# hotdog-orders-service

Servicio de ventas de **PerroCaliente Express**: registra las ventas y consulta
el historial. Para conocer los precios le pregunta a `products-service`; no
tiene acceso a su base de datos.

Python 3.12, FastAPI, SQLAlchemy, httpx, PostgreSQL.
Documentación general: [hotdog-docs](https://github.com/SeguridadInfromacion/hotdog-docs).

## API

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| POST | `/api/orders` | con sesión | Registra una venta |
| GET | `/api/orders` | con sesión | Últimas ventas (un cajero ve solo las suyas) |
| GET | `/api/orders/summary` | con sesión | Cantidad y total de las últimas 24 horas |
| GET | `/api/orders/audit` | admin | Bitácora de este servicio |

Una venta se envía así. No lleva precios:

```json
{
  "customer_name": "Doña Marta",
  "items": [{ "product_id": "…uuid…", "quantity": 2 }]
}
```

## Decisiones de seguridad

- **El servidor pone los precios.** El cliente solo dice qué y cuánto. Cualquier
  campo extra (`unit_price`, `total`) hace que la petición se rechace.
- **Comunicación entre servicios autenticada.** Al consultar a
  `products-service` se reenvía el token del usuario, y ese servicio lo vuelve a verificar.
- **Desconfía de la respuesta ajena.** Lo que responde `products-service` se
  valida antes de usarse; si no cuadra, la venta falla con un 503 limpio.
- **Aislamiento entre cajeros.** El filtro por cajero se aplica en el servidor
  con el id del token.
- **Ventas inmutables frente al menú.** Cada renglón guarda nombre y precio del
  momento de la venta.
- **Todo o nada.** Si un producto falla, no se guarda nada de la venta.
- **Auditoría** de cada venta, con cajero e IP.

## Estructura

```
app/
  main.py             arranque, manejo de errores
  routes.py           HTTP -> casos de uso
  services.py         casos de uso
  products_client.py  cliente HTTP hacia products-service
  repositories.py     acceso a datos
  models.py           tablas
  schemas.py          contratos de entrada y salida
  security.py         verificación de tokens
  dependencies.py     sesión, usuario actual, roles, anti-CSRF
  config.py           variables de entorno
tests/                products-service se reemplaza por un doble en memoria
```

## Desarrollo

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

pytest              # pruebas (SQLite en memoria, sin red ni Docker)
ruff check .
bandit -r app
pip-audit -r requirements.txt
```

Para ejecutarlo junto al resto del sistema, usa
[hotdog-infra](https://github.com/SeguridadInfromacion/hotdog-infra).

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `DATABASE_URL` | sí | Conexión a PostgreSQL |
| `JWT_PUBLIC_KEY_FILE` | sí | Ruta a la llave pública RSA (PEM) |
| `PRODUCTS_SERVICE_URL` | sí | Dirección interna de `products-service` |
| `PRODUCTS_TIMEOUT_SECONDS` | no (3) | Tiempo máximo de espera al consultar el menú |
| `ENABLE_DOCS` | no (false) | Activa `/docs` (solo para desarrollo) |
