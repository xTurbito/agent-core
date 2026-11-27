"""Arnes de evals: corre casos de varios turnos contra el agente y aplica reglas puras.

El fork arma el agente igual que en produccion y agrega sus propias reglas; aqui
solo vive lo que cualquier fork necesita tal cual. Ver docs/evals.md.
"""

import re
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
    modelos: list[str] = field(default_factory=list)  # en orden de aparicion, sin repetir
    contesto: str | None = None  # modelo del mensaje final
    error: str = ""  # la excepcion si el turno no termino


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
    """Manda los mensajes en orden, en un hilo nuevo; si un turno truena, el caso para ahi."""
    config = {"configurable": {"thread_id": f"eval-{uuid.uuid4().hex}"}}
    turnos: list[Turno] = []
    for numero, mensaje in enumerate(mensajes, start=1):
        contador = _ContadorDeLlamadas()
        inicio = time.monotonic()
        try:
            resultado = agente.invoke(
                {"messages": [("user", mensaje)]}, {**config, "callbacks": [contador]}
            )
        except Exception as exc:
            segundos = time.monotonic() - inicio
            turnos.append(
                Turno(numero, mensaje, [], "", contador.llamadas, segundos, error=repr(exc))
            )
            break
        segundos = time.monotonic() - inicio
        msgs = resultado["messages"]
        ultimo_humano = max(
            (k for k, m in enumerate(msgs) if isinstance(m, HumanMessage)), default=-1
        )
        nuevos = msgs[ultimo_humano + 1 :]
        tools = [tc["name"] for m in nuevos for tc in (getattr(m, "tool_calls", None) or [])]
        modelos: list[str] = []
        contesto = None
        for m in nuevos:
            nombre = (getattr(m, "response_metadata", None) or {}).get("model_name")
            if isinstance(m, AIMessage) and nombre:
                contesto = nombre
                if nombre not in modelos:
                    modelos.append(nombre)
        final = extract_text(nuevos[-1].content).strip() if nuevos else ""
        turnos.append(
            Turno(numero, mensaje, tools, final, contador.llamadas, segundos, modelos, contesto)
        )
    return turnos


def evaluar(turnos: list[Turno], reglas: list[Regla]) -> Metricas:
    metricas = Metricas()
    for turno in turnos:
        metricas.turnos += 1
        metricas.llamadas_modelo += turno.llamadas_modelo
        metricas.segundos += turno.segundos
        if turno.contesto:
            metricas.modelos[turno.contesto] = metricas.modelos.get(turno.contesto, 0) + 1
    for regla in reglas:
        metricas.violaciones.extend(regla(turnos))
    return metricas


def regla_sin_respuesta_vacia(turnos: list[Turno]) -> list[Violacion]:
    return [
        Violacion(t.numero, "sin_respuesta_vacia", t.error) for t in turnos if not t.final.strip()
    ]


_SALUDO = re.compile(r"^\W*(hola\b|(buen[oa]s?)\s+(dias|días|tardes|noches)\b)", re.IGNORECASE)
_URL = re.compile(r"https?://\S+")
_TONO_DE_PIEL = range(0x1F3FB, 0x1F400)
_INDICADOR_REGIONAL = range(0x1F1E6, 0x1F200)


def _empieza_con_saludo(texto: str) -> bool:
    return bool(_SALUDO.match(texto))


def _es_pictograma(c: str) -> bool:
    cp = ord(c)
    return unicodedata.category(c) == "So" and (cp >= 0x1F000 or 0x2600 <= cp <= 0x27BF)


def _emojis(texto: str) -> int:
    """Cuenta emojis como se ven: una bandera, una secuencia ZWJ o un keycap valen uno."""
    total = 0
    tras_zwj = False
    indicadores = 0
    for c in texto:
        cp = ord(c)
        if c == "\u200d":
            tras_zwj = True
            continue
        if cp in _INDICADOR_REGIONAL:
            indicadores += 1
            total += indicadores % 2  # dos indicadores forman una bandera
        elif c == "\u20e3" or (_es_pictograma(c) and cp not in _TONO_DE_PIEL and not tras_zwj):
            total += 1
        if cp not in _INDICADOR_REGIONAL:
            indicadores = 0
        tras_zwj = False
    return total


def _pregunta(texto: str) -> bool:
    return "?" in _URL.sub("", texto)


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
            if tool_escalar in t.tools and _pregunta(t.final)
        ]

    def tono_cierra_con_pregunta(turnos: list[Turno]) -> list[Violacion]:
        return [
            Violacion(t.numero, "tono_cierra_con_pregunta")
            for t in turnos
            if t.final.strip() and tool_escalar not in t.tools and not _pregunta(t.final)
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
