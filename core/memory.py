"""Factory de memoria (checkpointer).

Guarda el historial de cada conversacion, identificada por un thread_id
(ej. el numero de WhatsApp del cliente). Sin esto el agente es amnesico.
"""

from typing import cast


def make_checkpointer(kind: str = "memory"):
    if kind == "memory":
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()

    if kind == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg import Connection
        from psycopg.rows import DictRow, dict_row

        from core.settings import settings

        if not settings.postgres_url:
            raise ValueError("POSTGRES_URL es requerido cuando MEMORY_KIND=postgres")

        conn = cast(
            Connection[DictRow],
            Connection.connect(
                settings.postgres_url,
                autocommit=True,
                prepare_threshold=0,
                row_factory=dict_row,
            ),
        )
        return PostgresSaver(conn)

    raise ValueError(f"Tipo de memoria no soportado: {kind}")
