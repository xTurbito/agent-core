"""Pruebas del EmptyResponseRetryMiddleware: reintenta respuestas vacias del
modelo antes de que se persistan, sin tocar las validas. Sin red real."""

from langchain.agents.middleware.types import ModelResponse
from langchain_core.messages import AIMessage, SystemMessage

from core.agent import EmptyResponseRetryMiddleware, _respuesta_vacia


class FakeRequest:
    def __init__(self):
        self.system_message = SystemMessage(content="prompt base")


def respuesta(texto: str = "", tool_calls: list | None = None) -> ModelResponse:
    msg = AIMessage(content=texto)
    if tool_calls:
        msg.tool_calls = tool_calls
    return ModelResponse(result=[msg])


# Caso 1: deteccion de vacio
assert _respuesta_vacia(respuesta("")) is True
assert _respuesta_vacia(respuesta("   ")) is True
assert _respuesta_vacia(ModelResponse(result=[])) is True
assert _respuesta_vacia(respuesta("hola")) is False
assert _respuesta_vacia(
    respuesta("", tool_calls=[{"name": "listar_categorias", "args": {}, "id": "1"}])
) is False
print("OK: detecta vacio real; texto o tool_calls no cuentan como vacio")


# Caso 2: respuesta valida pasa directo, una sola llamada al modelo
llamadas = {"n": 0}


def handler_ok(request):
    llamadas["n"] += 1
    return respuesta("respuesta normal")


mw = EmptyResponseRetryMiddleware()
resultado = mw.wrap_model_call(FakeRequest(), handler_ok)
assert llamadas["n"] == 1
assert resultado.result[-1].content == "respuesta normal"
print("OK: respuesta valida no gasta reintentos")


# Caso 3: vacio una vez -> reintenta con nudge y recupera
llamadas = {"n": 0}


def handler_flaky(request):
    llamadas["n"] += 1
    if llamadas["n"] == 1:
        return respuesta("")
    assert "salio vacia" in request.system_message.content
    return respuesta("ahora si contesto")


request = FakeRequest()
mw = EmptyResponseRetryMiddleware()
resultado = mw.wrap_model_call(request, handler_flaky)
assert llamadas["n"] == 2
assert resultado.result[-1].content == "ahora si contesto"
print("OK: vacio se reintenta con nudge en el system prompt")


# Caso 4: el nudge se agrega UNA sola vez aunque haya 2 reintentos
llamadas = {"n": 0}


def handler_siempre_vacio(request):
    llamadas["n"] += 1
    return respuesta("")


request = FakeRequest()
mw = EmptyResponseRetryMiddleware(max_retries=2)
resultado = mw.wrap_model_call(request, handler_siempre_vacio)
assert llamadas["n"] == 3  # original + 2 reintentos
assert request.system_message.content.count("salio vacia") == 1
assert _respuesta_vacia(resultado) is True  # se rinde y regresa lo que hay
print("OK: nudge unico y limite de reintentos respetado")

print("\nTodas las pruebas del retry de respuesta vacia pasaron.")
