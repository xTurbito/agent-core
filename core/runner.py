"""Runner: interfaz simple para hablar con el agente.

Esconde los detalles de LangGraph (config, invoke, estructura de messages).
La app solo llama responder(session_id, mensaje) y recibe texto.
"""

from threading import Lock

from langgraph.errors import GraphRecursionError

# Explicito en vez de confiar en el default de LangGraph (25): si un mensaje
# ambiguo hace que el LLM entre en un loop de tool-calls, mejor cortar rapido
# y responder algo seguro que dejar al usuario sin respuesta ese turno.
RECURSION_LIMIT = 25
FALLBACK_RESPONSE = (
    "Dame un segundo para revisar eso con calma y te contesto. "
    "Mientras tanto, ¿hay algo más en lo que te pueda ayudar?"
)


def extract_text(content) -> str:
    """Normaliza content de un mensaje de LLM a texto plano.

    Algunos proveedores (ej. Gemini con thinking) devuelven una lista de
    bloques ({"type": "text", ...} + bloques internos de razonamiento) en vez
    de un string. Aqui nos quedamos solo con el texto visible para el usuario.
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )

    return str(content)


class AgentRunner:
    def __init__(self, agent):
        self._agent = agent
        self._locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

    def responder(self, session_id: str, mensaje: str) -> str:
        return self.responder_con_metadata(session_id, mensaje)["text"]

    def responder_con_metadata(self, session_id: str, mensaje: str) -> dict:
        session_lock = self._get_session_lock(session_id)

        with session_lock:
            return self._responder_con_metadata(session_id, mensaje)

    def _get_session_lock(self, session_id: str) -> Lock:
        with self._locks_guard:
            if session_id not in self._locks:
                self._locks[session_id] = Lock()
            return self._locks[session_id]

    def _responder_con_metadata(self, session_id: str, mensaje: str) -> dict:
        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": RECURSION_LIMIT,
        }
        try:
            result = self._agent.invoke(
                {"messages": [("user", mensaje)]},
                config,
            )
        except GraphRecursionError:
            # El LLM entro en un loop de tool-calls (mensaje ambiguo, datos
            # contradictorios, etc.) y LangGraph corto la ejecucion. Sin este
            # catch la excepcion sube sin manejar y el usuario se queda sin
            # respuesta ese turno.
            return {
                "text": FALLBACK_RESPONSE,
                "usage_metadata": None,
                "response_metadata": None,
            }

        message = result["messages"][-1]

        return {
            "text": extract_text(message.content),
            "usage_metadata": getattr(message, "usage_metadata", None),
            "response_metadata": getattr(message, "response_metadata", None),
        }

    def registrar_turno(self, session_id: str, mensaje: str, respuesta: str) -> None:
        """Guarda en el historial un turno que NO paso por el LLM.

        Hay canales que responden solos a ciertos eventos (una foto que el
        agente no puede ver, por ejemplo). Si ese turno no se registra, el
        historial queda desincronizado con lo que el usuario ve: el agente no
        sabe lo que el mismo dijo y repite lo que ya resolvio.

        Va aparte de responder() a proposito: aqui no se invoca al modelo, solo
        se escribe el checkpoint. Toma el lock de la sesion para no escribir
        encima de un turno en curso.
        """
        from langchain_core.messages import AIMessage, HumanMessage

        with self._get_session_lock(session_id):
            self._agent.update_state(
                {"configurable": {"thread_id": session_id}},
                {"messages": [HumanMessage(content=mensaje), AIMessage(content=respuesta)]},
            )

    def get_conversation_messages(self, session_id: str) -> list:
        config = {"configurable": {"thread_id": session_id}}
        snapshot = self._agent.get_state(config)
        return snapshot.values.get("messages", [])

    def reset_thread(self, session_id: str) -> None:
        """Archiva el historial de checkpoint de una sesion, liberando el
        thread_id para que la sesion vuelva a arrancar limpia.

        Para cuando una conversacion se da por cerrada (ej. cita ya
        confirmada) y no debe arrastrar contexto viejo si la misma sesion
        vuelve a escribir despues por algo nuevo.

        Archiva (renombra thread_id) en vez de borrar: un DELETE real no
        deja rastro para depurar que paso si la conversacion se cerro de
        forma prematura (ej. a mitad de un intercambio en curso, no en una
        reactivacion real dias despues). El checkpointer no ofrece un
        "archive" nativo, asi que se renombra directo en las 3 tablas que
        usa PostgresSaver.delete_thread (checkpoints, checkpoint_blobs,
        checkpoint_writes); verificado con inspect que son esas y ninguna
        mas.
        """
        from datetime import UTC, datetime

        with self._get_session_lock(session_id):
            checkpointer = self._agent.checkpointer
            if not hasattr(checkpointer, "conn"):
                # InMemorySaver (desarrollo): no hay nada que archivar.
                checkpointer.delete_thread(session_id)
                return

            archived_id = f"{session_id}::archived::{datetime.now(UTC).timestamp()}"
            with checkpointer.conn.cursor() as cur:
                for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
                    cur.execute(
                        f"UPDATE {table} SET thread_id = %s WHERE thread_id = %s",  # noqa: S608
                        (archived_id, session_id),
                    )
