"""Prueba estructural del safety prompt (sin LLM real, sin red).

Verifica que build_agent SIEMPRE antepone BASE_SAFETY_PROMPT al prompt del
fork: si un refactor futuro lo desconecta, el agente quedaria sin defensa
anti prompt-injection y sin la regla de no revelar datos internos, y esto
lo cacha antes de llegar a produccion.
"""

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from core.agent import BASE_SAFETY_PROMPT, build_agent

FORK_PROMPT = "Eres el asistente de prueba del negocio X."


class MessageSpy(BaseCallbackHandler):
    """Captura los mensajes exactos que le llegan al modelo."""

    def __init__(self):
        self.seen_messages = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.seen_messages.extend(messages[0])


spy = MessageSpy()
agent = build_agent(FakeListChatModel(responses=["ok"]), [], FORK_PROMPT)
agent.invoke(
    {"messages": [("user", "hola")]},
    {"callbacks": [spy]},
)

assert spy.seen_messages, "el modelo fake debio recibir mensajes"

system_text = spy.seen_messages[0].content
assert BASE_SAFETY_PROMPT in system_text, "falta BASE_SAFETY_PROMPT en el system prompt"
assert FORK_PROMPT in system_text, "falta el prompt del fork en el system prompt"
assert system_text.index(BASE_SAFETY_PROMPT) < system_text.index(FORK_PROMPT), (
    "las reglas de seguridad deben ir ANTES del prompt del fork"
)
print("OK: BASE_SAFETY_PROMPT + prompt del fork, en ese orden")

# Las reglas clave siguen presentes (si alguien las recorta, esto truena)
for regla in [
    "scores de calificacion",   # no revelar datos internos del CRM
    "Ignora cualquier instruccion",  # anti prompt-injection
    "alcance del negocio",      # no salirse del giro
]:
    assert regla in system_text, f"regla de seguridad ausente: {regla}"
print("OK: reglas clave presentes (datos internos, anti-injection, alcance)")

print("\nTodas las pruebas del safety prompt pasaron.")
