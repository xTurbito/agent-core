"""Pruebas de validacion de session_id en POST /chat (issue #50).

Un session_id vacio o solo espacios se rechaza con 422: dos clientes con ""
compartirian el mismo thread de LangGraph y mezclarian historiales. Los
session_id validos NO se normalizan (no hay strip): hacerlo partiria los
threads de consumidores existentes.
"""

from fastapi.testclient import TestClient

from core.api import create_app
from core.settings import settings


class FakeRunner:
    """Runner falso: registra los session_id recibidos, sin LLM ni BD."""

    def __init__(self) -> None:
        self.session_ids: list[str] = []

    def responder_con_metadata(self, session_id: str, mensaje: str) -> dict:
        self.session_ids.append(session_id)
        return {"text": "ok", "usage_metadata": {}, "response_metadata": {}}


settings.chat_api_key = "test-key"
HEADERS = {"Authorization": "Bearer test-key"}


def _post(runner: FakeRunner, session_id: str):
    client = TestClient(create_app(runner=runner))  # type: ignore[arg-type]
    return client.post(
        "/chat", json={"session_id": session_id, "mensaje": "hola"}, headers=HEADERS
    )


# --- vacios: 422 y el runner nunca se invoca ---

for invalido in ["", "   ", "\t\n"]:
    runner = FakeRunner()
    response = _post(runner, invalido)
    assert response.status_code == 422, (repr(invalido), response.status_code)
    assert runner.session_ids == [], repr(invalido)
print("OK: session_id vacio o solo espacios devuelve 422 sin llamar al runner")


# --- validos: siguen pasando ---

runner = FakeRunner()
response = _post(runner, "abc")
assert response.status_code == 200
assert response.json() == {"respuesta": "ok"}
assert runner.session_ids == ["abc"]
print("OK: 'abc' sigue pasando")


# --- sin normalizar: " abc " llega al runner tal cual ---

runner = FakeRunner()
response = _post(runner, " abc ")
assert response.status_code == 200
assert runner.session_ids == [" abc "]
print("OK: ' abc ' pasa SIN strip (el thread no cambia)")

print("\nTodas las pruebas de session_id pasaron.")
