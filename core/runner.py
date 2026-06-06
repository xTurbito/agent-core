"""Runner: interfaz simple para hablar con el agente.

Esconde los detalles de LangGraph (config, invoke, estructura de messages).
La app solo llama responder(session_id, mensaje) y recibe texto.
"""


class AgentRunner:
    def __init__(self, agent):
        self._agent = agent

    def responder(self, session_id: str, mensaje: str) -> str:
        config = {"configurable": {"thread_id": session_id}}
        result = self._agent.invoke(
            {"messages": [("user",  mensaje)]},
            config,
        )
        return result["messages"][-1].content