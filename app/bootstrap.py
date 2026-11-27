"""Arma el runner de ESTE cliente (fork).

Junta config (settings) + tools del negocio + prompt, y devuelve un
AgentRunner listo. El core no sabe de esto; es especifico del fork.
"""

from app.memory.context import build_business_context
from app.prompts.system import SYSTEM_PROMPT
from app.tools.disponibilidad import consultar_disponibilidad
from core.agent import build_agent
from core.llm import construir_llms
from core.memory import make_checkpointer
from core.runner import AgentRunner
from core.settings import settings

TOOLS = [consultar_disponibilidad]


def armar_agente(checkpointer, llm=None, llm_respaldo=None):
    """Produccion y evals arman el agente aqui, para que los evals midan lo mismo que corre."""
    if llm is None:
        llm, llm_respaldo = construir_llms()
    return build_agent(
        llm,
        TOOLS,
        SYSTEM_PROMPT,
        checkpointer=checkpointer,
        context_provider=build_business_context,
        llm_respaldo=llm_respaldo,
    )


def build_runner() -> AgentRunner:
    return AgentRunner(armar_agente(make_checkpointer(settings.memory_kind)))
