"""Chat interactivo en terminal para probar el agente completo en local.

Usa build_runner() (prompt, tools y guards del fork), sin servidor HTTP,
sin CHAT_API_KEY y sin curl. Requiere solo el .env con la API key del LLM.

    .venv/bin/python -m scripts.chat_cli
    .venv/bin/python -m scripts.chat_cli --session mi-prueba

Comandos: /nuevo (sesion nueva, historial limpio), /salir (o Ctrl+D).
Con MEMORY_KIND=memory el historial vive solo mientras corre este proceso.
"""

import argparse
import uuid

from app.bootstrap import build_runner


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat local con el agente")
    parser.add_argument("--session", default=None, help="session_id a usar")
    args = parser.parse_args()

    runner = build_runner()
    session_id = args.session or f"cli-{uuid.uuid4().hex[:8]}"
    print(f"Sesion: {session_id}  (/nuevo para reiniciar, /salir para terminar)")

    while True:
        try:
            mensaje = input("\ntu> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not mensaje:
            continue
        if mensaje == "/salir":
            break
        if mensaje == "/nuevo":
            session_id = f"cli-{uuid.uuid4().hex[:8]}"
            print(f"Sesion nueva: {session_id}")
            continue
        try:
            print(f"bot> {runner.responder(session_id, mensaje)}")
        except Exception as exc:
            print(f"[error] {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
