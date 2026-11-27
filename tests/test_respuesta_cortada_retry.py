"""Pruebas del reintento de respuestas CORTADAS por limite de tokens.

Un modelo que razona puede gastar casi todo max_tokens pensando y dejar media
frase con finish_reason="length"; sin reintento esa mitad llega al usuario.
Contrato: una respuesta de texto con finish_reason "length" se reintenta con un
nudge, igual que la vacia. Sin red real.

Correr con: .venv/bin/python -m tests.test_respuesta_cortada_retry
"""

from langchain.agents.middleware.types import ModelResponse
from langchain_core.messages import AIMessage, SystemMessage

from core.agent import EmptyResponseRetryMiddleware, _respuesta_cortada


class FakeRequest:
    def __init__(self):
        self.system_message = SystemMessage(content="prompt base")


def respuesta(texto: str, finish_reason: str | None = "stop", tool_calls: list | None = None):
    msg = AIMessage(
        content=texto,
        response_metadata={"finish_reason": finish_reason} if finish_reason else {},
    )
    if tool_calls:
        msg.tool_calls = tool_calls
    return ModelResponse(result=[msg])


# Caso 1: deteccion
assert _respuesta_cortada(respuesta("¡Qué bueno que quieras agendar", "length")) is True
assert _respuesta_cortada(respuesta("Respuesta completa.", "stop")) is False
assert _respuesta_cortada(respuesta("Sin metadata", None)) is False
assert _respuesta_cortada(ModelResponse(result=[])) is False
# Una respuesta con tool_calls es una llamada a tool, no texto para el usuario.
assert _respuesta_cortada(
    respuesta(
        "", "length", tool_calls=[{"name": "consultar_disponibilidad", "args": {}, "id": "1"}]
    )
) is False
print("OK: solo cuenta como cortada una respuesta de texto con finish_reason=length")


def respuesta_con_metadata(texto: str, metadata: dict):
    return ModelResponse(result=[AIMessage(content=texto, response_metadata=metadata)])


# Caso 1b: Gemini y Anthropic avisan el corte con otros valores
assert _respuesta_cortada(respuesta_con_metadata("Media fr", {"finish_reason": "MAX_TOKENS"}))
assert _respuesta_cortada(respuesta_con_metadata("Media fr", {"stop_reason": "max_tokens"}))
assert not _respuesta_cortada(respuesta_con_metadata("Completa.", {"finish_reason": "STOP"}))
assert not _respuesta_cortada(respuesta_con_metadata("Completa.", {"stop_reason": "end_turn"}))
print("OK: el corte se detecta tambien en Gemini (MAX_TOKENS) y Anthropic (max_tokens)")


# Caso 2: respuesta completa pasa directo, una sola llamada
llamadas = {"n": 0}


def handler_ok(request):
    llamadas["n"] += 1
    return respuesta("Respuesta completa.", "stop")


resultado = EmptyResponseRetryMiddleware().wrap_model_call(FakeRequest(), handler_ok)
assert llamadas["n"] == 1
assert resultado.result[-1].content == "Respuesta completa."
print("OK: una respuesta completa no gasta reintentos")


# Caso 3: cortada una vez -> reintenta con nudge y recupera
llamadas = {"n": 0}


def handler_corta_una_vez(request):
    llamadas["n"] += 1
    if llamadas["n"] == 1:
        return respuesta("¡Qué bueno que quieras agendar", "length")
    assert "se corto" in request.system_message.content
    return respuesta("¡Qué bueno que quieras agendar tu visita!", "stop")


resultado = EmptyResponseRetryMiddleware().wrap_model_call(FakeRequest(), handler_corta_una_vez)
assert llamadas["n"] == 2
assert resultado.result[-1].content.endswith("visita!")
print("OK: la respuesta cortada se reintenta con nudge y recupera la completa")


# Caso 4: nudge unico y limite de reintentos; si sigue cortada se rinde sin bucle
llamadas = {"n": 0}


def handler_siempre_corta(request):
    llamadas["n"] += 1
    return respuesta("¡Hola! ✨", "length")


request = FakeRequest()
resultado = EmptyResponseRetryMiddleware(max_retries=2).wrap_model_call(
    request, handler_siempre_corta
)
assert llamadas["n"] == 3  # original + 2 reintentos
assert request.system_message.content.count("se corto") == 1
assert _respuesta_cortada(resultado) is True  # se rinde y regresa lo que hay
print("OK: nudge unico y limite de reintentos respetado")

print("\nTodas las pruebas del reintento de respuesta cortada pasaron.")
