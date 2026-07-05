"""Runner: interfaz simple para hablar con el agente.

Esconde los detalles de LangGraph (config, invoke, estructura de messages).
La app solo llama responder(session_id, mensaje) y recibe texto.
"""

from threading import Lock


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
        config = {"configurable": {"thread_id": session_id}}
        result = self._agent.invoke(
            {"messages": [("user", mensaje)]},
            config,
        )
        message = result["messages"][-1]

        return {
            "text": extract_text(message.content),
            "usage_metadata": getattr(message, "usage_metadata", None),
            "response_metadata": getattr(message, "response_metadata", None),
        }
    
    def get_conversation_messages(self, session_id: str) -> list:
        config = {"configurable": {"thread_id": session_id}}
        snapshot = self._agent.get_state(config)
        return snapshot.values.get("messages", [])
