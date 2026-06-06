"""Factory de memoria (checkpointer).

Guarda el historial de cada conversacion, identificada por un thread_id
(ej. el numero de WhatsApp del cliente). Sin esto el agente es amnesico.
"""


def make_checkpointer(kind: str = "memory"):
    if kind == "memory":
        from langgraph.checkpoint.memory import InMemorySaver
        return InMemorySaver()
    
    raise ValueError(f"Tipo de memoria no soportado: {kind}")