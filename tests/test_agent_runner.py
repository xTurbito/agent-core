"""Pruebas de AgentRunner: responder, registrar_turno, reset_thread, locks
por sesion y el fallback ante GraphRecursionError. Usa grafos minimos de
LangGraph sin pegarle a ningun LLM real.

La parte de reset_thread contra Postgres crea y destruye su propia base de
datos de prueba (ver _conectar_postgres_de_prueba) para no arriesgar ninguna
base de negocio real. Si no hay un Postgres local disponible, esa seccion se
salta con un aviso en vez de fallar: lo que valida (el archivado real en 3
tablas) no se puede fingir con un mock sin perder el sentido de la prueba.
"""

from typing import TypedDict

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from core.runner import FALLBACK_RESPONSE, AgentRunner


class _Estado(TypedDict):
    messages: list


def _grafo_que_responde_fijo(texto: str, checkpointer=None):
    def nodo(_state):
        return {"messages": [AIMessage(content=texto)]}

    g = StateGraph(_Estado)
    g.add_node("nodo", nodo)
    g.set_entry_point("nodo")
    g.add_edge("nodo", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


def _grafo_que_nunca_termina():
    def nodo(state):
        return {"messages": state["messages"]}

    g = StateGraph(_Estado)
    g.add_node("nodo", nodo)
    g.set_entry_point("nodo")
    g.add_edge("nodo", "nodo")
    return g.compile(checkpointer=InMemorySaver())


# --- responder() / responder_con_metadata() ---

runner = AgentRunner(_grafo_que_responde_fijo("hola, como puedo ayudarte"))
assert runner.responder("sesion-1", "hola") == "hola, como puedo ayudarte"
print("OK: responder() devuelve el texto generado por el grafo")

metadata = runner.responder_con_metadata("sesion-2", "hola")
assert metadata["text"] == "hola, como puedo ayudarte"
assert "usage_metadata" in metadata
assert "response_metadata" in metadata
print("OK: responder_con_metadata() incluye usage/response metadata")


# --- fallback ante GraphRecursionError ---

runner_en_loop = AgentRunner(_grafo_que_nunca_termina())
resultado = runner_en_loop.responder_con_metadata("sesion-loop", "hola")
assert resultado["text"] == FALLBACK_RESPONSE
assert resultado["usage_metadata"] is None
print("OK: un grafo que nunca llega a END devuelve FALLBACK_RESPONSE, no explota")


# --- lock por sesion ---

runner_lock = AgentRunner(_grafo_que_responde_fijo("x"))
lock_a1 = runner_lock._get_session_lock("sesion-a")
lock_a2 = runner_lock._get_session_lock("sesion-a")
lock_b = runner_lock._get_session_lock("sesion-b")
assert lock_a1 is lock_a2, "la misma sesion debe reusar el mismo lock"
assert lock_a1 is not lock_b, "sesiones distintas no deben compartir lock"
print("OK: el lock por sesion se reusa para la misma sesion y no se mezcla entre sesiones")


# --- registrar_turno() ---

grafo_registro = _grafo_que_responde_fijo("respuesta del grafo")
runner_registro = AgentRunner(grafo_registro)
runner_registro.registrar_turno("sesion-registro", "mensaje del usuario", "respuesta sin LLM")

mensajes = runner_registro.get_conversation_messages("sesion-registro")
assert len(mensajes) == 2
assert mensajes[-2].content == "mensaje del usuario"
assert mensajes[-1].content == "respuesta sin LLM"
print("OK: registrar_turno() escribe el turno en el checkpoint sin invocar al modelo")


# --- reset_thread() con InMemorySaver (desarrollo): sin archivo, borra directo ---

grafo_reset_mem = _grafo_que_responde_fijo("algo")
runner_reset_mem = AgentRunner(grafo_reset_mem)
runner_reset_mem.responder("sesion-a-borrar", "hola")
assert len(runner_reset_mem.get_conversation_messages("sesion-a-borrar")) > 0

runner_reset_mem.reset_thread("sesion-a-borrar")
assert runner_reset_mem.get_conversation_messages("sesion-a-borrar") == []
print("OK: reset_thread() con InMemorySaver borra el historial sin fallar")


# --- reset_thread() con Postgres real: debe ARCHIVAR (renombrar), no borrar ---


def _conectar_postgres_de_prueba():
    """Crea una base de datos de prueba aislada y desechable.

    Usa el Postgres local si esta disponible (igual host/puerto que el resto
    del proyecto), pero en una base nueva creada solo para esta corrida, que
    se destruye al final. Nunca toca una base de negocio existente.
    """
    import uuid

    import psycopg
    from psycopg.rows import dict_row

    nombre_db = f"agent_core_test_{uuid.uuid4().hex[:8]}"
    admin_url = "postgresql://postgres@127.0.0.1:5432/postgres"

    try:
        admin_conn = psycopg.Connection.connect(admin_url, autocommit=True)
    except psycopg.OperationalError:
        return None, None, None

    admin_conn.execute(f'CREATE DATABASE "{nombre_db}"')  # noqa: S608

    conn = psycopg.Connection.connect(
        f"postgresql://postgres@127.0.0.1:5432/{nombre_db}",
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )

    def limpiar():
        conn.close()
        admin_conn.execute(f'DROP DATABASE "{nombre_db}"')  # noqa: S608
        admin_conn.close()

    return conn, nombre_db, limpiar


conn, nombre_db, limpiar_postgres = _conectar_postgres_de_prueba()

if conn is None:
    print(
        "SALTADO: no hay Postgres local en 127.0.0.1:5432 (ver core/memory.py). "
        "reset_thread() contra Postgres real no se pudo verificar en esta corrida."
    )
else:
    from langgraph.checkpoint.postgres import PostgresSaver

    saver = PostgresSaver(conn)
    saver.setup()

    grafo_pg = _grafo_que_responde_fijo("respuesta guardada en postgres", checkpointer=saver)
    runner_pg = AgentRunner(grafo_pg)
    thread_id = "sesion-postgres-1"
    runner_pg.responder(thread_id, "hola")

    with conn.cursor() as cur:
        for tabla in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
            cur.execute(f"SELECT count(*) AS n FROM {tabla} WHERE thread_id = %s", (thread_id,))  # noqa: S608
            assert cur.fetchone()["n"] > 0, f"deberia haber filas en {tabla} antes de resetear"

    runner_pg.reset_thread(thread_id)

    with conn.cursor() as cur:
        filas_originales = 0
        filas_archivadas = 0
        for tabla in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
            cur.execute(f"SELECT count(*) AS n FROM {tabla} WHERE thread_id = %s", (thread_id,))  # noqa: S608
            filas_originales += cur.fetchone()["n"]

            cur.execute(
                f"SELECT count(*) AS n FROM {tabla} WHERE thread_id LIKE %s",  # noqa: S608
                (f"{thread_id}::archived::%",),
            )
            filas_archivadas += cur.fetchone()["n"]

    assert filas_originales == 0, "reset_thread no debe dejar NINGUNA fila bajo el thread_id original"
    assert filas_archivadas > 0, "reset_thread debe archivar (renombrar) las filas, no borrarlas"

    limpiar_postgres()
    print(
        "OK: reset_thread() contra Postgres real ARCHIVA (renombra thread_id en las 3 "
        "tablas) en vez de borrar -- verificado con datos reales, no con un mock"
    )


print("\nTodas las pruebas de AgentRunner pasaron.")
