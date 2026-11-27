"""Arnes de evals: corre casos de varios turnos contra el agente y aplica reglas puras.

El fork arma el agente igual que en produccion y agrega sus propias reglas; aqui
solo vive lo que cualquier fork necesita tal cual. Ver docs/evals.md.
"""

import time
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage

from core.runner import extract_text


@dataclass
class Turno:
    numero: int
    mensaje: str
    tools: list[str]
    final: str
    llamadas_modelo: int = 0
    segundos: float = 0.0
    modelos: list[str] = field(default_factory=list)


@dataclass
class Violacion:
    turno: int
    regla: str
    detalle: str = ""


@dataclass
class Metricas:
    turnos: int = 0
    llamadas_modelo: int = 0
    segundos: float = 0.0
    modelos: dict[str, int] = field(default_factory=dict)  # turnos que contesto cada modelo
    violaciones: list[Violacion] = field(default_factory=list)


Regla = Callable[[list[Turno]], list[Violacion]]


class _ContadorDeLlamadas(BaseCallbackHandler):
    def __init__(self) -> None:
        self.llamadas = 0

    def on_chat_model_start(self, *args, **kwargs) -> None:
        self.llamadas += 1


def correr_caso(agente, mensajes: list[str]) -> list[Turno]:
    """Manda los mensajes en orden, en un hilo nuevo, y registra que paso en cada turno."""
    config = {"configurable": {"thread_id": f"eval-{uuid.uuid4().hex}"}}
    turnos: list[Turno] = []
    for numero, mensaje in enumerate(mensajes, start=1):
        contador = _ContadorDeLlamadas()
        inicio = time.monotonic()
        resultado = agente.invoke(
            {"messages": [("user", mensaje)]}, {**config, "callbacks": [contador]}
        )
        segundos = time.monotonic() - inicio
        msgs = resultado["messages"]
        ultimo_humano = max(
            (k for k, m in enumerate(msgs) if isinstance(m, HumanMessage)), default=-1
        )
        nuevos = msgs[ultimo_humano + 1 :]
        tools = [tc["name"] for m in nuevos for tc in (getattr(m, "tool_calls", None) or [])]
        modelos: list[str] = []
        for m in nuevos:
            nombre = (getattr(m, "response_metadata", None) or {}).get("model_name")
            if isinstance(m, AIMessage) and nombre and nombre not in modelos:
                modelos.append(nombre)
        final = extract_text(nuevos[-1].content).strip() if nuevos else ""
        turnos.append(
            Turno(numero, mensaje, tools, final, contador.llamadas, segundos, modelos)
        )
    return turnos


def evaluar(turnos: list[Turno], reglas: list[Regla]) -> Metricas:
    metricas = Metricas()
    for turno in turnos:
        metricas.turnos += 1
        metricas.llamadas_modelo += turno.llamadas_modelo
        metricas.segundos += turno.segundos
        if turno.modelos:
            contesto = turno.modelos[-1]
            metricas.modelos[contesto] = metricas.modelos.get(contesto, 0) + 1
    for regla in reglas:
        metricas.violaciones.extend(regla(turnos))
    return metricas


def regla_sin_respuesta_vacia(turnos: list[Turno]) -> list[Violacion]:
    return [Violacion(t.numero, "sin_respuesta_vacia") for t in turnos if not t.final.strip()]


def _empieza_con_saludo(texto: str) -> bool:
    palabras = texto.lower().lstrip("¡!¿ ").split()
    return bool(palabras) and palabras[0].strip(",.!") in ("hola", "buenas", "buenos", "buen")


def _emojis(texto: str) -> int:
    return sum(1 for c in texto if unicodedata.category(c) == "So")


def reglas_de_tono(tool_escalar: str | None = None, max_emojis: int = 1) -> list[Regla]:
    """Rubrica de tono que se revisa con codigo; las de escalamiento piden el nombre de la tool."""

    def tono_sin_saludo_a_media(turnos: list[Turno]) -> list[Violacion]:
        return [
            Violacion(t.numero, "tono_sin_saludo_a_media")
            for t in turnos
            if t.numero > 1 and _empieza_con_saludo(t.final)
        ]

    def tono_max_emojis(turnos: list[Turno]) -> list[Violacion]:
        return [
            Violacion(t.numero, "tono_max_emojis", str(_emojis(t.final)))
            for t in turnos
            if _emojis(t.final) > max_emojis
        ]

    def tono_no_pregunta_al_escalar(turnos: list[Turno]) -> list[Violacion]:
        # Al escalar la IA suele pausarse: una pregunta ahi ya no la contesta nadie.
        return [
            Violacion(t.numero, "tono_no_pregunta_al_escalar")
            for t in turnos
            if tool_escalar in t.tools and "?" in t.final
        ]

    def tono_cierra_con_pregunta(turnos: list[Turno]) -> list[Violacion]:
        return [
            Violacion(t.numero, "tono_cierra_con_pregunta")
            for t in turnos
            if t.final.strip() and tool_escalar not in t.tools and "?" not in t.final
        ]

    reglas: list[Regla] = [tono_sin_saludo_a_media, tono_max_emojis]
    if tool_escalar:
        reglas += [tono_no_pregunta_al_escalar, tono_cierra_con_pregunta]
    return reglas


def modelos_para_eval(llm, llm_respaldo, con_respaldo: bool) -> tuple:
    """Con con_respaldo, el respaldo corre solo: un respaldo que nunca se midio no es respaldo."""
    if not con_respaldo:
        return llm, llm_respaldo
    if llm_respaldo is None:
        raise SystemExit(
            "No hay modelo de respaldo: configura LLM_FALLBACK_PROVIDER y LLM_FALLBACK_MODEL."
        )
    return llm_respaldo, None
