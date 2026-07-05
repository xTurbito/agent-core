"""Crea/actualiza las tablas del checkpointer Postgres de LangGraph."""

import sys
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.settings import settings


def main() -> None:
    load_dotenv()

    if not settings.postgres_url:
        raise ValueError("POSTGRES_URL es requerido para configurar memoria Postgres")

    with PostgresSaver.from_conn_string(settings.postgres_url) as checkpointer:
        checkpointer.setup()

    print("Memoria Postgres configurada correctamente.")


if __name__ == "__main__":
    main()
