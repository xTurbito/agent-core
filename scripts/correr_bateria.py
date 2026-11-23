"""Corre toda la bateria offline de tests/ y falla si algun modulo falla.

Uso: .venv/bin/python scripts/correr_bateria.py [test_modulo ...]

Los tests son scripts planos (asserts al importar), asi que cada modulo corre
en su propio proceso con `python -m tests.<modulo>`. Sin argumentos corre
todos los `tests/test_*.py`.

POSTGRES_URL se vacia a proposito: el `.env` local apunta a una BD real
compartida y la bateria offline no debe poder leerla ni escribirla. Un test
que la necesite falla aqui en vez de tocar produccion.
"""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TIMEOUT_SEGUNDOS = 120

# Modulos que ya fallaban al montar el CI. Se corren igual: si alguno vuelve a
# pasar, la bateria falla para obligar a quitarlo de aqui. No agregar entradas
# para tapar una regresion; esto solo registra deuda que ya existia.
EN_CUARENTENA: dict[str, str] = {}


def _entorno() -> dict[str, str]:
    entorno = dict(os.environ)
    entorno["POSTGRES_URL"] = ""
    return entorno


def _correr(modulo: str) -> tuple[str, bool, str]:
    try:
        resultado = subprocess.run(
            [sys.executable, "-m", f"tests.{modulo}"],
            cwd=RAIZ,
            env=_entorno(),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEGUNDOS,
        )
    except subprocess.TimeoutExpired:
        return modulo, False, f"timeout tras {TIMEOUT_SEGUNDOS}s"
    salida = (resultado.stdout + resultado.stderr).strip()
    return modulo, resultado.returncode == 0, salida


def _modulos(argumentos: list[str]) -> list[str]:
    if argumentos:
        return argumentos
    return sorted(ruta.stem for ruta in (RAIZ / "tests").glob("test_*.py"))


def main(argumentos: list[str]) -> int:
    modulos = _modulos(argumentos)
    inicio = time.monotonic()
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as hilos:
        resultados = list(hilos.map(_correr, modulos))

    fallaron = []
    revividos = []
    conocidos = 0
    for modulo, paso, salida in resultados:
        en_cuarentena = modulo in EN_CUARENTENA
        if paso and en_cuarentena:
            revividos.append(modulo)
        elif not paso and en_cuarentena:
            conocidos += 1
            print(f"CUARENTENA {modulo}: {EN_CUARENTENA[modulo]}")
        elif not paso:
            fallaron.append(modulo)
            print(f"\nFALLO {modulo}\n{salida[-3000:]}\n")

    for modulo in revividos:
        print(f"REVIVIO {modulo}: ya pasa, quitalo de EN_CUARENTENA")

    pasaron = len(modulos) - len(fallaron) - conocidos - len(revividos)
    duracion = time.monotonic() - inicio
    print(
        f"\n{pasaron} pasaron, {len(fallaron)} fallaron, {conocidos} en cuarentena, "
        f"{len(revividos)} revividos ({duracion:.0f}s)"
    )
    return 1 if fallaron or revividos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
