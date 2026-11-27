"""Arnes de evals: corre casos de varios turnos y aplica reglas puras.

Contrato:
1. correr_caso captura por turno las tools, el texto final, las llamadas al modelo
   y que modelo contesto; cada caso va en su propio hilo.
2. evaluar aplica las reglas que le pases y suma metricas por modelo.
3. Reglas base: respuesta vacia y rubrica de tono.
4. modelos_para_eval permite correr con el respaldo como principal.
Sin red real ni LLM.
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from core.evals import (
    Turno,
    correr_caso,
    evaluar,
    modelos_para_eval,
    regla_sin_respuesta_vacia,
    reglas_de_tono,
)


class FakeAgente:
    """Imita create_agent: guarda el hilo y avisa al callback cada llamada al modelo."""

    def __init__(self, guion):
        self.guion = guion  # por turno: (tools, texto_final, modelo)
        self.hilos = {}
        self.threads_vistos = []

    def invoke(self, entrada, config):
        thread_id = config["configurable"]["thread_id"]
        self.threads_vistos.append(thread_id)
        historial = self.hilos.setdefault(thread_id, [])
        _, texto_usuario = entrada["messages"][0]
        historial.append(HumanMessage(content=texto_usuario))
        tools, final, modelo = self.guion.pop(0)
        contador = config["callbacks"][0]
        for i, nombre in enumerate(tools):
            contador.on_chat_model_start({}, [])
            historial.append(
                AIMessage(content="", tool_calls=[{"name": nombre, "args": {}, "id": f"c{i}"}])
            )
            historial.append(
                ToolMessage(content='{"status": "ok"}', name=nombre, tool_call_id=f"c{i}")
            )
        contador.on_chat_model_start({}, [])
        historial.append(AIMessage(content=final, response_metadata={"model_name": modelo}))
        return {"messages": list(historial)}


# --- 1. correr_caso captura lo que paso en cada turno ---

agente = FakeAgente(
    [
        (["consultar_disponibilidad"], "Tengo el martes a las 10, ¿te queda?", "primario"),
        ([], [{"type": "text", "text": "Listo, te espero."}], "respaldo"),
    ]
)
turnos = correr_caso(agente, ["¿Tienen el martes?", "Sí, a las 10"])
assert [t.numero for t in turnos] == [1, 2]
assert turnos[0].mensaje == "¿Tienen el martes?"
assert turnos[0].tools == ["consultar_disponibilidad"]
assert turnos[0].final == "Tengo el martes a las 10, ¿te queda?"
assert turnos[0].llamadas_modelo == 2
assert turnos[0].modelos == ["primario"]
assert turnos[1].tools == [] and turnos[1].llamadas_modelo == 1
assert turnos[1].final == "Listo, te espero.", "el contenido en bloques se extrae como texto"
assert turnos[1].modelos == ["respaldo"]
assert len(set(agente.threads_vistos)) == 1, "los turnos de un caso comparten hilo"
print("OK: correr_caso captura tools, texto final, llamadas y modelo por turno")

otro = FakeAgente([([], "Hola, ¿en que te ayudo?", "primario")])
correr_caso(otro, ["Hola"])
assert otro.threads_vistos[0] != agente.threads_vistos[0], "cada caso va en un hilo nuevo"
print("OK: cada caso corre en su propio hilo")

# --- 2. evaluar aplica las reglas y suma metricas por modelo ---

metricas = evaluar(turnos, [regla_sin_respuesta_vacia])
assert metricas.turnos == 2
assert metricas.llamadas_modelo == 3
assert metricas.modelos == {"primario": 1, "respaldo": 1}
assert metricas.violaciones == []
print("OK: evaluar suma turnos, llamadas y que modelo contesto cada turno")


def turno(numero, final, tools=()):
    return Turno(numero=numero, mensaje="x", tools=list(tools), final=final)


vacia = evaluar([turno(1, "  ")], [regla_sin_respuesta_vacia])
assert [v.regla for v in vacia.violaciones] == ["sin_respuesta_vacia"]
print("OK: un turno sin texto para el usuario es una violacion")

# --- 3. rubrica de tono ---

tono = reglas_de_tono(tool_escalar="escalar_a_humano")
casos_malos = [
    turno(1, "Hola, ¿que servicio te interesa?"),
    turno(2, "Hola de nuevo, ¿algo mas?"),  # saluda a media conversacion
    turno(3, "Genial 😀😀, ¿te aparto?"),  # dos emojis
    turno(4, "Te paso con alguien del equipo, ¿te parece?", ["escalar_a_humano"]),
    turno(5, "Perfecto, gracias."),  # no escala y no deja siguiente paso
]
reglas = sorted((v.turno, v.regla) for v in evaluar(casos_malos, tono).violaciones)
assert reglas == [
    (2, "tono_sin_saludo_a_media"),
    (3, "tono_max_emojis"),
    (4, "tono_no_pregunta_al_escalar"),
    (5, "tono_cierra_con_pregunta"),
], reglas
print("OK: la rubrica marca saludo a media, emojis, pregunta al escalar y cierre sin pregunta")

casos_buenos = [
    turno(1, "Hola, ¿que servicio te interesa?"),
    turno(2, "Te paso con alguien del equipo para confirmarlo.", ["escalar_a_humano"]),
]
assert evaluar(casos_buenos, tono).violaciones == []
sin_escalar = reglas_de_tono()
assert [r.__name__ for r in sin_escalar] == ["tono_sin_saludo_a_media", "tono_max_emojis"]
print("OK: sin tool de escalamiento solo aplican las reglas que no la necesitan")

# --- 4. correr con el respaldo como principal ---

assert modelos_para_eval("p", "r", con_respaldo=False) == ("p", "r")
assert modelos_para_eval("p", "r", con_respaldo=True) == ("r", None)
try:
    modelos_para_eval("p", None, con_respaldo=True)
except SystemExit as exc:
    assert "LLM_FALLBACK" in str(exc)
else:
    raise AssertionError("pedir el respaldo sin tenerlo configurado debe cortar")
print("OK: --con-respaldo corre los casos con el respaldo como unico modelo")

# --- 5. build_runner sigue armando lo mismo que antes ---

import app.bootstrap as bootstrap  # noqa: E402
import scripts.evals.correr as correr  # noqa: E402

capturado = {}
originales = (bootstrap.construir_llms, bootstrap.make_checkpointer, bootstrap.build_agent)
bootstrap.construir_llms = lambda: ("llm-p", "llm-r")
bootstrap.make_checkpointer = lambda kind: f"checkpointer-{kind}"
bootstrap.build_agent = lambda llm, tools, prompt, **kw: capturado.update(llm=llm, **kw) or "agente"
try:
    runner = bootstrap.build_runner()
finally:
    bootstrap.construir_llms, bootstrap.make_checkpointer, bootstrap.build_agent = originales
assert runner._agent == "agente"
assert capturado["llm"] == "llm-p" and capturado["llm_respaldo"] == "llm-r"
assert capturado["checkpointer"] == f"checkpointer-{bootstrap.settings.memory_kind}"
assert capturado["context_provider"] is bootstrap.build_business_context
print("OK: build_runner arma el agente igual que antes (modelos, checkpointer y contexto)")

# --- 6. el runner usa el armado del fork y la salida refleja las violaciones ---

armados = []
originales = (correr.construir_llms, correr.armar_agente, correr.CASOS)
correr.construir_llms = lambda: ("llm-p", "llm-r")
correr.CASOS = {"vacio": ["Hola"], "bueno": ["Hola"]}


def armar_falso(checkpointer, llm, llm_respaldo):
    armados.append((type(checkpointer).__name__, llm, llm_respaldo))
    return FakeAgente([([], "" if not armados[1:] else "x", "m")] * 5)


correr.armar_agente = armar_falso
try:
    assert correr.main(["vacio"]) == 1, "una violacion hace salir con 1"
    assert correr.main(["bueno", "--con-respaldo"]) == 0
    try:
        correr.main(["no-existe"])
    except SystemExit as exc:
        assert "Hay: vacio, bueno" in str(exc)
    else:
        raise AssertionError("un caso desconocido debe cortar con la lista de casos")
finally:
    correr.construir_llms, correr.armar_agente, correr.CASOS = originales
assert armados[0] == ("InMemorySaver", "llm-p", "llm-r"), armados[0]
assert armados[1][1:] == ("llm-r", None), "con --con-respaldo el respaldo corre solo"
print("OK: el runner arma el agente del fork en memoria, respeta --con-respaldo y sale con 1")

# --- 7. con el agente real de LangChain (modelo falso, sin red) ---

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402

from core.agent import build_agent  # noqa: E402
from core.memory import make_checkpointer  # noqa: E402


class ModeloFalso(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


respuestas = iter(
    [
        AIMessage(content="Hola, ¿en que te ayudo?", response_metadata={"model_name": "falso"}),
        AIMessage(content="Claro, ¿que dia?", response_metadata={"model_name": "falso"}),
    ]
)
real = build_agent(ModeloFalso(messages=respuestas), [], "prompt", checkpointer=make_checkpointer())
turnos = correr_caso(real, ["Hola", "Quiero una cita"])
assert [t.final for t in turnos] == ["Hola, ¿en que te ayudo?", "Claro, ¿que dia?"]
assert [t.llamadas_modelo for t in turnos] == [1, 1]
assert evaluar(turnos, []).modelos == {"falso": 2}
print("OK: con build_agent real cuenta las llamadas y lee el modelo de cada turno")


class PrimarioSinSaldo(ModeloFalso):
    def _generate(self, *args, **kwargs):
        raise RuntimeError("402: sin saldo")


respaldo_ok = ModeloFalso(
    messages=iter(
        [AIMessage(content="Claro, ¿que dia?", response_metadata={"model_name": "resp"})]
    )
)
con_caida = build_agent(
    PrimarioSinSaldo(messages=iter([])),
    [],
    "prompt",
    checkpointer=make_checkpointer(),
    llm_respaldo=respaldo_ok,
)
turno_caido = correr_caso(con_caida, ["Quiero una cita"])[0]
assert turno_caido.final == "Claro, ¿que dia?" and turno_caido.contesto == "resp"
assert turno_caido.llamadas_modelo == 2, "cuenta el intento del primario y el del respaldo"
print("OK: si el primario se cae, el arnes muestra que contesto el respaldo")

# --- 8. hallazgos de la revision ---


class AgenteMezclado:
    """Turno mixto: el primario llama una tool, el respaldo otra y el primario cierra."""

    def __init__(self, error_en=None):
        self.error_en = error_en
        self.vistos = 0

    def invoke(self, entrada, config):
        self.vistos += 1
        if self.error_en == self.vistos:
            raise RuntimeError("primario y respaldo caidos")
        return {
            "messages": [
                HumanMessage(content=entrada["messages"][0][1]),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "t", "args": {}, "id": "1"}],
                    response_metadata={"model_name": "primario"},
                ),
                ToolMessage(content="{}", name="t", tool_call_id="1"),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "t", "args": {}, "id": "2"}],
                    response_metadata={"model_name": "respaldo"},
                ),
                ToolMessage(content="{}", name="t", tool_call_id="2"),
                AIMessage(
                    content="Listo, ¿algo mas?", response_metadata={"model_name": "primario"}
                ),
            ]
        }


mezclado = correr_caso(AgenteMezclado(), ["hola"])
assert mezclado[0].modelos == ["primario", "respaldo"]
assert mezclado[0].contesto == "primario"
assert evaluar(mezclado, []).modelos == {"primario": 1}
print("OK: 'contesto' es el modelo del mensaje final, no el ultimo que aparecio")

con_error = correr_caso(AgenteMezclado(error_en=2), ["uno", "dos", "tres"])
assert [t.numero for t in con_error] == [1, 2], "el caso se corta en el turno que fallo"
assert con_error[1].final == "" and "primario y respaldo caidos" in con_error[1].error
fallas = evaluar(con_error, [regla_sin_respuesta_vacia]).violaciones
assert [(v.turno, v.regla) for v in fallas] == [(2, "sin_respuesta_vacia")]
assert "caidos" in fallas[0].detalle
print("OK: un error del modelo queda como violacion del turno y no tumba la corrida")

emoji = reglas_de_tono(max_emojis=1)[1]
assert emoji([turno(2, "Te esperamos 🇲🇽")]) == [], "una bandera es un emoji"
assert emoji([turno(2, "Familia 👨‍👩‍👧")]) == [], "una secuencia ZWJ es un emoji"
assert emoji([turno(2, "Hace 25°C © ™")]) == [], "simbolos de texto no son emojis"
assert emoji([turno(2, "Opcion 1️⃣ o 2️⃣")]) != [], "los keycaps cuentan"
print("OK: el conteo de emojis trata banderas, ZWJ y keycaps como uno y no cuenta simbolos")

saludo = reglas_de_tono()[0]
assert saludo([turno(2, "Buenas noticias: hay espacio el martes")]) == []
assert saludo([turno(2, "Buenas tardes, ¿te ayudo?")]) != []
assert saludo([turno(2, "👋 Hola otra vez")]) != []
print("OK: 'Buenas noticias' no es saludo; 'Buenas tardes' y '👋 Hola' si")

con_url = reglas_de_tono(tool_escalar="escalar")
url_al_escalar = turno(3, "Te paso con el equipo: https://x.test/p?id=1", ["escalar"])
url_sin_pregunta = turno(4, "Aqui esta el link https://x.test/p?id=1")
violaciones_url = evaluar([url_al_escalar, url_sin_pregunta], con_url).violaciones
reglas_url = sorted(v.regla for v in violaciones_url)
assert reglas_url == ["tono_cierra_con_pregunta"], reglas_url
print("OK: el ? de una URL no cuenta como pregunta")

try:
    correr.main(["saludo", "0"])
except SystemExit as exc:
    assert exc.code != 0
else:
    raise AssertionError("corridas=0 debe rechazarse")
print("OK: corridas tiene que ser mayor que 0")

print("\nTodas las pruebas del arnes de evals pasaron.")
