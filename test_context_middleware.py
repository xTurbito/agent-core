"""Prueba aislada del middleware de contexto: sin LLM real, sin Postgres.

Verifica que ContextInjectionMiddleware agrega el contexto de negocio al
system_message antes de llamar al modelo, y que no hace nada si el
context_provider no devuelve contexto.
"""

from unittest.mock import patch

from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, SystemMessage

from core.agent import ContextInjectionMiddleware

BASE_PROMPT = "Eres el asistente de una clinica dental."


def make_request(system_prompt: str = BASE_PROMPT) -> ModelRequest:
    return ModelRequest(
        model=None,
        messages=[],
        system_message=SystemMessage(content=system_prompt),
    )


def fake_handler(request: ModelRequest) -> ModelResponse:
    fake_handler.last_request = request
    return ModelResponse(result=[AIMessage(content="ok")])


# Caso 1: el context_provider devuelve contexto -> se agrega al system_message
middleware = ContextInjectionMiddleware(context_provider=lambda session_id: "Nombre: Juan.")

with patch("core.agent.get_config", return_value={"configurable": {"thread_id": "sesion-1"}}):
    middleware.wrap_model_call(make_request(), fake_handler)

final_prompt = fake_handler.last_request.system_message.content
assert BASE_PROMPT in final_prompt, "el prompt base debe seguir presente"
assert "Nombre: Juan." in final_prompt, "el contexto debe inyectarse"
print("OK: contexto inyectado ->", repr(final_prompt))


# Caso 2: el context_provider devuelve None -> el system_message no cambia
middleware_sin_contexto = ContextInjectionMiddleware(context_provider=lambda session_id: None)

with patch("core.agent.get_config", return_value={"configurable": {"thread_id": "sesion-2"}}):
    middleware_sin_contexto.wrap_model_call(make_request(), fake_handler)

final_prompt_sin_contexto = fake_handler.last_request.system_message.content
assert final_prompt_sin_contexto == BASE_PROMPT, "sin contexto, el prompt no debe modificarse"
print("OK: sin contexto, prompt sin cambios ->", repr(final_prompt_sin_contexto))


# Caso 3: session_id correcto llega al context_provider (via get_config -> thread_id)
seen_session_ids = []
middleware_captura = ContextInjectionMiddleware(
    context_provider=lambda session_id: seen_session_ids.append(session_id) or None
)

with patch("core.agent.get_config", return_value={"configurable": {"thread_id": "sesion-3"}}):
    middleware_captura.wrap_model_call(make_request(), fake_handler)

assert seen_session_ids == ["sesion-3"], "el thread_id debe llegar como session_id"
print("OK: session_id propagado ->", seen_session_ids)

print("\nTodas las pruebas del middleware de contexto pasaron.")
