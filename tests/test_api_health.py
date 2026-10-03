"""Pruebas del healthcheck de core/api.py: debe reportar el estado real de
Postgres, no un "ok" fijo sin verificar nada.
"""

from fastapi.testclient import TestClient

from core.api import create_app
from core.settings import settings


def _client() -> TestClient:
    app = create_app(runner=None)  # /health no toca el runner
    return TestClient(app)


# --- sin Postgres configurado: no debe fallar, solo reportarlo ---

original_url = settings.postgres_url
settings.postgres_url = None

response = _client().get("/health")
assert response.status_code == 200
body = response.json()
assert body["status"] == "ok"
assert body["checks"]["postgres"] == "not configured"
print("OK: sin POSTGRES_URL configurado, /health sigue sano")


# --- Postgres configurado pero inalcanzable: debe degradarse a 503 ---

settings.postgres_url = "postgresql://postgres@127.0.0.1:1/no_existe"

response = _client().get("/health")
assert response.status_code == 503
body = response.json()
assert body["status"] == "degraded"
assert body["checks"]["postgres"] == "unreachable"
print("OK: Postgres inalcanzable degrada /health a 503, sin filtrar el detalle del error")


# --- Postgres configurado y alcanzable: debe reportar ok (soft-skip si no hay uno local) ---

import psycopg  # noqa: E402

try:
    psycopg.connect("postgresql://postgres@127.0.0.1:5432/postgres", connect_timeout=2).close()
    hay_postgres_local = True
except psycopg.OperationalError:
    hay_postgres_local = False

if hay_postgres_local:
    settings.postgres_url = "postgresql://postgres@127.0.0.1:5432/postgres"

    response = _client().get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["postgres"] == "ok"
    print("OK: Postgres alcanzable, /health reporta ok")
else:
    print("SALTADO: no hay Postgres local en 127.0.0.1:5432 para probar el caso 'alcanzable'")


settings.postgres_url = original_url

print("\nTodas las pruebas del healthcheck pasaron.")
