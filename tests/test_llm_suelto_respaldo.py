"""Las llamadas sueltas al LLM (fuera del agente) tambien usan el modelo de respaldo.

Contrato:
1. Si el primario truena o regresa texto vacio, la llamada se repite UNA vez con el respaldo.
2. Si el primario contesta, el respaldo no se toca.
3. Sin respaldo configurado, el error del primario se propaga como antes.
4. El resumen para el asesor humano usa ese mismo camino.
Sin red real.
"""

from langchain_core.messages import AIMessage, HumanMessage

import app.business.summarizer as summarizer
from core.llm import invocar_con_respaldo


class FakeLLM:
    def __init__(self, respuesta=None, error=None):
        self.respuesta = respuesta
        self.error = error
        self.entradas = []

    def invoke(self, entrada):
        self.entradas.append(entrada)
        if self.error is not None:
            raise self.error
        return AIMessage(content=self.respuesta)


# --- 1. el respaldo contesta lo que el primario no pudo ---

primario = FakeLLM(error=RuntimeError("402: sin saldo"))
respaldo = FakeLLM(respuesta="texto del respaldo")
resultado = invocar_con_respaldo("hola", primario, respaldo)
assert resultado.content == "texto del respaldo"
assert primario.entradas == ["hola"] and respaldo.entradas == ["hola"]
print("OK: si el primario truena, contesta el respaldo con la misma entrada")

primario = FakeLLM(respuesta="   ")
respaldo = FakeLLM(respuesta="texto del respaldo")
resultado = invocar_con_respaldo("hola", primario, respaldo)
assert resultado.content == "texto del respaldo"
assert len(respaldo.entradas) == 1
print("OK: si el primario regresa vacio, contesta el respaldo")

# --- 2. el respaldo no se toca si el primario contesta ---

primario = FakeLLM(respuesta="texto del primario")
respaldo = FakeLLM(respuesta="texto del respaldo")
resultado = invocar_con_respaldo("hola", primario, respaldo)
assert resultado.content == "texto del primario"
assert respaldo.entradas == []
print("OK: con primario sano el respaldo no se llama")

# --- 3. sin respaldo se conserva el comportamiento previo ---

primario = FakeLLM(error=RuntimeError("402: sin saldo"))
try:
    invocar_con_respaldo("hola", primario, None)
except RuntimeError as exc:
    assert "402" in str(exc)
else:
    raise AssertionError("sin respaldo el error del primario debe propagarse")

primario = FakeLLM(respuesta="")
assert invocar_con_respaldo("hola", primario, None).content == ""
print("OK: sin respaldo el error o el vacio del primario salen igual que antes")

# --- 4. el resumen para el asesor usa el respaldo ---


class FakeRunner:
    def get_conversation_messages(self, session_id):
        return [HumanMessage(content="quiero una cita"), AIMessage(content="claro, que dia?")]


primario = FakeLLM(error=RuntimeError("402: sin saldo"))
respaldo = FakeLLM(respuesta="Quiere una cita; falta el dia.")
original = summarizer.construir_llms
summarizer.construir_llms = lambda: (primario, respaldo)
try:
    resumen = summarizer.summarize_conversation(FakeRunner(), "s-1")
finally:
    summarizer.construir_llms = original
assert resumen == "Quiere una cita; falta el dia."
assert "Cliente: quiero una cita" in respaldo.entradas[0]
print("OK: el resumen para el asesor sale aunque el primario este caido")

print("\nTodas las pruebas de llamadas sueltas con respaldo pasaron.")
