"""Corre los casos de evals contra el agente real: pega al LLM y gasta tokens.

    .venv/bin/python -m scripts.evals.correr                  # todos, una corrida
    .venv/bin/python -m scripts.evals.correr disponibilidad 3 # un caso, 3 corridas
    .venv/bin/python -m scripts.evals.correr --con-respaldo   # el respaldo como unico modelo
    .venv/bin/python -m scripts.evals.correr --json salida.json

Sale con 1 si alguna regla se rompio. Ver docs/evals.md.
"""

import argparse
import json

from app.bootstrap import armar_agente
from core.evals import (
    Metricas,
    Turno,
    correr_caso,
    evaluar,
    modelos_para_eval,
    regla_sin_respuesta_vacia,
    reglas_de_tono,
)
from core.llm import construir_llms
from core.memory import make_checkpointer
from scripts.evals.casos import CASOS

# Nombre de la tool con la que el fork pasa la conversacion a un humano (None si no tiene).
TOOL_ESCALAR: str | None = None
# Aqui el fork agrega sus reglas de negocio, por ejemplo "no cierra sin decir el precio".
REGLAS = [regla_sin_respuesta_vacia, *reglas_de_tono(tool_escalar=TOOL_ESCALAR)]


def imprimir(nombre: str, corrida: int, turnos: list[Turno], metricas: Metricas) -> None:
    print(f"\n######## {nombre} (corrida {corrida})")
    for t in turnos:
        print(
            f"[t{t.numero}] {t.segundos:5.1f}s modelo x{t.llamadas_modelo} "
            f"tools={t.tools} contesto={t.contesto or '?'}"
            f"{' ERROR ' + t.error if t.error else ''}\n"
            f"      {t.final[:200]}"
        )
    for v in metricas.violaciones:
        print(f"  !! t{v.turno} {v.regla} {v.detalle}")


def _positivo(valor: str) -> int:
    numero = int(valor)
    if numero < 1:
        raise argparse.ArgumentTypeError("corridas tiene que ser mayor que 0")
    return numero


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evals del agente contra el LLM real")
    parser.add_argument("caso", nargs="?", default="todos", help="nombre del caso o 'todos'")
    parser.add_argument("corridas", nargs="?", type=_positivo, default=1)
    parser.add_argument(
        "--con-respaldo", action="store_true", help="usa solo el modelo de respaldo"
    )
    parser.add_argument("--json", help="guarda los turnos de cada corrida en este archivo")
    args = parser.parse_args(argv)

    if args.caso != "todos" and args.caso not in CASOS:
        raise SystemExit(f"Caso desconocido '{args.caso}'. Hay: {', '.join(CASOS)}")
    nombres = list(CASOS) if args.caso == "todos" else [args.caso]

    llm, llm_respaldo = construir_llms()
    llm, llm_respaldo = modelos_para_eval(llm, llm_respaldo, con_respaldo=args.con_respaldo)
    agente = armar_agente(make_checkpointer("memory"), llm, llm_respaldo)

    resumen: list[tuple[str, Metricas]] = []
    volcado: list[dict] = []
    for nombre in nombres:
        for corrida in range(1, args.corridas + 1):
            turnos = correr_caso(agente, CASOS[nombre])
            metricas = evaluar(turnos, REGLAS)
            imprimir(nombre, corrida, turnos, metricas)
            resumen.append((nombre, metricas))
            volcado.append(
                {"caso": nombre, "corrida": corrida, "turnos": [t.__dict__ for t in turnos]}
            )

    if args.json:
        with open(args.json, "w", encoding="utf-8") as archivo:
            json.dump(volcado, archivo, ensure_ascii=False, indent=1)

    print("\n==== RESUMEN ====")
    for nombre in nombres:
        filas = [m for n, m in resumen if n == nombre]
        turnos_total = sum(m.turnos for m in filas)
        modelos: dict[str, int] = {}
        for m in filas:
            for modelo, veces in m.modelos.items():
                modelos[modelo] = modelos.get(modelo, 0) + veces
        print(
            f"{nombre}: corridas={len(filas)} turnos={turnos_total} "
            f"llamadas/turno={sum(m.llamadas_modelo for m in filas) / turnos_total:.2f} "
            f"s/turno={sum(m.segundos for m in filas) / turnos_total:.1f} "
            f"violaciones={sum(len(m.violaciones) for m in filas)} contesto={modelos}"
        )
    return 1 if any(m.violaciones for _, m in resumen) else 0


if __name__ == "__main__":
    raise SystemExit(main())
