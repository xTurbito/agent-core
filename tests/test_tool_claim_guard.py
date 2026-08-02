"""Pruebas del ToolClaimGuardMiddleware: el agente no puede afirmar un hecho
que su tool de respaldo no confirmo en ESTE turno. Sin red real.

Se prueba con un dominio inventado (reservar_mesa) a proposito: el guardian de
core no debe saber nada del negocio de ningun fork.
"""

from langchain.agents.middleware.types import ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from core.guards import ToolClaimGuardMiddleware

NUDGE = "\n\nALERTA DEL SISTEMA: afirmaste una reserva que no existe."


def afirma_reserva(texto: str) -> bool:
    return "quedo reservada" in texto.lower()


def make_guard():
    return ToolClaimGuardMiddleware(
        claim_detector=afirma_reserva,
        tool_name="reservar_mesa",
        success_marker='"status": "confirmada"',
        nudge=NUDGE,
    )


class FakeRequest:
    def __init__(self, messages=None):
        self.system_message = SystemMessage(content="prompt base")
        self.messages = messages or []


def respuesta(texto, tool_calls=None):
    msg = AIMessage(content=texto)
    if tool_calls:
        msg.tool_calls = tool_calls
    return ModelResponse(result=[msg])


# Caso 1: el respaldo solo vale dentro del turno actual
turno_confirmado = [
    HumanMessage(content="si, resérvala"),
    AIMessage(content=""),
    ToolMessage(
        content='{"status": "confirmada", "mesa": 4}',
        name="reservar_mesa",
        tool_call_id="1",
    ),
]
assert make_guard()._respaldada_en_turno(turno_confirmado) is True

turno_viejo = [
    ToolMessage(content='{"status": "confirmada"}', name="reservar_mesa", tool_call_id="1"),
    HumanMessage(content="y que mas tienen?"),  # nuevo turno: lo de antes no cuenta
]
assert make_guard()._respaldada_en_turno(turno_viejo) is False

turno_fallido = [
    HumanMessage(content="si, resérvala"),
    ToolMessage(content='{"status": "sin_cupo"}', name="reservar_mesa", tool_call_id="1"),
]
assert make_guard()._respaldada_en_turno(turno_fallido) is False

otra_tool = [
    HumanMessage(content="si, resérvala"),
    ToolMessage(content='{"status": "confirmada"}', name="consultar_menu", tool_call_id="1"),
]
assert make_guard()._respaldada_en_turno(otra_tool) is False
print("OK: el respaldo solo cuenta si es la tool correcta, exitosa y del turno actual")


# Caso 2: afirmacion sin respaldo -> reintenta con la alerta inyectada
llamadas = {"n": 0}


def handler_mentiroso(request):
    llamadas["n"] += 1
    if llamadas["n"] == 1:
        return respuesta("¡Listo! Tu mesa quedo reservada para el sábado.")
    assert "ALERTA DEL SISTEMA" in request.system_message.content
    return respuesta("", tool_calls=[{"name": "reservar_mesa", "args": {}, "id": "1"}])


request = FakeRequest(messages=[HumanMessage(content="Miguel")])
resultado = make_guard().wrap_model_call(request, handler_mentiroso)
assert llamadas["n"] == 2
assert resultado.result[-1].tool_calls
print("OK: mentira interceptada, el reintento llama la tool")


# Caso 3: afirmacion CON respaldo real pasa sin reintento
llamadas = {"n": 0}


def handler_honesto(request):
    llamadas["n"] += 1
    return respuesta("¡Listo! Tu mesa quedo reservada el sábado a las 12.")


resultado = make_guard().wrap_model_call(FakeRequest(messages=turno_confirmado), handler_honesto)
assert llamadas["n"] == 1
print("OK: afirmacion respaldada pasa directo")


# Caso 4: respuesta normal sin afirmacion no gasta reintentos
llamadas = {"n": 0}


def handler_normal(request):
    llamadas["n"] += 1
    return respuesta("Tenemos mesa a las 10:00 y 11:30. ¿Cuál prefieres?")


make_guard().wrap_model_call(FakeRequest(), handler_normal)
assert llamadas["n"] == 1
print("OK: respuestas normales no gastan reintentos")


# Caso 5: pasada intermedia con tool_calls pendientes no se intercepta
llamadas = {"n": 0}


def handler_con_tools(request):
    llamadas["n"] += 1
    return respuesta(
        "tu mesa quedo reservada",
        tool_calls=[{"name": "reservar_mesa", "args": {}, "id": "1"}],
    )


make_guard().wrap_model_call(FakeRequest(), handler_con_tools)
assert llamadas["n"] == 1
print("OK: pasadas intermedias con tools no se interceptan")

print("\nTodas las pruebas del guardian de claims pasaron.")
