"""Arma el runner de ESTE cliente (fork).

Junta config (settings) + tools del negocio + prompt, y devuelve un
AgentRunner listo. El core no sabe de esto; es especifico del fork.
"""

from app.memory.context import build_business_context
from app.prompts.system import SYSTEM_PROMPT
from app.tools.disponibilidad import consultar_disponibilidad
from core.agent import build_agent
from core.llm import make_llm
from core.memory import make_checkpointer
from core.runner import AgentRunner
from core.settings import settings

TOOLS = [consultar_disponibilidad]


def build_runner() -> AgentRunner:
    llm = make_llm(
        settings.llm_provider,
        settings.llm_model,
        api_key=settings.active_llm_api_key,
    )
    checkpointer = make_checkpointer(settings.memory_kind)
    agent = build_agent(
        llm,
        TOOLS,
        SYSTEM_PROMPT,
        checkpointer=checkpointer,
        context_provider=build_business_context,
    )
    return AgentRunner(agent)
